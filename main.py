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

from src.services.tiktok_scraper import (
    TikTokScraper,
    ScrapingOptions,
    APIError,
    NetworkError,
    ValidationError,
)
from src.services.genai_service import GenAIService
from src.worker.video_processor import VideoProcessor

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Log environment info (without exposing secrets)
environment = os.getenv("ENVIRONMENT", "production")
project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
logger.info(f"Starting application - Environment: {environment}, Project: {project_id}")

# Verify required environment variables
required_vars = ["SCRAPECREATORS_API_KEY", "GOOGLE_CLOUD_PROJECT_ID"]
for var in required_vars:
    if not os.getenv(var):
        logger.error(f"Missing required environment variable: {var}")
        raise ValueError(f"Missing required environment variable: {var}")


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


class ProcessRequest(BaseModel):
    url: str


@app.post("/process")
async def process_video(request: ProcessRequest, req: Request):
    """Process a TikTok video and return workout JSON"""
    try:
        # Configure scraping options - transcript is now included by default
        options = ScrapingOptions(
            get_transcript=True,  # Transcript is now included in main response
            trim_response=True,
            max_retries=3,
            timeout=30,
        )

        # Scrape video with transcript in single request
        request_id = getattr(req.state, "request_id", "unknown")
        logger.info(f"Processing video - Request ID: {request_id}, URL: {request.url}")
        video_content, metadata, transcript = await scraper.scrape_tiktok_complete(
            request.url, options
        )

        if transcript:
            logger.info(f"Successfully got transcript: {len(transcript)} characters")
        else:
            logger.info("No transcript available for this video")

        # 3. Remove audio
        logger.info("Removing audio from video...")
        silent_video = await video_processor.remove_audio(video_content)

        # 4. Analyze with Gemini
        caption = metadata.description or metadata.caption

        # Handle case where transcript might be None
        if transcript is None:
            logger.warning(f"Processing video without transcript: {request.url}")
            # You can still proceed without transcript, or modify this based on your needs
        else:
            logger.info(
                f"Processing video with transcript ({len(transcript)} chars): " f"{request.url}"
            )

        logger.info("Analyzing video with Google Gen AI...")
        workout_json = genai_service.analyze_video_with_transcript(
            silent_video, transcript, caption
        )

        if not workout_json:
            raise HTTPException(status_code=422, detail="Could not extract workout information")

        logger.info(
            f"Successfully processed video - Request ID: {request_id}, " f"URL: {request.url}"
        )
        return workout_json

    except ValidationError as e:
        logger.error(
            f"Validation error - Request ID: {request_id}, URL: {request.url}, " f"Error: {str(e)}"
        )
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")
    except APIError as e:
        logger.error(
            f"API error - Request ID: {request_id}, URL: {request.url}, "
            f"Error: {str(e)}, Status: {e.status_code}"
        )
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="TikTok video not found or unavailable")
        elif e.status_code == 401:
            raise HTTPException(
                status_code=500, detail="API authentication failed - check your API key"
            )
        elif e.status_code == 429:
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded - please try again later"
            )
        else:
            raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except NetworkError as e:
        logger.error(
            f"Network error - Request ID: {request_id}, URL: {request.url}, " f"Error: {str(e)}"
        )
        raise HTTPException(status_code=503, detail=f"Network error: {str(e)}")
    except Exception as e:
        # Log the full error for debugging
        logger.exception(
            f"Unexpected error - Request ID: {request_id}, URL: {request.url}, " f"Error: {str(e)}"
        )

        error_message = str(e)
        # Handle 429 rate limit errors specifically
        if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Rate limit exceeded. The Google Gen AI service is currently "
                    "overloaded. Please try again in a few moments."
                ),
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint for container orchestration"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": environment,
        "version": app.version,
    }


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


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
