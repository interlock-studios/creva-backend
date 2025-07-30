from google.cloud import firestore
from typing import Optional, Dict, Any
import structlog
from datetime import datetime

from src.models.job import JobResult, JobStatus

logger = structlog.get_logger()


class FirestoreService:
    def __init__(self):
        self.client = firestore.Client()
        self.collection = "results"
    
    async def save_job_result(self, job_result: JobResult) -> None:
        try:
            doc_ref = self.client.collection(self.collection).document(job_result.job_id)
            
            data = job_result.dict()
            data["created_at"] = firestore.SERVER_TIMESTAMP
            data["updated_at"] = firestore.SERVER_TIMESTAMP
            
            doc_ref.set(data)
            
            logger.info("Job result saved", job_id=job_result.job_id)
            
        except Exception as e:
            logger.error("Failed to save job result", job_id=job_result.job_id, error=str(e))
            raise
    
    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        try:
            doc_ref = self.client.collection(self.collection).document(job_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            return JobResult(**data)
            
        except Exception as e:
            logger.error("Failed to get job result", job_id=job_id, error=str(e))
            raise
    
    async def update_job_status(
        self, 
        job_id: str, 
        status: JobStatus, 
        progress: Optional[int] = None,
        message: Optional[str] = None,
        workout_json: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        try:
            doc_ref = self.client.collection(self.collection).document(job_id)
            
            update_data = {
                "status": status.value,
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            
            if progress is not None:
                update_data["progress"] = progress
            if message is not None:
                update_data["message"] = message
            if workout_json is not None:
                update_data["workout_json"] = workout_json
            if metrics is not None:
                update_data["metrics"] = metrics
            
            doc_ref.update(update_data)
            
            logger.info("Job status updated", job_id=job_id, status=status.value)
            
        except Exception as e:
            logger.error("Failed to update job status", job_id=job_id, error=str(e))
            raise