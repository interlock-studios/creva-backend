from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import os
import logging
import time
import json
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from collections import defaultdict
import threading
import asyncio
from google.cloud import monitoring_v3

# GenAI service pool cleanup not needed
from src.api.process import cleanup_processing_resources

# Import API routers
from src.api import health_router, process_router, admin_router
from src.api.search import router as search_router, video_router
from src.services.config_validator import validate_required_env_vars, AppConfig
from src.auth import get_appcheck_service
from src.utils.logging import StructuredLogger, RequestLoggingMiddleware
from src.utils.error_handlers import register_error_handlers

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = StructuredLogger(__name__)

# Validate configuration
validate_required_env_vars(["SCRAPECREATORS_API_KEY", "GOOGLE_CLOUD_PROJECT_ID"], "API")

# Get centralized configuration
config = AppConfig.from_env()
environment = config.environment
project_id = config.project_id
logger.info(f"Starting application - Environment: {environment}, Project: {project_id}")


# Application lifespan management with resource cleanup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup complete")
    logger.info(f"Environment: {environment}, Project: {project_id}")
    logger.info("Optimized multi-region GenAI service pool initialized")
    
    yield
    
    # Shutdown - cleanup resources
    logger.info("Application shutdown initiated")
    try:
        # Cleanup processing resources
        await cleanup_processing_resources()
        
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title="Creva - Creator Video Parser",
    version="3.0.0",
    description="Extract transcripts, hooks, and metadata from TikTok and Instagram videos for content creators",
    docs_url="/docs" if environment != "production" else None,
    redoc_url="/redoc" if environment != "production" else None,
    lifespan=lifespan,
)

# Include API routers
app.include_router(health_router)
app.include_router(process_router)
app.include_router(admin_router)
app.include_router(search_router)
app.include_router(video_router)

# Register error handlers
register_error_handlers(app)

# Enhanced Security Configuration
from src.middleware.security import (
    SecurityMiddleware, 
    SecurityHeadersMiddleware, 
    RequestSizeLimitMiddleware
)
from src.config.security import security_config

# Security middleware - Configure trusted hosts based on environment
# Temporarily disable host checking if environment variable is set
if not os.getenv("DISABLE_HOST_CHECK", "").lower() == "true":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=security_config.trusted_hosts)
else:
    logger.warning("Host checking disabled via DISABLE_HOST_CHECK environment variable")

# CORS middleware - Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.cors_origins,
    allow_credentials=False,  # Set to False when using wildcard origins
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=[
        "X-Firebase-AppCheck",
        "Content-Type", 
        "Authorization",
        "Accept",
        "Origin",
        "User-Agent",
        "X-Requested-With",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers",
    ],
)

# Add security headers
app.add_middleware(SecurityHeadersMiddleware)

# Add request size limits
app.add_middleware(
    RequestSizeLimitMiddleware, 
    max_size=security_config.request_limits["max_request_size"]
)

