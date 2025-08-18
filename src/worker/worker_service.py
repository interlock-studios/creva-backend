"""
Worker service for processing queued TikTok videos
Runs as a separate Cloud Run service from the main API
"""

import os
import asyncio
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import socket


from src.services.genai_service_pool import GenAIServicePool
from src.services.cache_service import CacheService
from src.services.queue_service import QueueService
from src.worker.video_processor import VideoProcessor
from src.services.config_validator import validate_required_env_vars, get_config_with_defaults

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Validate configuration
validate_required_env_vars(["SCRAPECREATORS_API_KEY", "GOOGLE_CLOUD_PROJECT_ID"], "Worker")

# Get configuration
config = get_config_with_defaults()
environment = config["environment"]
project_id = config["project_id"]

# Worker configuration
WORKER_ID = f"worker-{socket.gethostname()}-{os.getpid()}"
POLLING_INTERVAL = config["worker_polling_interval"]
WORKER_BATCH_SIZE = config["worker_batch_size"]
WORKER_SHUTDOWN_TIMEOUT = config["worker_shutdown_timeout"]

logger.info(
    f"Starting worker - Environment: {environment}, Project: {project_id}, Worker ID: {WORKER_ID}"
)


class VideoWorker:
    def __init__(self):
        self.running = False
        self.tasks = set()

        # Initialize services
        self.genai_pool = GenAIServicePool()
        self.cache_service = CacheService()
        self.queue_service = QueueService()
        self.video_processor = VideoProcessor()

        logger.info(f"Worker initialized with {self.genai_pool.get_pool_size()} GenAI services")

    async def process_video_job(self, job: dict):
        """Process a single video job"""
        job_id = job["job_id"]
        url = job["url"]
        localization = job.get("localization")
        start_time = time.time()

        try:
            logger.info(f"Processing job {job_id} - URL: {url[:50]}...")

            # Check cache first (in case it was processed by another worker)
            cached_workout = self.cache_service.get_cached_workout(url, localization)
            if cached_workout:
                logger.info(f"Job {job_id} - Found in cache, marking complete")
                await self.queue_service.mark_job_complete(job_id, cached_workout)
                return

            # 1. Download content using video processor (handles both TikTok and Instagram)
            logger.info(f"Job {job_id} - Downloading and processing content...")
            video_content, metadata_dict = await self.video_processor.download_video(url)

            # Check if this is a slideshow
            is_slideshow = metadata_dict.get("is_slideshow", False)

            # Extract transcript from metadata
            transcript = metadata_dict.get("transcript_text")
            caption = metadata_dict.get("caption", "") or metadata_dict.get("description", "")

            if transcript:
                logger.info(f"Job {job_id} - Got transcript/caption: {len(transcript)} characters")
            else:
                logger.info(f"Job {job_id} - No transcript/caption available")

            if is_slideshow:
                # Handle slideshow content
                logger.info(
                    f"Job {job_id} - Processing slideshow with {metadata_dict.get('image_count', 0)} images"
                )

                # For slideshows, get all images and analyze directly
                platform = self.video_processor.url_router.detect_platform(url)
                if platform == "tiktok":
                    # Get all slideshow images
                    slideshow_images, slideshow_metadata, slideshow_transcript = (
                        await self.video_processor.tiktok_scraper.scrape_tiktok_slideshow(url)
                    )

                    # Use the slideshow-specific transcript if available
                    if slideshow_transcript:
                        transcript = slideshow_transcript

                    # Analyze slideshow with GenAI
                    logger.info(f"Job {job_id} - Analyzing slideshow with AI...")
                    workout_json = await self.genai_pool.analyze_slideshow(
                        slideshow_images, transcript, caption
                    )
                else:
                    # Instagram slideshows (if supported in the future)
                    logger.warning(f"Job {job_id} - Instagram slideshows not yet supported")
                    raise Exception("Instagram slideshows not yet supported")
            else:
                # Handle regular video content
                logger.info(f"Job {job_id} - Processing regular video")

                # 2. Process audio removal for video analysis
                logger.info(f"Job {job_id} - Removing audio from video...")
                silent_video = await self.video_processor.remove_audio(video_content)

                # 3. Analyze with Gemini
                logger.info(f"Job {job_id} - Analyzing video with AI...")
                workout_json = await self.genai_pool.analyze_video(
                    silent_video, transcript, caption, localization
                )

            if not workout_json:
                raise Exception("Could not extract workout information from video")

            # 5. Cache the result
            cache_metadata = {
                "title": metadata_dict.get("title", "Unknown"),
                "author": metadata_dict.get("uploader", "Unknown"),
                "duration_seconds": metadata_dict.get("duration", 0),
                "processed_at": datetime.utcnow().isoformat(),
                "worker_id": WORKER_ID,
                "platform": metadata_dict.get("platform", "unknown"),
            }
            self.cache_service.cache_workout(url, workout_json, cache_metadata, localization)

            # 6. Mark job complete
            await self.queue_service.mark_job_complete(job_id, workout_json)

            process_time = time.time() - start_time
            logger.info(f"Job {job_id} - Completed successfully in {process_time:.2f}s")

        except Exception as e:
            process_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Job {job_id} - Failed after {process_time:.2f}s: {error_msg}")

            # Mark job as failed (will retry if under max attempts)
            await self.queue_service.mark_job_failed(job_id, error_msg)

    async def worker_loop(self):
        """Main worker loop"""
        logger.info(f"Worker {WORKER_ID} starting main loop")
        logger.info(
            f"Worker configuration: batch_size={WORKER_BATCH_SIZE}, polling_interval={POLLING_INTERVAL}"
        )

        while self.running:
            try:
                # Check if we can take more jobs
                active_tasks = len(self.tasks)
                if active_tasks < WORKER_BATCH_SIZE:
                    # Get next job from queue
                    job = await self.queue_service.get_next_job(WORKER_ID)

                    if job:
                        # Process job asynchronously
                        task = asyncio.create_task(self.process_video_job(job))
                        self.tasks.add(task)
                        task.add_done_callback(self.tasks.discard)
                        logger.info(
                            f"Started processing job {job['job_id']} ({active_tasks + 1}/{WORKER_BATCH_SIZE} active)"
                        )
                    else:
                        # No jobs available, wait before polling again
                        await asyncio.sleep(POLLING_INTERVAL)
                else:
                    # At capacity, wait a bit before checking again
                    await asyncio.sleep(0.05)  # Check more frequently when at capacity

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(POLLING_INTERVAL)

    async def start(self):
        """Start the worker"""
        self.running = True
        logger.info(f"Worker {WORKER_ID} started")
        await self.worker_loop()

    async def stop(self):
        """Stop the worker gracefully"""
        logger.info(f"Worker {WORKER_ID} stopping...")
        self.running = False

        # Wait for active tasks to complete
        if self.tasks:
            logger.info(f"Waiting for {len(self.tasks)} active tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.tasks, return_exceptions=True),
                    timeout=WORKER_SHUTDOWN_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Shutdown timeout reached, cancelling {len(self.tasks)} tasks")
                for task in self.tasks:
                    task.cancel()

        logger.info(f"Worker {WORKER_ID} stopped")


# For Cloud Run health checks (optional)
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

worker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker
    # Startup
    worker = VideoWorker()
    # Start worker in background
    asyncio.create_task(worker.start())
    logger.info("Worker FastAPI app started")

    yield

    # Shutdown
    if worker:
        await worker.stop()
    logger.info("Worker FastAPI app stopped")


app = FastAPI(title="TikTok Workout Parser Worker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "worker_id": WORKER_ID,
        "timestamp": datetime.now().isoformat(),
        "genai_services": worker.genai_pool.get_pool_size() if worker else 0,
    }


@app.get("/worker/stats")
async def worker_stats():
    """Get worker statistics"""
    if not worker:
        return JSONResponse(status_code=503, content={"error": "Worker not initialized"})

    return {
        "worker_id": WORKER_ID,
        "running": worker.running,
        "active_tasks": len(worker.tasks),
        "genai_pool_size": worker.genai_pool.get_pool_size(),
        "timestamp": datetime.now().isoformat(),
    }


# Main entry point for running directly
async def main():
    """Run worker without FastAPI (for testing or simple deployments)"""
    worker = VideoWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    # For Cloud Run, use FastAPI with uvicorn
    import uvicorn

    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port)

    # For direct execution (testing), use asyncio
    # asyncio.run(main())
