"""
Video processing endpoints
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Union
import asyncio
import time
import os
import logging
import base64
from dotenv import load_dotenv

# Load environment variables before importing services
load_dotenv()

from src.utils.logging import StructuredLogger, set_request_context
from src.models.requests import ProcessRequest
from src.models.responses import RelationshipContent, QueuedResponse
from src.services.cache_service import CacheService
from src.services.queue_service import QueueService
from src.services.genai_service import GenAIService
from src.worker.video_processor import VideoProcessor
from src.auth import optional_appcheck_token
from src.exceptions import NotFoundError, ProcessingError

logger = StructuredLogger(__name__)
router = APIRouter(prefix="", tags=["processing"])

# Initialize services
cache_service = CacheService()
queue_service = QueueService()
genai_service = GenAIService()
video_processor = VideoProcessor()

# Configuration
MAX_DIRECT_PROCESSING = int(os.getenv("MAX_DIRECT_PROCESSING", "15"))
active_direct_processing = 0


async def process_video_direct(url: str, request_id: str, localization: str = None) -> dict:
    """Process video directly (not through queue)"""
    global active_direct_processing

    try:
        # Increment active processing count
        active_direct_processing += 1

        logger.info(
            "Direct processing started",
            active_processing=active_direct_processing,
            max_processing=MAX_DIRECT_PROCESSING,
        )

        # 1. Download and process video using video processor
        video_content, metadata = await video_processor.download_video(url)

        # Check if this is a slideshow
        is_slideshow = metadata.get("is_slideshow", False)
        caption = metadata.get("caption", "") or metadata.get("description", "")
        transcript = metadata.get("transcript_text")
        extracted_image_base64 = None

        if is_slideshow:
            # Handle slideshow content
            logger.info(
                f"Processing slideshow with {metadata.get('image_count', 0)} images - Request ID: {request_id}"
            )

            # For TikTok slideshows, get all images and analyze directly
            platform = video_processor.url_router.detect_platform(url)
            if platform == "tiktok":
                slideshow_images, slideshow_metadata, slideshow_transcript = (
                    await video_processor.tiktok_scraper.scrape_tiktok_slideshow(url)
                )

                if slideshow_transcript:
                    transcript = slideshow_transcript

                # Extract first image from slideshow
                if slideshow_images:
                    try:
                        logger.info(
                            f"Attempting to extract first slideshow image - Request ID: {request_id}, Image count: {len(slideshow_images)}"
                        )
                        first_image = await video_processor.extract_image_from_slideshow(
                            slideshow_images
                        )
                        extracted_image_base64 = f"data:image/jpeg;base64,{base64.b64encode(first_image).decode('utf-8')}"
                        logger.info(
                            f"Successfully extracted first slideshow image - Request ID: {request_id}, Image size: {len(first_image)} bytes"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to extract slideshow image - Request ID: {request_id}, Error: {e}",
                            exc_info=True,
                        )

                # Analyze slideshow with Gemini
                content_json = await genai_service.analyze_slideshow_with_transcript(
                    slideshow_images, transcript, caption, localization
                )
            else:
                raise Exception("Instagram slideshows not yet supported")
        else:
            # Handle regular video content
            logger.info(f"Processing regular video - Request ID: {request_id}")

            # Extract first frame from video
            try:
                logger.info(
                    f"Attempting to extract first frame - Request ID: {request_id}, Video size: {len(video_content)} bytes"
                )
                first_frame = await video_processor.extract_first_frame(video_content)
                extracted_image_base64 = (
                    f"data:image/jpeg;base64,{base64.b64encode(first_frame).decode('utf-8')}"
                )
                logger.info(
                    f"Successfully extracted first frame - Request ID: {request_id}, Frame size: {len(first_frame)} bytes"
                )
            except Exception as e:
                logger.error(
                    f"Failed to extract video frame - Request ID: {request_id}, Error: {e}",
                    exc_info=True,
                )

            # Analyze with Gemini (no audio removal needed)
            content_json = await genai_service.analyze_video_with_transcript(
                video_content, transcript, caption, localization
            )

        if not content_json:
            raise ProcessingError(
                message="Could not extract content information from video",
                operation="genai_analysis",
            )

        # Log what Gemini returned for the image field
        logger.info(
            f"Gemini returned image field: {content_json.get('image', 'NOT_SET')} - Request ID: {request_id}"
        )

        # Override the image field with the extracted frame/image if available
        if extracted_image_base64:
            content_json["image"] = extracted_image_base64
            logger.info(
                f"Added extracted image to response - Request ID: {request_id}, Image data length: {len(extracted_image_base64)}"
            )
        else:
            logger.warning(f"No extracted image available to add - Request ID: {request_id}")

        # Log final image field value
        logger.info(
            f"Final image field value (first 100 chars): {str(content_json.get('image', 'NULL'))[:100]} - Request ID: {request_id}"
        )

        # Cache the result
        await cache_service.cache_workout(url, content_json, localization=localization)

        logger.info(f"Direct processing completed - Request ID: {request_id}")
        return content_json

    finally:
        # Always decrement counter
        active_direct_processing -= 1


@router.post("/process", response_model=Union[RelationshipContent, QueuedResponse])
async def process_video(
    request: ProcessRequest, req: Request, appcheck_claims: dict = Depends(optional_appcheck_token)
) -> Union[RelationshipContent, QueuedResponse]:
    """Hybrid processing: try direct first, fall back to queue if busy"""

    request_id = getattr(req.state, "request_id", "unknown")

    # Log App Check status
    appcheck_required = os.getenv("APPCHECK_REQUIRED", "false").lower() == "true"
    if appcheck_claims:
        logger.info(
            f"Request verified with App Check - App ID: {appcheck_claims.get('app_id')} - Request ID: {request_id}"
        )
    elif appcheck_required:
        logger.warning(f"App Check required but not provided - Request ID: {request_id}")
    else:
        logger.debug(f"App Check not provided (optional) - Request ID: {request_id}")

    # Check cache first
    cached_workout = await cache_service.get_cached_workout(request.url, request.localization)
    if cached_workout:
        logger.info(f"Returning cached result - Request ID: {request_id}, URL: {request.url}")
        return RelationshipContent(**cached_workout)

    # Check if already in queue (with localization)
    existing_job = await queue_service.get_job_by_url(request.url, status="pending", localization=request.localization)
    if existing_job:
        logger.info(
            f"Video already queued - Request ID: {request_id}, Job ID: {existing_job['job_id']}"
        )
        return QueuedResponse(
            status="queued",
            job_id=existing_job["job_id"],
            message="Video already queued for processing",
            check_url=f"/status/{existing_job['job_id']}",
        )

    processing_job = await queue_service.get_job_by_url(request.url, status="processing", localization=request.localization)
    if processing_job:
        logger.info(
            f"Video already processing - Request ID: {request_id}, Job ID: {processing_job['job_id']}"
        )
        return QueuedResponse(
            status="processing",
            job_id=processing_job["job_id"],
            message="Video is currently being processed",
            check_url=f"/status/{processing_job['job_id']}",
        )

    # Try direct processing if we have capacity
    can_process_direct = active_direct_processing < MAX_DIRECT_PROCESSING

    if can_process_direct:
        try:
            # Try to process directly with timeout
            result = await asyncio.wait_for(
                process_video_direct(request.url, request_id, request.localization),
                timeout=30.0,  # 30 second timeout for direct processing
            )
            return RelationshipContent(**result)
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
        job_id = await queue_service.enqueue_video(
            request.url, request_id, priority="normal", localization=request.localization
        )

        logger.info(f"Video queued for processing - Request ID: {request_id}, Job ID: {job_id}")

        return QueuedResponse(
            status="queued",
            job_id=job_id,
            message="Video queued for processing. Check status with job_id.",
            check_url=f"/status/{job_id}",
        )

    except Exception as e:
        logger.error(f"Failed to queue video - Request ID: {request_id}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Check processing status for a specific job"""
    result = await queue_service.get_job_result(job_id)

    if result.get("status") == "not_found":
        raise NotFoundError(
            message=f"Job not found: {job_id}", resource_type="job", resource_id=job_id
        )

    return result


# Cleanup function for graceful shutdown
async def cleanup_processing_resources():
    """Cleanup processing resources on shutdown"""
    try:
        global executor, geoip_db
        
        if 'executor' in globals() and executor:
            executor.shutdown(wait=True)
        
        if 'geoip_db' in globals() and geoip_db:
            geoip_db.close()
            
        logger.info("Processing resources cleaned up")
    except Exception as e:
        logger.error(f"Error during processing cleanup: {e}")
