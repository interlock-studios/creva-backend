from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any
import structlog
import uuid
from datetime import datetime

from src.models.job import ParseRequest, ParseResponse, JobResult, JobStatus
from src.api.auth import get_current_user
from src.services.firestore_service import FirestoreService
from src.services.pubsub_service import PubSubService

logger = structlog.get_logger()
router = APIRouter()

firestore_service = FirestoreService()
pubsub_service = PubSubService()


@router.post("/parse", response_model=ParseResponse, status_code=202)
async def parse_video(
    request: ParseRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        job_id = str(uuid.uuid4())
        
        # Create initial job record
        job_result = JobResult(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress=0
        )
        
        # Save to Firestore
        await firestore_service.save_job_result(job_result)
        
        # Publish to Pub/Sub for processing
        message_data = {
            "job_id": job_id,
            "url": request.url,
            "user_id": user["uid"]
        }
        await pubsub_service.publish_parse_request(message_data)
        
        logger.info(
            "Parse request submitted",
            job_id=job_id,
            url=request.url,
            user_id=user["uid"]
        )
        
        return ParseResponse(job_id=job_id)
        
    except Exception as e:
        logger.error("Error submitting parse request", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="INTERNAL: Failed to submit parse request"
        )


@router.get("/parse/{job_id}")
async def get_parse_result(
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        job_result = await firestore_service.get_job_result(job_id)
        
        if not job_result:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )
        
        if job_result.status == JobStatus.SUCCEEDED:
            return {
                "status": job_result.status.value,
                "workout_json": job_result.workout_json,
                "metrics": job_result.metrics
            }
        elif job_result.status == JobStatus.PROCESSING:
            return {
                "status": job_result.status.value,
                "progress": job_result.progress or 0
            }
        else:
            return {
                "status": job_result.status.value,
                "message": job_result.message or "Processing failed"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving parse result", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="INTERNAL: Failed to retrieve parse result"
        )


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}