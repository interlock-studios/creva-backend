from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import logging
import time
import json
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from collections import defaultdict
import asyncio

from src.services.tiktok_scraper import (
    TikTokScraper,
    ScrapingOptions,
    APIError,
    NetworkError,
    ValidationError,
)
from src.services.genai_service import GenAIService
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
validate_required_env_vars(["SCRAPECREATORS_API_KEY", "GOOGLE_CLOUD_PROJECT_ID"], "API")

# Get configuration
config = get_config_with_defaults()
environment = config["environment"]
project_id = config["project_id"]
logger.info(f"Starting application - Environment: {environment}, Project: {project_id}")


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutdown complete")


app = FastAPI(
    title="TikTok Workout Parser - AI Powered",
    version="1.0.0",
    docs_url="/docs" if environment != "production" else None,
    redoc_url="/redoc" if environment != "production" else None,
    lifespan=lifespan,
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Configure based on your domain

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", f"{time.time()}-{os.getpid()}")
    request.state.request_id = request_id

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)

    # Log request details
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": round(process_time, 3),
            }
        )
    )

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled exception - Request ID: {request_id}", exc_info=exc)

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


scraper = TikTokScraper()
genai_service = GenAIService()
video_processor = VideoProcessor()
cache_service = CacheService()
queue_service = QueueService()


class ProcessRequest(BaseModel):
    url: str


@app.post("/process")
async def process_video(request: ProcessRequest, req: Request):
    """Process a TikTok video and return workout JSON"""
    
    request_id = getattr(req.state, "request_id", "unknown")
    
    # Check cache first
    cached_workout = cache_service.get_cached_workout(request.url)
    if cached_workout:
        logger.info(f"Returning cached result - Request ID: {request_id}, URL: {request.url}")
        return cached_workout
    
    # Check if already in queue with pending status
    existing_job = await queue_service.get_job_by_url(request.url, status="pending")
    if existing_job:
        logger.info(f"Video already queued - Request ID: {request_id}, Job ID: {existing_job['job_id']}")
        return {
            "status": "queued",
            "job_id": existing_job["job_id"],
            "message": "Video already queued for processing",
            "check_url": f"/status/{existing_job['job_id']}"
        }
    
    # Check if already processing
    processing_job = await queue_service.get_job_by_url(request.url, status="processing")
    if processing_job:
        logger.info(f"Video already processing - Request ID: {request_id}, Job ID: {processing_job['job_id']}")
        return {
            "status": "processing",
            "job_id": processing_job["job_id"],
            "message": "Video is currently being processed",
            "check_url": f"/status/{processing_job['job_id']}"
        }
    
    try:
        # Add to queue with normal priority
        job_id = await queue_service.enqueue_video(request.url, request_id, priority="normal")
        
        logger.info(f"Video queued for processing - Request ID: {request_id}, Job ID: {job_id}")
        
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Video queued for processing. Check status with job_id.",
            "check_url": f"/status/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to queue video - Request ID: {request_id}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue video: {str(e)}")


# Rate limiting configuration
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))     # seconds
rate_limit_store = defaultdict(list)

# Request queue management
MAX_CONCURRENT_PROCESSING = int(os.getenv("MAX_CONCURRENT_PROCESSING", "50"))
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROCESSING)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)
    
    # Get client IP (handle proxy headers)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    current_time = time.time()
    
    # Clean old entries
    rate_limit_store[client_ip] = [
        req_time for req_time in rate_limit_store[client_ip] 
        if current_time - req_time < RATE_LIMIT_WINDOW
    ]
    
    # Check rate limit
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": f"Too many requests. Limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds",
                "retry_after": RATE_LIMIT_WINDOW
            },
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)}
        )
    
    # Add current request
    rate_limit_store[client_ip].append(current_time)
    
    return await call_next(request)


