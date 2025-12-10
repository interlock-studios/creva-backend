"""
Worker service for processing queued TikTok videos
Runs as a separate Cloud Run service from the main API
"""

import os
import asyncio
import logging
import time
import base64
from datetime import datetime, timedelta, timezone
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
        self._task_cleanup_lock = asyncio.Lock()
        
        # Exponential backoff for polling
        self._consecutive_empty_polls = 0
        self._max_backoff = 30.0  # Max 30 seconds between polls
        self._base_polling_interval = POLLING_INTERVAL

        # Queue cleanup tracking
        self._last_cleanup = datetime.now()
        self._cleanup_interval = timedelta(hours=1)  # Run cleanup every hour

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
            cached_bucket_list = await self.cache_service.get_cached_bucket_list(url, localization)
            if cached_bucket_list:
                logger.info(f"Job {job_id} - Found in cache, marking complete")
                # Mark as cached when returning from cache
                cached_bucket_list["cached"] = True
                await self.queue_service.mark_job_complete(job_id, cached_bucket_list)
                return

            # 1. Download content using video processor (handles both TikTok and Instagram)
            logger.info(f"Job {job_id} - Downloading and processing content...")
            video_content, metadata_dict = await self.video_processor.download_video(url)

            # Check if this is a slideshow
            is_slideshow = metadata_dict.get("is_slideshow", False)

            # Extract transcript from metadata
            transcript = metadata_dict.get("transcript_text")
            caption = metadata_dict.get("caption", "")
            description = metadata_dict.get("description", "")
            extracted_image_base64 = None

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

                    # Extract first image from slideshow
                    if slideshow_images:
                        try:
                            first_image = await self.video_processor.extract_image_from_slideshow(
                                slideshow_images
                            )
                            extracted_image_base64 = f"data:image/jpeg;base64,{base64.b64encode(first_image).decode('utf-8')}"
                            logger.info(f"Job {job_id} - Extracted first image from slideshow")
                        except Exception as e:
                            logger.warning(f"Job {job_id} - Failed to extract slideshow image: {e}")

                    # Analyze slideshow with GenAI
                    logger.info(f"Job {job_id} - Analyzing slideshow with AI...")
                    workout_json = await self.genai_pool.analyze_slideshow(
                        slideshow_images, transcript, caption, description, localization
                    )
                else:
                    # Handle Instagram slideshows - same pattern as TikTok
                    logger.info(f"Job {job_id} - Processing Instagram slideshow")
                    slideshow_images, slideshow_metadata, slideshow_transcript = (
                        await self.video_processor.instagram_scraper.scrape_instagram_slideshow(url)
                    )

                    # Use the slideshow-specific transcript if available
                    if slideshow_transcript:
                        transcript = slideshow_transcript

                    # Extract first image from slideshow
                    if slideshow_images:
                        try:
                            first_image = await self.video_processor.extract_image_from_slideshow(
                                slideshow_images
                            )
                            extracted_image_base64 = f"data:image/jpeg;base64,{base64.b64encode(first_image).decode('utf-8')}"
                            logger.info(f"Job {job_id} - Extracted first image from Instagram slideshow")
                        except Exception as e:
                            logger.warning(f"Job {job_id} - Failed to extract Instagram slideshow image: {e}")

                    # Analyze slideshow with GenAI
                    logger.info(f"Job {job_id} - Analyzing Instagram slideshow with AI...")
                    workout_json = await self.genai_pool.analyze_slideshow(
                        slideshow_images, transcript, caption, description, localization
                    )
            else:
                # Handle regular video content
                logger.info(f"Job {job_id} - Processing regular video")

                # Extract first frame from video
                try:
                    first_frame = await self.video_processor.extract_first_frame(video_content)
                    extracted_image_base64 = (
                        f"data:image/jpeg;base64,{base64.b64encode(first_frame).decode('utf-8')}"
                    )
                    logger.info(f"Job {job_id} - Extracted first frame from video")
                except Exception as e:
                    logger.warning(f"Job {job_id} - Failed to extract video frame: {e}")

                # 2. Analyze with Gemini (no audio removal needed)
                logger.info(f"Job {job_id} - Analyzing video with AI...")
                workout_json = await self.genai_pool.analyze_video(
                    video_content, transcript, caption, description, localization
                )

            if not workout_json:
                raise Exception("Could not extract workout information from video")

            # Override the image field with the extracted frame/image if available
            if extracted_image_base64:
                workout_json["image"] = extracted_image_base64

            # 5. Cache the result
            cache_metadata = {
                "title": metadata_dict.get("title", "Unknown"),
                "author": metadata_dict.get("uploader", "Unknown"),
                "duration_seconds": metadata_dict.get("duration", 0),
                "processed_at": datetime.utcnow().isoformat(),
                "worker_id": WORKER_ID,
                "platform": metadata_dict.get("platform", "unknown"),
            }
            await self.cache_service.cache_bucket_list(url, workout_json, cache_metadata, localization)

            # 6. Mark job complete
            await self.queue_service.mark_job_complete(job_id, workout_json)

            process_time = time.time() - start_time
            logger.info(f"Job {job_id} - Completed successfully in {process_time:.2f}s")

        except Exception as e:
            process_time = time.time() - start_time
            # Ensure error message is a clean string without object references
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Job {job_id} - Failed after {process_time:.2f}s: {error_msg}")

            # Classify error for better retry logic
            is_retryable = self._is_retryable_error(e)
            if not is_retryable:
                # For non-retryable errors, mark as failed immediately
                logger.error(f"Job {job_id} - Non-retryable error, moving to dead letter queue: {error_msg}")
                # Force max attempts to move to dead letter queue
                job["attempts"] = job.get("max_attempts", 3)
            
            # Mark job as failed (will retry if under max attempts)
            await self.queue_service.mark_job_failed(job_id, error_msg)

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is worth retrying"""
        # Import here to avoid circular imports
        from src.exceptions import VideoFormatError, UnsupportedPlatformError
        
        # Non-retryable errors
        non_retryable_types = (
            VideoFormatError,
            UnsupportedPlatformError,
            ValueError,  # Usually indicates bad input data
            KeyError,    # Usually indicates malformed data
        )
        
        # Circuit breaker errors would be retryable (service might recover)
        # Note: CircuitBreakerOpenError not currently implemented
        
        # Check for non-retryable error types
        if isinstance(error, non_retryable_types):
            return False
        
        # Check error message for non-retryable patterns
        error_msg = str(error).lower()
        non_retryable_patterns = [
            "invalid url",
            "malformed url", 
            "video not found",
            "private video",
            "video unavailable",
            "unsupported format",
            "invalid video id",
        ]
        
        for pattern in non_retryable_patterns:
            if pattern in error_msg:
                return False
        
        # Default to retryable for network/API errors
        return True

    async def periodic_queue_cleanup(self):
        """Perform periodic queue cleanup to prevent backup"""
        try:
            logger.info("Starting periodic queue cleanup...")
            
            # Clean up old jobs (older than 24 hours)
            deleted_count = await self.queue_service.cleanup_old_jobs(days=1, batch_size=50)
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old jobs from queue")
            else:
                logger.debug("No old jobs to clean up")
                
            self._last_cleanup = datetime.now()
            
        except Exception as e:
            logger.error(f"Error during periodic queue cleanup: {e}")

    async def worker_loop(self):
        """Main worker loop"""
        logger.info(f"Worker {WORKER_ID} starting main loop")
        logger.info(
            f"Worker configuration: batch_size={WORKER_BATCH_SIZE}, polling_interval={POLLING_INTERVAL}"
        )

        while self.running:
            try:
                # Periodic queue cleanup
                if datetime.now() - self._last_cleanup > self._cleanup_interval:
                    asyncio.create_task(self.periodic_queue_cleanup())
                
                # Check if we can take more jobs
                active_tasks = len(self.tasks)
                if active_tasks < WORKER_BATCH_SIZE:
                    # Get next job from queue
                    job = await self.queue_service.get_next_job(WORKER_ID)

                    if job:
                        # Reset backoff when we find work
                        self._consecutive_empty_polls = 0
                        
                        # Process job asynchronously with robust cleanup
                        task = asyncio.create_task(self.process_video_job(job))
                        self.tasks.add(task)
                        
                        # Robust task cleanup with error handling
                        def cleanup_task(finished_task):
                            asyncio.create_task(self._safe_task_cleanup(finished_task))
                        
                        task.add_done_callback(cleanup_task)
                        logger.info(
                            f"Started processing job {job['job_id']} ({active_tasks + 1}/{WORKER_BATCH_SIZE} active)"
                        )
                    else:
                        # No jobs available, use exponential backoff
                        self._consecutive_empty_polls += 1
                        backoff_time = min(
                            self._max_backoff,
                            self._base_polling_interval * (2 ** min(self._consecutive_empty_polls - 1, 5))
                        )
                        
                        if self._consecutive_empty_polls > 1:
                            logger.debug(f"No jobs found, backing off for {backoff_time:.1f}s (attempt {self._consecutive_empty_polls})")
                        
                        await asyncio.sleep(backoff_time)
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

    async def _safe_task_cleanup(self, task):
        """Safely remove completed task from tracking set"""
        async with self._task_cleanup_lock:
            try:
                self.tasks.discard(task)
                
                # Log any task exceptions for debugging
                if task.done() and not task.cancelled():
                    try:
                        task.result()  # This will raise if the task had an exception
                    except Exception as e:
                        logger.warning(f"Task completed with exception: {e}")
                        
            except Exception as e:
                logger.error(f"Error during task cleanup: {e}")
                # Ensure task is removed even if cleanup fails
                try:
                    self.tasks.discard(task)
                except:
                    pass


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
        "last_cleanup": worker._last_cleanup.isoformat(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/worker/queue-health")
async def queue_health():
    """Get queue health metrics"""
    if not worker:
        return JSONResponse(status_code=503, content={"error": "Worker not initialized"})
    
    try:
        # Get queue status
        queue_service = worker.queue_service
        if not queue_service.db:
            return {"error": "Queue service not available"}
        
        # Count jobs by status
        pending = len(list(queue_service.queue_collection.where('status', '==', 'pending').stream()))
        processing = len(list(queue_service.queue_collection.where('status', '==', 'processing').stream()))
        
        # Check for any old jobs that might be accumulating
        from datetime import timedelta
        old_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        old_jobs = len(list(queue_service.queue_collection.where('created_at', '<', old_cutoff).stream()))
        
        return {
            "queue_status": {
                "pending": pending,
                "processing": processing,
                "old_jobs_24h": old_jobs
            },
            "health": "healthy" if old_jobs < 10 else "warning" if old_jobs < 50 else "critical",
            "last_cleanup": worker._last_cleanup.isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to get queue health: {str(e)}"})


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

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

    # For direct execution (testing), use asyncio
    # asyncio.run(main())
