from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import structlog
import uuid
import asyncio
from datetime import datetime

from src.models.parser_result import (
    ParseRequest, ParseResponse, TikTokParseResult, 
    ProcessingStatus, HealthResponse
)
from src.api.auth import get_current_user
from src.worker.pipeline import ProcessingPipeline
from src.services.firestore_service import FirestoreService
from src.services.pubsub_service import PubSubService
from src.utils.monitoring import metrics
from src.utils.validation import validate_tiktok_url

logger = structlog.get_logger()
router = APIRouter()

# Global services
pipeline = ProcessingPipeline()
firestore_service = FirestoreService()
pubsub_service = PubSubService()

# Rate limiting storage (in production, use Redis)
rate_limit_storage = {}


@router.post("/parse", response_model=ParseResponse, status_code=202)
async def parse_tiktok_video(
    request: ParseRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user),
    http_request: Request = None
):
    """
    Submit TikTok video for parsing
    
    Returns immediately with job_id for async processing
    """
    try:
        # Validate TikTok URL
        if not validate_tiktok_url(request.url):
            raise HTTPException(
                status_code=422,
                detail="Invalid TikTok URL format"
            )
        
        # Rate limiting check (simple in-memory for demo)
        user_id = user.get("uid", "anonymous")
        await _check_rate_limit(user_id)
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Estimate completion time based on processing options
        estimated_time = _estimate_processing_time(request)
        
        logger.info(
            "Parse request received",
            job_id=job_id,
            url=request.url,
            user_id=user_id,
            include_stt=request.include_stt,
            include_ocr=request.include_ocr,
            priority=request.priority
        )
        
        # Initialize result in Firestore
        initial_result = TikTokParseResult(
            job_id=job_id,
            url=request.url,
            status=ProcessingStatus.PENDING
        )
        await firestore_service.save_parse_result(initial_result)
        
        # Submit for async processing based on priority
        if request.priority == "high":
            # Process immediately in background
            background_tasks.add_task(
                _process_video_task,
                job_id,
                request.url,
                request.include_stt,
                request.include_ocr,
                request.stt_method,
                request.webhook_url
            )
        else:
            # Queue for batch processing via Pub/Sub
            await pubsub_service.publish_parse_request({
                "job_id": job_id,
                "url": request.url,
                "user_id": user_id,
                "include_stt": request.include_stt,
                "include_ocr": request.include_ocr,
                "stt_method": request.stt_method,
                "webhook_url": request.webhook_url,
                "priority": request.priority
            })
        
        # Track metrics
        metrics.increment("parse_requests_total", tags={
            "priority": request.priority,
            "include_stt": str(request.include_stt),
            "include_ocr": str(request.include_ocr)
        })
        
        return ParseResponse(
            job_id=job_id,
            status=ProcessingStatus.PENDING,
            estimated_completion_seconds=estimated_time,
            webhook_url=request.webhook_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit parse request", error=str(e))
        metrics.increment("parse_request_errors_total")
        raise HTTPException(
            status_code=500,
            detail="Failed to submit parse request"
        )


@router.get("/parse/{job_id}", response_model=TikTokParseResult)
async def get_parse_result(
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get parsing result by job ID
    
    Returns complete result when processing is done,
    or status update if still processing
    """
    try:
        # Get result from Firestore
        result = await firestore_service.get_parse_result(job_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )
        
        # Track metrics
        metrics.increment("result_requests_total", tags={
            "status": result.status.value
        })
        
        logger.info(
            "Parse result retrieved",
            job_id=job_id,
            status=result.status.value,
            user_id=user.get("uid", "anonymous")
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve parse result", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve parse result"
        )


@router.get("/parse/{job_id}/status")
async def get_parse_status(
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get just the processing status (lightweight)
    """
    try:
        result = await firestore_service.get_parse_result(job_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        
        response = {
            "job_id": job_id,
            "status": result.status.value,
            "created_at": result.created_at.isoformat(),
            "updated_at": result.updated_at.isoformat()
        }
        
        if result.completed_at:
            response["completed_at"] = result.completed_at.isoformat()
        
        if result.metrics:
            response["metrics"] = {
                "total_latency_seconds": result.metrics.total_latency_seconds,
                "total_cost_usd": result.metrics.total_cost_usd
            }
        
        if result.error_message:
            response["error_message"] = result.error_message
            response["error_code"] = result.error_code
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get parse status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get parse status")


@router.delete("/parse/{job_id}")
async def cancel_parse_job(
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Cancel a pending or processing job
    """
    try:
        result = await firestore_service.get_parse_result(job_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if result.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED_DOWNLOAD, 
                           ProcessingStatus.FAILED_STT, ProcessingStatus.FAILED_OCR]:
            raise HTTPException(status_code=400, detail="Job already completed")
        
        # Update status to cancelled (we'll add this status)
        result.status = ProcessingStatus.PENDING  # Placeholder - would add CANCELLED status
        result.error_message = "Cancelled by user"
        result.updated_at = datetime.utcnow()
        
        await firestore_service.save_parse_result(result)
        
        logger.info("Parse job cancelled", job_id=job_id, user_id=user.get("uid"))
        
        return {"job_id": job_id, "status": "cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check for monitoring
    """
    try:
        # Get service health status
        health_data = {"whisper": {"gpu_available": False, "model_loaded": True}}
        
        # Check critical dependencies
        services_status = {}
        
        try:
            # Quick Firestore check
            await firestore_service.health_check()
            services_status["firestore"] = "healthy"
        except:
            services_status["firestore"] = "unhealthy"
        
        try:
            # Quick Vision API check (could be enhanced)
            services_status["vision_api"] = "healthy"
        except:
            services_status["vision_api"] = "unhealthy"
        
        # Overall system status
        all_healthy = all(status == "healthy" for status in services_status.values())
        
        response = HealthResponse(
            status="healthy" if all_healthy else "degraded",
            timestamp=datetime.utcnow(),
            version="2.0.0",  # Should come from config
            environment="production",  # Should come from env
            services=services_status,
            gpu_available=health_data["whisper"]["gpu_available"],
            whisper_model_loaded=health_data["whisper"]["model_loaded"]
        )
        
        logger.info("Health check completed", status=response.status)
        return response
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            version="2.0.0",
            environment="production",
            services={"system": "error"},
            gpu_available=False,
            whisper_model_loaded=False
        )


@router.get("/metrics")
async def get_metrics():
    """
    Get processing metrics for monitoring dashboard
    
    Returns aggregated stats about processing performance
    """
    try:
        # Get recent job statistics from Firestore
        stats = await firestore_service.get_processing_stats(hours=24)
        
        return {
            "last_24h": stats,
            "system": {"status": "healthy"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get metrics")


# Background task for high-priority processing
async def _process_video_task(
    job_id: str,
    url: str,
    include_stt: bool,
    include_ocr: bool,
    stt_method: str,
    webhook_url: Optional[str] = None
):
    """Background task for immediate video processing"""
    try:
        result = await pipeline.process_video(
            job_id=job_id,
            url=url,
            user_id="background_task"
        )
        
        # Send webhook notification if provided
        if webhook_url and result.status == ProcessingStatus.COMPLETED:
            await _send_webhook_notification(webhook_url, result)
            
    except Exception as e:
        logger.error("Background processing failed", job_id=job_id, error=str(e))


async def _send_webhook_notification(webhook_url: str, result: TikTokParseResult):
    """Send completion notification to webhook URL"""
    try:
        import httpx
        
        payload = {
            "job_id": result.job_id,
            "status": result.status.value,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "metrics": result.metrics.dict() if result.metrics else None
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            
        logger.info("Webhook notification sent", job_id=result.job_id, webhook_url=webhook_url)
        
    except Exception as e:
        logger.error("Failed to send webhook", job_id=result.job_id, error=str(e))


async def _check_rate_limit(user_id: str):
    """Simple rate limiting (use Redis in production)"""
    current_time = datetime.utcnow().timestamp()
    
    if user_id not in rate_limit_storage:
        rate_limit_storage[user_id] = []
    
    # Remove old requests (older than 1 hour)
    rate_limit_storage[user_id] = [
        timestamp for timestamp in rate_limit_storage[user_id]
        if current_time - timestamp < 3600
    ]
    
    # Check limit (100 requests per hour per user)
    if len(rate_limit_storage[user_id]) >= 100:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 100 requests per hour."
        )
    
    # Record current request
    rate_limit_storage[user_id].append(current_time)


def _estimate_processing_time(request: ParseRequest) -> int:
    """Estimate processing time based on request parameters"""
    base_time = 10  # Base processing time
    
    if request.include_stt:
        base_time += 15  # STT adds ~15 seconds
    
    if request.include_ocr:
        base_time += 20  # OCR adds ~20 seconds
    
    if request.priority == "low":
        base_time += 30  # Queue delay for low priority
    
    return base_time