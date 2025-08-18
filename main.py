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

# Import API routers
from src.api import health_router, process_router, admin_router
from src.services.config_validator import validate_required_env_vars, AppConfig
from src.services.appcheck_middleware import get_appcheck_service
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

# Include API routers
app.include_router(health_router)
app.include_router(process_router)
app.include_router(admin_router)

# Register error handlers
register_error_handlers(app)

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
    "total_requests": 0
}
appcheck_metrics_lock = threading.Lock()

def log_structured_metric(metric_data: dict):
    """Log structured data for Google Cloud Logging to parse as JSON"""
    from src.utils.logging import log_business_event
    
    # Use our structured logging for consistency
    log_business_event("appcheck_metric", metric_data)

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
    log_structured_metric({
        "event_type": "appcheck_metric",
        "metric": metric_type,
        "path": path,
        "app_id": app_id,
        "cumulative_verified": appcheck_metrics["verified_requests"],
        "cumulative_unverified": appcheck_metrics["unverified_requests"],
        "cumulative_invalid": appcheck_metrics["invalid_tokens"],
        "total_requests": appcheck_metrics["total_requests"]
    })

# Track active direct processing (shared state for routes)
active_direct_processing = 0
active_processing_lock = threading.Lock()
MAX_DIRECT_PROCESSING = config.processing.max_direct_processing

# Rate limiting configuration
RATE_LIMIT_REQUESTS = config.rate_limiting.requests_per_window
RATE_LIMIT_WINDOW = config.rate_limiting.window_seconds
rate_limit_store = defaultdict(list)

# Request queue management
MAX_CONCURRENT_PROCESSING = config.processing.max_concurrent_processing
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











if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
