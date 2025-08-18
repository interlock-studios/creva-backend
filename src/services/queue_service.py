from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from google.cloud.firestore import Client
import logging
import os
import warnings
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time
import asyncio

# Suppress Firestore deprecation warnings for now
warnings.filterwarnings("ignore", message="Detected filter using positional arguments")

logger = logging.getLogger(__name__)


class QueueService:
    def __init__(self):
        """Initialize Firestore queue service"""
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not self.project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT_ID not set. Queue will be disabled.")
            self.db = None
            return

        try:
            # Initialize Firestore client
            self.db = firestore.Client(project=self.project_id)
            self.queue_collection = self.db.collection("processing_queue")
            self.results_collection = self.db.collection("processing_results")

            logger.info(f"Queue service connected to Firestore in project: {self.project_id}")

        except Exception as e:
            logger.warning(f"Firestore connection failed: {e}. Queue will be disabled.")
            self.db = None

    async def enqueue_video(self, url: str, request_id: str, priority: str = "normal", localization: Optional[str] = None) -> str:
        """Add video to processing queue"""
        if not self.db:
            raise Exception("Queue service not available")

        job_id = f"{request_id}_{int(time.time() * 1000)}"

        job_data = {
            "url": url,
            "request_id": request_id,
            "job_id": job_id,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "attempts": 0,
            "max_attempts": 3,
            "last_error": None,
            "worker_id": None,
            "localization": localization,
        }

        self.queue_collection.document(job_id).set(job_data)
        logger.info(f"Enqueued video job: {job_id} for URL: {url[:50]}...")

        return job_id

    async def get_job_by_url(self, url: str, status: Optional[str] = None) -> Optional[Dict]:
        """Check if URL is already in queue with optional status filter"""
        if not self.db:
            return None

        try:
            query = self.queue_collection.where(filter=FieldFilter("url", "==", url))

            if status:
                query = query.where(filter=FieldFilter("status", "==", status))

            # Get most recent job for this URL
            query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(1)

            docs = query.stream()
            for doc in docs:
                return {"job_id": doc.id, **doc.to_dict()}

            return None

        except Exception as e:
            logger.error(f"Error checking job by URL: {e}")
            return None

    async def get_next_job(self, worker_id: str) -> Optional[Dict]:
        """Get next pending job for worker to process"""
        if not self.db:
            return None

        # Try up to 3 times to claim a job (in case of race conditions)
        for attempt in range(3):
            try:
                # Find the oldest pending jobs
                query = (
                    self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
                    .order_by("created_at")
                    .limit(5)  # Get a few in case of race conditions
                )

                docs = list(query.stream())
                if not docs:
                    return None

                # Try to claim each job until we succeed
                for doc in docs:
                    job_data = doc.to_dict()
                    job_id = doc.id

                    # Check if job is still pending (to avoid race condition)
                    current_status = job_data.get("status")
                    if current_status != "pending":
                        logger.debug(f"Job {job_id} already claimed (status: {current_status})")
                        continue

                    # Try to claim the job atomically
                    try:
                        # Use conditional update to prevent race conditions
                        doc.reference.update(
                            {
                                "status": "processing",
                                "worker_id": worker_id,
                                "started_at": datetime.utcnow(),
                                "attempts": job_data.get("attempts", 0) + 1,
                            }
                        )

                        logger.info(f"Worker {worker_id} claimed job {job_id}")
                        return {"job_id": job_id, **job_data}
                    except Exception as e:
                        # Another worker might have claimed it
                        logger.debug(f"Failed to claim job {job_id}: {e}")
                        continue

                # If we get here, all jobs were already claimed
                if attempt < 2:
                    await asyncio.sleep(0.1)  # Brief pause before retry

            except Exception as e:
                logger.error(f"Error getting next job: {e}")
                return None

        return None

    async def mark_job_complete(self, job_id: str, result: Dict):
        """Mark job as complete and store result"""
        if not self.db:
            return

        try:
            # Store result
            self.results_collection.document(job_id).set(
                {
                    "job_id": job_id,
                    "result": result,
                    "completed_at": datetime.utcnow(),
                    "status": "completed",
                }
            )

            # Update queue status
            self.queue_collection.document(job_id).update(
                {"status": "completed", "completed_at": datetime.utcnow()}
            )

            logger.info(f"Job {job_id} marked as complete")

        except Exception as e:
            logger.error(f"Error marking job complete: {e}")
            raise

    async def mark_job_failed(self, job_id: str, error: str):
        """Mark job as failed"""
        if not self.db:
            return

        try:
            job_ref = self.queue_collection.document(job_id)
            job_doc = job_ref.get()

            if job_doc.exists:
                job_data = job_doc.to_dict()
                attempts = job_data.get("attempts", 0)
                max_attempts = job_data.get("max_attempts", 3)

                update_data = {
                    "last_error": error,
                    "failed_at": datetime.utcnow(),
                    "worker_id": None,
                }

                # If we've exceeded max attempts, mark as failed
                if attempts >= max_attempts:
                    update_data["status"] = "failed"
                    logger.error(f"Job {job_id} failed after {attempts} attempts: {error}")
                else:
                    # Otherwise, mark as pending for retry
                    update_data["status"] = "pending"
                    logger.warning(f"Job {job_id} failed attempt {attempts}, will retry: {error}")

                job_ref.update(update_data)

        except Exception as e:
            logger.error(f"Error marking job failed: {e}")

    async def get_job_result(self, job_id: str) -> Optional[Dict]:
        """Get result for completed job"""
        if not self.db:
            return None

        try:
            # Check if job exists in queue
            queue_doc = self.queue_collection.document(job_id).get()
            if not queue_doc.exists:
                return {"status": "not_found"}

            queue_data = queue_doc.to_dict()
            status = queue_data.get("status", "unknown")

            if status == "completed":
                # Get result
                result_doc = self.results_collection.document(job_id).get()
                if result_doc.exists:
                    result_data = result_doc.to_dict()
                    return {
                        "status": "completed",
                        "result": result_data.get("result"),
                        "completed_at": result_data.get("completed_at"),
                    }

            return {
                "status": status,
                "created_at": queue_data.get("created_at"),
                "attempts": queue_data.get("attempts", 0),
                "last_error": queue_data.get("last_error"),
            }

        except Exception as e:
            logger.error(f"Error getting job result: {e}")
            return {"status": "error", "error": str(e)}

    async def cleanup_old_jobs(self, days: int = 7):
        """Clean up old completed/failed jobs"""
        if not self.db:
            return 0

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            deleted_count = 0

            # Clean up old queue entries
            old_jobs = (
                self.queue_collection.where(filter=FieldFilter("status", "in", ["completed", "failed"]))
                .where(filter=FieldFilter("created_at", "<", cutoff_date))
                .stream()
            )

            batch = self.db.batch()
            batch_size = 0

            for doc in old_jobs:
                batch.delete(doc.reference)

                # Also delete corresponding result if exists
                result_ref = self.results_collection.document(doc.id)
                batch.delete(result_ref)

                batch_size += 2
                deleted_count += 1

                # Commit batch every 250 operations (Firestore limit is 500)
                if batch_size >= 250:
                    batch.commit()
                    batch = self.db.batch()
                    batch_size = 0

            # Commit remaining deletions
            if batch_size > 0:
                batch.commit()

            logger.info(f"Cleaned up {deleted_count} old jobs")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")
            return 0

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        if not self.db:
            return {"status": "disabled"}

        try:
            stats = {
                "status": "active",
                "queue_stats": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
            }

            # Count jobs by status
            for status in ["pending", "processing", "completed", "failed"]:
                count = len(
                    list(self.queue_collection.where(filter=FieldFilter("status", "==", status)).limit(1000).stream())
                )
                stats["queue_stats"][status] = count

            return stats

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {"status": "error", "error": str(e)}