@app.get("/health")
async def health():
    """Health check endpoint with service validation"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": environment,
        "project_id": project_id,
        "version": "1.0.0",
        "services": {}
    }
    
    # Check cache service
    try:
        cache_healthy = cache_service.is_healthy()
        health_status["services"]["cache"] = "healthy" if cache_healthy else "unhealthy"
    except Exception as e:
        health_status["services"]["cache"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check queue service
    try:
        queue_stats = queue_service.get_queue_stats()
        health_status["services"]["queue"] = queue_stats.get("status", "unknown")
        if queue_stats.get("status") == "error":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["queue"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check TikTok scraper
    try:
        # Just check if the service is initialized
        health_status["services"]["tiktok_scraper"] = "healthy"
    except Exception as e:
        health_status["services"]["tiktok_scraper"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/status")
async def status():
    """Status endpoint showing current system load and queue status"""
    current_time = time.time()
    
    # Calculate active rate limit entries
    active_ips = sum(
        1 for ip_requests in rate_limit_store.values()
        if any(current_time - req_time < RATE_LIMIT_WINDOW for req_time in ip_requests)
    )
    
    # Calculate semaphore status
    available_slots = processing_semaphore._value
    total_slots = MAX_CONCURRENT_PROCESSING
    
    # Get cache stats
    cache_stats = cache_service.get_cache_stats()
    
    # Get queue stats
    queue_stats = queue_service.get_queue_stats()
    
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "rate_limiting": {
            "active_ips": active_ips,
            "limit_per_ip": RATE_LIMIT_REQUESTS,
            "window_seconds": RATE_LIMIT_WINDOW
        },
        "processing_queue": {
            "available_slots": available_slots,
            "total_slots": total_slots,
            "utilization_percent": round(((total_slots - available_slots) / total_slots) * 100, 2)
        },
        "cache": cache_stats,
        "queue": queue_stats,
        "cloud_run": {
            "max_instances": 50,
            "concurrency_per_instance": 80,
            "max_concurrent_requests": 4000
        }
    }


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Check processing status for a specific job"""
    result = await queue_service.get_job_result(job_id)
    
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    
    return result


@app.get("/test-api")
async def test_api(req: Request):
    """Test the ScrapeCreators API connection"""
    try:
        # Test with a simple video info fetch (no video download)
        test_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"

        options = ScrapingOptions(
            get_transcript=False,  # Skip transcript for faster testing
            trim_response=True,
            max_retries=1,
            timeout=10,
        )

        info = await scraper.get_video_info(test_url, options)

        return {
            "status": "success",
            "message": "API key is working correctly",
            "test_video": {
                "title": info["metadata"]["title"][:100],
                "author": info["metadata"]["author"],
                "duration": info["metadata"]["duration_seconds"],
            },
        }

    except ValidationError as e:
        return {"status": "error", "type": "validation", "message": str(e)}
    except APIError as e:
        if e.status_code == 401:
            return {
                "status": "error",
                "type": "auth",
                "message": "API key is invalid or missing",
            }
        else:
            return {
                "status": "error",
                "type": "api",
                "message": str(e),
                "status_code": e.status_code,
            }
    except Exception as e:
        return {"status": "error", "type": "unexpected", "message": str(e)}


@app.delete("/cache/{url_hash}")
async def invalidate_cache_by_hash(url_hash: str):
    """Invalidate cache entry by URL hash (for debugging)"""
    # This is a debug endpoint - in production you might want to restrict access
    if environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        if cache_service.db:
            doc_ref = cache_service.cache_collection.document(url_hash)
            exists = doc_ref.get().exists
            if exists:
                doc_ref.delete()
                return {"deleted": 1, "cache_key": url_hash}
            else:
                return {"deleted": 0, "cache_key": url_hash, "message": "Document not found"}
        else:
            return {"error": "Cache service not available"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/cache/invalidate")
async def invalidate_cache_by_url(request: ProcessRequest):
    """Invalidate cache for a specific TikTok URL"""
    if environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    success = cache_service.invalidate_cache(request.url)
    return {
        "url": request.url,
        "invalidated": success,
        "cache_key": cache_service._generate_cache_key(request.url)
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