# App Check middleware - use centralized configuration
APPCHECK_REQUIRED = config.app_check.required
APPCHECK_SKIP_PATHS = config.app_check.skip_paths

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
            # Record unverified request metric with IP
            client_ip = request.headers.get("X-Forwarded-For", request.client.host)
            if "," in client_ip:
                client_ip = client_ip.split(",")[0].strip()
            record_appcheck_metric("unverified", request.url.path, ip=client_ip)

            if self.required:
                logger.warning(f"Missing App Check token for {request.url.path}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "App Check token required"},
                    headers={"WWW-Authenticate": "X-Firebase-AppCheck"},
                )
            else:
                logger.info(f"App Check token missing but not required for {request.url.path}")
                request.state.appcheck_verified = False
                return await call_next(request)

        # Verify the token (simplified for middleware)
        try:
            verification_result = self.appcheck_service.verify_token(appcheck_token)

            if verification_result and verification_result.get("valid"):
                # Record verified request metric with IP
                app_id = verification_result.get("app_id", "unknown")
                client_ip = request.headers.get("X-Forwarded-For", request.client.host)
                if "," in client_ip:
                    client_ip = client_ip.split(",")[0].strip()
                record_appcheck_metric("verified", request.url.path, app_id, client_ip)

                request.state.appcheck_verified = True
                request.state.appcheck_claims = verification_result
                logger.debug(f"App Check verified for app: {app_id}")
                return await call_next(request)
            else:
                # Record invalid token metric with IP
                client_ip = request.headers.get("X-Forwarded-For", request.client.host)
                if "," in client_ip:
                    client_ip = client_ip.split(",")[0].strip()
                record_appcheck_metric("invalid", request.url.path, ip=client_ip)

                request.state.appcheck_verified = False
                if self.required:
                    error_msg = (
                        verification_result.get("error", "Invalid App Check token")
                        if verification_result
                        else "Invalid App Check token"
                    )
                    logger.warning(f"Invalid App Check token for {request.url.path}: {error_msg}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": f"Invalid App Check token: {error_msg}"},
                        headers={"WWW-Authenticate": "X-Firebase-AppCheck"},
                    )
                else:
                    logger.info(f"Invalid App Check token but not required for {request.url.path}")
                    return await call_next(request)

        except Exception as e:
            logger.error(f"Error in App Check middleware: {str(e)}")
            if self.required:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "App Check verification service unavailable"},
                )
            else:
                request.state.appcheck_verified = False
                return await call_next(request)


app.add_middleware(
    AppCheckHTTPMiddleware, skip_paths=APPCHECK_SKIP_PATHS, required=APPCHECK_REQUIRED
)

# Add enhanced security middleware (includes rate limiting, threat detection)
security_config = {
    "skip_paths": APPCHECK_SKIP_PATHS,
    "environment": environment
}
app.add_middleware(SecurityMiddleware, config=security_config)

# Add structured logging middleware
app.add_middleware(RequestLoggingMiddleware)


# Error handlers are now registered via register_error_handlers()


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
    "total_requests": 0,
}
appcheck_metrics_lock = threading.Lock()


def log_structured_metric(metric_data: dict):
    """Log structured data for Google Cloud Logging to parse as JSON"""
    from src.utils.logging import log_business_event

    # Use our structured logging for consistency
    log_business_event("appcheck_metric", metric_data)


