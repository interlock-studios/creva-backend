from fastapi import FastAPI, HTTPException, Request, Depends
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
import threading
from google.cloud import monitoring_v3

from src.services.tiktok_scraper import (
    TikTokScraper,
    ScrapingOptions as TikTokScrapingOptions,
    APIError as TikTokAPIError,
    NetworkError as TikTokNetworkError,
    ValidationError as TikTokValidationError,
)
from src.services.instagram_scraper import (
    InstagramScraper,
    ScrapingOptions as InstagramScrapingOptions,
    APIError as InstagramAPIError,
    NetworkError as InstagramNetworkError,
    ValidationError as InstagramValidationError,
)
from src.services.url_router import URLRouter
from src.services.genai_service import GenAIService
from src.services.cache_service import CacheService
from src.services.queue_service import QueueService
from src.worker.video_processor import VideoProcessor
from src.services.config_validator import validate_required_env_vars, get_config_with_defaults
from src.services.appcheck_middleware import (
    AppCheckMiddleware, 
    verify_appcheck_token, 
    optional_appcheck_token,
    get_appcheck_service,
    get_appcheck_claims,
    is_appcheck_verified
)

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
    title="Social Media Workout Parser - AI Powered",
    version="1.0.0",
    description="Parse workout videos from TikTok and Instagram using AI",
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

# App Check middleware - configure based on your requirements
# Set required=False for development, True for production
APPCHECK_REQUIRED = os.getenv("APPCHECK_REQUIRED", "false").lower() == "true"
APPCHECK_SKIP_PATHS = ["/health", "/docs", "/redoc", "/openapi.json", "/test-api"]

# Add App Check middleware
# Note: Using BaseHTTPMiddleware instead of custom class for better FastAPI compatibility
from starlette.middleware.base import BaseHTTPMiddleware

class AppCheckHTTPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, skip_paths: list = None, required: bool = True):
        super().__init__(app)
        self.skip_paths = skip_paths or ["/health", "/docs", "/redoc", "/openapi.json"]
        self.required = required
        self.appcheck_service = get_appcheck_service()
    
    async def dispatch(self, request: Request, call_next):
        # Skip verification for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Get App Check token from header
        appcheck_token = request.headers.get("X-Firebase-AppCheck")
        
        if not appcheck_token:
            # Record unverified request metric
            record_appcheck_metric("unverified", request.url.path)
            
            if self.required:
                logger.warning(f"Missing App Check token for {request.url.path}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "App Check token required"},
                    headers={"WWW-Authenticate": "X-Firebase-AppCheck"}
                )
            else:
                logger.info(f"App Check token missing but not required for {request.url.path}")
                request.state.appcheck_verified = False
                return await call_next(request)
        
        # Verify the token (simplified for middleware)
        try:
            verification_result = self.appcheck_service.verify_token(appcheck_token)
            
            if verification_result and verification_result.get("valid"):
                # Record verified request metric
                app_id = verification_result.get('app_id', 'unknown')
                record_appcheck_metric("verified", request.url.path, app_id)
                
                request.state.appcheck_verified = True
                request.state.appcheck_claims = verification_result
                logger.debug(f"App Check verified for app: {app_id}")
                return await call_next(request)
            else:
                # Record invalid token metric
                record_appcheck_metric("invalid", request.url.path)
                
                request.state.appcheck_verified = False
                if self.required:
                    error_msg = verification_result.get("error", "Invalid App Check token") if verification_result else "Invalid App Check token"
                    logger.warning(f"Invalid App Check token for {request.url.path}: {error_msg}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": f"Invalid App Check token: {error_msg}"},
                        headers={"WWW-Authenticate": "X-Firebase-AppCheck"}
                    )
                else:
                    logger.info(f"Invalid App Check token but not required for {request.url.path}")
                    return await call_next(request)
                    
        except Exception as e:
            logger.error(f"Error in App Check middleware: {str(e)}")
            if self.required:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "App Check verification service unavailable"}
                )
            else:
                request.state.appcheck_verified = False
                return await call_next(request)

