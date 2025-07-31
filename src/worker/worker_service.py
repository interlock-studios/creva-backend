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

from src.services.tiktok_scraper import TikTokScraper, ScrapingOptions
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

logger.info(f"Starting worker - Environment: {environment}, Project: {project_id}, Worker ID: {WORKER_ID}")


class VideoWorker:
    def __init__(self):
        self.running = False
        self.tasks = set()
        
        # Initialize services
        self.scraper = TikTokScraper()
        self.genai_pool = GenAIServicePool()
        self.cache_service = CacheService()
        self.queue_service = QueueService()
        self.video_processor = VideoProcessor()
        
        logger.info(f"Worker initialized with {self.genai_pool.get_pool_size()} GenAI services")
    
    async def process_video_job(self, job: dict):
        """Process a single video job"""
        job_id = job["job_id"]
        url = job["url"]
        start_time = time.time()
        
        try:
            logger.info(f"Processing job {job_id} - URL: {url[:50]}...")
            
            # Check cache first (in case it was processed by another worker)
            cached_workout = self.cache_service.get_cached_workout(url)
            if cached_workout:
                logger.info(f"Job {job_id} - Found in cache, marking complete")
                await self.queue_service.mark_job_complete(job_id, cached_workout)
                return
            
            # Configure scraping options
            options = ScrapingOptions(
                get_transcript=True,
                trim_response=True,
                max_retries=3,
                timeout=30,
            )
            
            # 1. Scrape video with transcript
            logger.info(f"Job {job_id} - Scraping video...")
            video_content, metadata, transcript = await self.scraper.scrape_tiktok_complete(url, options)
            
            if transcript:
                logger.info(f"Job {job_id} - Got transcript: {len(transcript)} characters")
            else:
                logger.info(f"Job {job_id} - No transcript available")
            
            # 2. Remove audio
            logger.info(f"Job {job_id} - Removing audio...")
            silent_video = await self.video_processor.remove_audio(video_content)
            
            # 3. Get GenAI service from pool
            genai_service = await self.genai_pool.get_next_service()
            
            # 4. Analyze with Gemini
            caption = metadata.description or metadata.caption
            logger.info(f"Job {job_id} - Analyzing with GenAI service {genai_service.service_id}...")
            
            workout_json = genai_service.analyze_video_with_transcript(
                silent_video, transcript, caption
            )
            
            if not workout_json:
                raise Exception("Could not extract workout information from video")
            
            # 5. Cache the result
            cache_metadata = {
                "title": metadata.title,
                "author": metadata.author,
                "duration_seconds": metadata.duration_seconds,
                "processed_at": datetime.utcnow().isoformat(),
                "worker_id": WORKER_ID
            }
            self.cache_service.cache_workout(url, workout_json, cache_metadata)
            
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
        
        while self.running:
            try:
                # Get next job from queue
                job = await self.queue_service.get_next_job(WORKER_ID)
                
                if job:
                    # Process job asynchronously
                    task = asyncio.create_task(self.process_video_job(job))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
                else:
                    # No jobs available, wait before polling again
                    await asyncio.sleep(POLLING_INTERVAL)
                
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
                    timeout=WORKER_SHUTDOWN_TIMEOUT
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
        "genai_services": worker.genai_pool.get_pool_size() if worker else 0
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
        "timestamp": datetime.now().isoformat()
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