def record_appcheck_metric(metric_type: str, path: str = "", app_id: str = "", ip: str = ""):
    """Record App Check metrics for monitoring with enhanced security tracking"""
    global appcheck_metrics, performance_metrics
    
    with appcheck_metrics_lock:
        appcheck_metrics["total_requests"] += 1
        if metric_type == "verified":
            appcheck_metrics["verified_requests"] += 1
        elif metric_type == "unverified":
            appcheck_metrics["unverified_requests"] += 1
        elif metric_type == "invalid":
            appcheck_metrics["invalid_tokens"] += 1
    
    # Update performance metrics
    with metrics_lock:
        performance_metrics["total_requests"] += 1

    # Enhanced security logging with App Check readiness metrics
    severity = "info"
    readiness_score = 0
    
    if metric_type == "verified":
        severity = "info"
        readiness_score = 100  # Verified requests contribute positively
        logger.info(
            "App Check token verified",
            extra={
                "security_event": "appcheck_verified",
                "ip_address": ip,
                "path": path,
                "app_id": app_id,
                "severity": "info",
                "readiness_score": readiness_score,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    elif metric_type == "invalid":
        severity = "warning"
        readiness_score = -50  # Invalid tokens hurt readiness
        logger.warning(
            "Invalid App Check token detected",
            extra={
                "security_event": "invalid_appcheck_token",
                "ip_address": ip,
                "path": path,
                "app_id": app_id,
                "severity": "medium",
                "readiness_score": readiness_score,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    elif metric_type == "unverified":
        severity = "info"
        readiness_score = -10  # Unverified requests slightly hurt readiness
        logger.info(
            "Unverified App Check request",
            extra={
                "security_event": "appcheck_bypass_attempt",
                "ip_address": ip,
                "path": path,
                "severity": "low",
                "readiness_score": readiness_score,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    # Calculate App Check readiness percentage
    total_requests = appcheck_metrics["total_requests"]
    verified_requests = appcheck_metrics["verified_requests"]
    readiness_percentage = (verified_requests / total_requests * 100) if total_requests > 0 else 0
    
    # Determine readiness status
    if readiness_percentage >= 80:
        readiness_status = "READY"
    elif readiness_percentage >= 50:
        readiness_status = "CAUTION"
    else:
        readiness_status = "NOT_READY"
    
    # Log structured metrics for Cloud Logging
    log_structured_metric(
        {
            "event_type": "appcheck_metric",
            "metric": metric_type,
            "path": path,
            "app_id": app_id,
            "ip_address": ip,
            "severity": severity,
            "readiness_score": readiness_score,
            "readiness_percentage": readiness_percentage,
            "readiness_status": readiness_status,
            "cumulative_verified": appcheck_metrics["verified_requests"],
            "cumulative_unverified": appcheck_metrics["unverified_requests"],
            "cumulative_invalid": appcheck_metrics["invalid_tokens"],
            "total_requests": appcheck_metrics["total_requests"],
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Add region-specific health check
@app.get("/health/regions")
async def get_regional_health():
    """Get health status of all regions for load balancer routing"""
    try:
        from src.services.genai_service_pool import GenAIServicePool
        
        # Initialize pool to check health
        pool = GenAIServicePool()
        pool_size = pool.get_pool_size()
        current_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
        
        return {
            "status": "healthy" if pool_size > 0 else "unhealthy",
            "current_region": current_region,
            "pool_size": pool_size,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get regional health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Track active direct processing (shared state for routes) - increased capacity
active_direct_processing = 0
active_processing_lock = threading.Lock()
MAX_DIRECT_PROCESSING = min(config.processing.max_direct_processing, 20)  # Increased from 5 to 20

# Enhanced rate limiting configuration with higher limits for optimized performance
RATE_LIMIT_REQUESTS = min(config.rate_limiting.requests_per_window * 2, 50)  # Double the rate limit
RATE_LIMIT_WINDOW = config.rate_limiting.window_seconds

# Add performance monitoring endpoint
@app.get("/metrics/performance")
async def get_performance_metrics():
    """Get performance metrics for monitoring"""
    with metrics_lock:
        return {
            "performance_metrics": performance_metrics.copy(),
            "appcheck_metrics": appcheck_metrics.copy(),
            "processing_capacity": {
                "active_direct_processing": active_direct_processing,
                "max_direct_processing": MAX_DIRECT_PROCESSING,
                "max_concurrent_processing": MAX_CONCURRENT_PROCESSING,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

# Optimized request queue management with higher concurrency
MAX_CONCURRENT_PROCESSING = min(config.processing.max_concurrent_processing, 100)  # Cap at 100 for safety
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROCESSING)

# Performance monitoring
performance_metrics = {
    "total_requests": 0,
    "cache_hits": 0,
    "direct_processing": 0,
    "queue_processing": 0,
    "avg_response_time": 0.0,
}
metrics_lock = threading.Lock()


# Legacy rate limiting middleware removed - now handled by SecurityMiddleware
# The new SecurityMiddleware provides enhanced rate limiting with:
# - Per-user limits using App Check app_id
# - Per-IP limits as fallback
# - Different limits for different endpoints
# - Threat detection and automatic IP blocking


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    
    # Optimized uvicorn configuration for high performance
    uvicorn_config = {
        "host": "0.0.0.0",
        "port": port,
        "workers": 1,  # Single worker for async app
        "loop": "asyncio",
        "http": "httptools",
        "lifespan": "on",
        "access_log": environment != "production",
        "server_header": False,
        "date_header": False,
    }
    
    logger.info(f"Starting optimized server on port {port}")
    logger.info(f"Max concurrent processing: {MAX_CONCURRENT_PROCESSING}")
    
    uvicorn.run(app, **uvicorn_config)