app.add_middleware(
    AppCheckHTTPMiddleware,
    skip_paths=APPCHECK_SKIP_PATHS,
    required=APPCHECK_REQUIRED
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


tiktok_scraper = TikTokScraper()
instagram_scraper = InstagramScraper()
url_router = URLRouter()
genai_service = GenAIService()
video_processor = VideoProcessor()
cache_service = CacheService()
queue_service = QueueService()
appcheck_service = get_appcheck_service()

# Initialize Google Cloud Monitoring
try:
    monitoring_client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"
    logger.info("Google Cloud Monitoring initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize Google Cloud Monitoring: {e}")
    monitoring_client = None
    project_name = None

# App Check metrics tracking
appcheck_metrics = {
    "verified_requests": 0,
    "unverified_requests": 0,
    "invalid_tokens": 0,
    "total_requests": 0
}
appcheck_metrics_lock = threading.Lock()

def record_appcheck_metric(metric_type: str, path: str = "", app_id: str = ""):
    """Record App Check metrics for monitoring"""
    global appcheck_metrics
    with appcheck_metrics_lock:
        appcheck_metrics["total_requests"] += 1
        if metric_type == "verified":
            appcheck_metrics["verified_requests"] += 1
        elif metric_type == "unverified":
            appcheck_metrics["unverified_requests"] += 1
        elif metric_type == "invalid":
            appcheck_metrics["invalid_tokens"] += 1
    
    # Log structured metrics for Cloud Logging
    logger.info(json.dumps({
        "event_type": "appcheck_metric",
        "metric": metric_type,
        "path": path,
        "app_id": app_id,
        "timestamp": datetime.utcnow().isoformat(),
        "cumulative_verified": appcheck_metrics["verified_requests"],
        "cumulative_unverified": appcheck_metrics["unverified_requests"],
        "cumulative_invalid": appcheck_metrics["invalid_tokens"],
        "total_requests": appcheck_metrics["total_requests"]
    }))

# Track active direct processing
active_direct_processing = 0
active_processing_lock = threading.Lock()
MAX_DIRECT_PROCESSING = 5  # Process directly if under this limit


class ProcessRequest(BaseModel):
    url: str


async def process_video_direct(url: str, request_id: str):
    """Process video directly (not through queue)"""
    global active_direct_processing

    try:
        # Increment active processing count
        with active_processing_lock:
            active_direct_processing += 1

        logger.info(
            f"Direct processing started - Request ID: {request_id}, Active: {active_direct_processing}"
        )

        # Validate URL and detect platform
        is_valid, error_msg, platform = url_router.validate_url(url)
        if not is_valid:
            raise ValueError(error_msg)

        logger.info(f"Processing {platform} video - Request ID: {request_id}")

        # 1. Download and process video using video processor (handles both platforms)
        video_content, metadata = await video_processor.download_video(url)

        # Check if this is a slideshow
        is_slideshow = metadata.get("is_slideshow", False)
        caption = metadata.get("caption", "") or metadata.get("description", "")
        transcript = metadata.get("transcript_text")

        if is_slideshow:
            # Handle slideshow content - get all images and analyze directly
            logger.info(f"Processing slideshow with {metadata.get('image_count', 0)} images - Request ID: {request_id}")
            
            if platform == "tiktok":
                # Get all slideshow images for AI analysis
                slideshow_images, slideshow_metadata, slideshow_transcript = (
                    await tiktok_scraper.scrape_tiktok_slideshow(url)
                )
                
                # Use slideshow-specific transcript if available
                if slideshow_transcript:
                    transcript = slideshow_transcript
                
                # Analyze slideshow with Gemini (use single service for direct processing)
                workout_json = genai_service.analyze_slideshow_with_transcript(
                    slideshow_images, transcript, caption
                )
            else:
                # Instagram slideshows not yet supported
                raise Exception("Instagram slideshows not yet supported")
        else:
            # Handle regular video content
            logger.info(f"Processing regular video - Request ID: {request_id}")
            
            # 2. Remove audio
            silent_video = await video_processor.remove_audio(video_content)

            # 3. Analyze with Gemini
            workout_json = genai_service.analyze_video_with_transcript(
                silent_video, transcript, caption
            )

        if not workout_json:
            raise Exception("Could not extract workout information from video")

        # 4. Cache the result
        cache_service.cache_workout(url, workout_json)

        logger.info(f"Direct processing completed - Request ID: {request_id}")
        return workout_json

    finally:
        # Always decrement counter
        with active_processing_lock:
            active_direct_processing -= 1


@app.post("/process")
async def process_video(
    request: ProcessRequest, 
    req: Request,
    appcheck_claims: dict = Depends(optional_appcheck_token)
):
    """Hybrid processing: try direct first, fall back to queue if busy"""

    request_id = getattr(req.state, "request_id", "unknown")
    
    # Log App Check status
    if appcheck_claims:
        logger.info(f"Request verified with App Check - App ID: {appcheck_claims.get('app_id')} - Request ID: {request_id}")
    elif APPCHECK_REQUIRED:
        logger.warning(f"App Check required but not provided - Request ID: {request_id}")
    else:
        logger.debug(f"App Check not provided (optional) - Request ID: {request_id}")

    # Check cache first
    cached_workout = cache_service.get_cached_workout(request.url)
    if cached_workout:
        logger.info(f"Returning cached result - Request ID: {request_id}, URL: {request.url}")
        return cached_workout

    # Check if already in queue
    existing_job = await queue_service.get_job_by_url(request.url, status="pending")
    if existing_job:
        logger.info(
            f"Video already queued - Request ID: {request_id}, Job ID: {existing_job['job_id']}"
        )
        return {
            "status": "queued",
            "job_id": existing_job["job_id"],
            "message": "Video already queued for processing",
            "check_url": f"/status/{existing_job['job_id']}",
        }

    processing_job = await queue_service.get_job_by_url(request.url, status="processing")
    if processing_job:
        logger.info(
            f"Video already processing - Request ID: {request_id}, Job ID: {processing_job['job_id']}"
        )
        return {
            "status": "processing",
            "job_id": processing_job["job_id"],
            "message": "Video is currently being processed",
            "check_url": f"/status/{processing_job['job_id']}",
        }

    # Try direct processing if we have capacity
    with active_processing_lock:
        can_process_direct = active_direct_processing < MAX_DIRECT_PROCESSING

    if can_process_direct:
        try:
            # Try to process directly with timeout
            result = await asyncio.wait_for(
                process_video_direct(request.url, request_id),
                timeout=30.0,  # 30 second timeout for direct processing
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(
                f"Direct processing timeout - Request ID: {request_id}, falling back to queue"
            )
        except Exception as e:
            logger.error(
                f"Direct processing failed - Request ID: {request_id}, Error: {str(e)}, falling back to queue"
            )
    else:
        logger.info(
            f"At capacity ({active_direct_processing}/{MAX_DIRECT_PROCESSING}) - Request ID: {request_id}, using queue"
        )

    # Fall back to queue
    try:
        job_id = await queue_service.enqueue_video(request.url, request_id, priority="normal")

        logger.info(f"Video queued for processing - Request ID: {request_id}, Job ID: {job_id}")

        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Video queued for processing. Check status with job_id.",
            "check_url": f"/status/{job_id}",
        }

    except Exception as e:
        logger.error(f"Failed to queue video - Request ID: {request_id}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")


# Rate limiting configuration
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
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
        req_time
        for req_time in rate_limit_store[client_ip]
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
                "retry_after": RATE_LIMIT_WINDOW,
            },
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
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
        "services": {},
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

    # Check App Check service
    try:
        app_check_healthy = appcheck_service.is_healthy()
        health_status["services"]["app_check"] = "healthy" if app_check_healthy else "unhealthy"
        if not app_check_healthy:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["app_check"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


@app.get("/status")
async def status():
    """Status endpoint showing current system load and queue status"""
    current_time = time.time()

    # Calculate active rate limit entries
    active_ips = sum(
        1
        for ip_requests in rate_limit_store.values()
        if any(current_time - req_time < RATE_LIMIT_WINDOW for req_time in ip_requests)
    )

    # Calculate semaphore status
    available_slots = processing_semaphore._value
    total_slots = MAX_CONCURRENT_PROCESSING

    # Get cache stats
    cache_stats = cache_service.get_cache_stats()

    # Get queue stats
    queue_stats = queue_service.get_queue_stats()

    # Get App Check stats
    appcheck_stats = appcheck_service.get_stats()

    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "hybrid_mode": {
            "enabled": True,
            "direct_processing": {
                "active": active_direct_processing,
                "max": MAX_DIRECT_PROCESSING,
                "available": MAX_DIRECT_PROCESSING - active_direct_processing,
            },
        },
        "rate_limiting": {
            "active_ips": active_ips,
            "limit_per_ip": RATE_LIMIT_REQUESTS,
            "window_seconds": RATE_LIMIT_WINDOW,
        },
        "processing_queue": {
            "available_slots": available_slots,
            "total_slots": total_slots,
            "utilization_percent": round(((total_slots - available_slots) / total_slots) * 100, 2),
        },
        "cache": cache_stats,
        "queue": queue_stats,
        "app_check": {
            "required": APPCHECK_REQUIRED,
            "stats": appcheck_stats,
            "metrics": appcheck_metrics.copy()  # Current session metrics
        },
        "cloud_run": {
            "max_instances": 50,
            "concurrency_per_instance": 80,
            "max_concurrent_requests": 4000,
        },
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
    """Test the ScrapeCreators API connection for both TikTok and Instagram"""
    results = {}

    # Test TikTok
    try:
        test_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"
        options = TikTokScrapingOptions(
            get_transcript=False,
            trim_response=True,
            max_retries=1,
            timeout=10,
        )
        info = await tiktok_scraper.get_video_info(test_url, options)
        results["tiktok"] = {
            "status": "success",
            "message": "TikTok API working correctly",
            "test_video": {
                "title": info["metadata"]["title"][:100],
                "author": info["metadata"]["author"],
                "duration": info["metadata"]["duration_seconds"],
            },
        }
    except (TikTokValidationError, TikTokAPIError, TikTokNetworkError) as e:
        results["tiktok"] = {"status": "error", "message": str(e), "type": type(e).__name__}
    except Exception as e:
        results["tiktok"] = {"status": "error", "type": "unexpected", "message": str(e)}

    # Test Instagram
    try:
        test_url = "https://www.instagram.com/reel/DDXT72CSnUJ/"
        options = InstagramScrapingOptions(
            trim_response=True,
            max_retries=1,
            timeout=10,
        )
        info = await instagram_scraper.get_video_info(test_url, options)
        results["instagram"] = {
            "status": "success",
            "message": "Instagram API working correctly",
            "test_video": {
                "title": info["metadata"]["title"][:100],
                "author": info["metadata"]["author"],
                "duration": info["metadata"]["duration_seconds"],
            },
        }
    except (InstagramValidationError, InstagramAPIError, InstagramNetworkError) as e:
        results["instagram"] = {"status": "error", "message": str(e), "type": type(e).__name__}
    except Exception as e:
        results["instagram"] = {"status": "error", "type": "unexpected", "message": str(e)}

    # Overall status
    overall_status = (
        "success" if all(r["status"] == "success" for r in results.values()) else "partial"
    )

    return {
        "status": overall_status,
        "message": "API connection test results",
        "platforms": results,
    }


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
        "cache_key": cache_service._generate_cache_key(request.url),
    }


@app.post("/test-appcheck")
async def test_appcheck(
    req: Request,
    appcheck_claims: dict = Depends(verify_appcheck_token)
):
    """Test endpoint that requires valid App Check token"""
    request_id = getattr(req.state, "request_id", "unknown")
    
    return {
        "status": "success",
        "message": "App Check token verified successfully",
        "request_id": request_id,
        "app_check_claims": {
            "app_id": appcheck_claims.get("app_id"),
            "iss": appcheck_claims.get("iss"),
            "aud": appcheck_claims.get("aud"),
            "verified_at": appcheck_claims.get("verified_at")
        }
    }


@app.get("/appcheck-status")
async def appcheck_status():
    """Get App Check service status and configuration"""
    if environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "app_check_enabled": True,
        "app_check_required": APPCHECK_REQUIRED,
        "skip_paths": APPCHECK_SKIP_PATHS,
        "service_stats": appcheck_service.get_stats(),
        "service_healthy": appcheck_service.is_healthy()
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
