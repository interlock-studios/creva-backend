from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import os
import asyncio
from contextlib import asynccontextmanager

from src.api.production_routes import router
from src.utils.logging import setup_logging
from src.services.whisper_service import WhisperService

# Global Whisper service for preloading
whisper_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global whisper_service
    
    setup_logging()
    logger = structlog.get_logger()
    
    logger.info(
        "TikTok Parser API starting up",
        version="2.0.0",
        environment=os.getenv("ENVIRONMENT", "development")
    )
    
    # Preload Whisper model for faster first requests
    try:
        logger.info("Preloading Whisper model...")
        whisper_service = WhisperService(
            model_size=os.getenv("WHISPER_MODEL_SIZE", "large-v3"),
            device=os.getenv("WHISPER_DEVICE", "auto")
        )
        await whisper_service.load_model()
        logger.info("Whisper model loaded successfully")
    except Exception as e:
        logger.error("Failed to preload Whisper model", error=str(e))
        # Continue startup - model will be lazy loaded
    
    yield
    
    logger.info("TikTok Parser API shutting down")


app = FastAPI(
    title="Production TikTok Parser API",
    description="""
    Production-grade TikTok video parser that extracts:
    - Video metadata (caption, author, stats)
    - Speech-to-text transcription with timestamps (OpenAI Whisper)
    - OCR text from video frames (Google Cloud Vision)
    
    Optimized for cost, speed, and reliability.
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)

# Include production routes
app.include_router(router, prefix="/api/v2")

# Legacy routes support (backward compatibility)
from src.api.routes import router as legacy_router
app.include_router(legacy_router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    logger = structlog.get_logger()
    
    if exc.status_code >= 500:
        logger.error(
            "HTTP error", 
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            method=request.method
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger = structlog.get_logger()
    
    logger.error(
        "Unhandled exception", 
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "path": request.url.path
        }
    )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "TikTok Parser API",
        "version": "2.0.0",
        "description": "Production-grade TikTok video parser with STT and OCR",
        "endpoints": {
            "v2": "/api/v2/docs",
            "v1": "/api/v1/health",
            "health": "/api/v2/health",
            "metrics": "/api/v2/metrics"
        },
        "features": [
            "OpenAI Whisper STT with GPU acceleration",
            "Google Cloud Vision OCR",
            "Comprehensive TikTok metadata extraction",
            "Cost-optimized processing pipeline",
            "Real-time progress tracking",
            "Webhook notifications"
        ]
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Handle favicon requests"""
    return JSONResponse(status_code=204, content=None)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )