from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from google.api_core import retry
from google.api_core import exceptions
import logging
import os
import warnings
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import time
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

        # Connection configuration with appropriate timeouts
        self.operation_timeout = 30  # 30 seconds for operations
        self.connection_timeout = 10  # 10 seconds for reads
        self.batch_timeout = 60  # 60 seconds for batch operations
        
        # Configure retry policy for better resilience
        self.retry_policy = retry.Retry(
            initial=1.0,  # Initial delay
            maximum=10.0,  # Maximum delay
            multiplier=2.0,  # Backoff multiplier
            deadline=30.0,  # Total deadline
            predicate=retry.if_exception_type(
                exceptions.DeadlineExceeded,
                exceptions.ServiceUnavailable,
                exceptions.InternalServerError,
            ),
        )

        self.db = self._initialize_firestore_with_retry()

    def _initialize_firestore_with_retry(self):
        """Initialize Firestore client with retry logic"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Initialize Firestore client with timeout
                self.db = firestore.Client(project=self.project_id)
                self.queue_collection = self.db.collection("processing_queue")
                self.results_collection = self.db.collection("processing_results")
                self.dead_letter_collection = self.db.collection("processing_dead_letter")
                
                # Test connection with a lightweight operation
                try:
                    # Just test if we can access the collection (no actual read/write)
                    test_doc_ref = self.queue_collection.document("__connection_test__")
                    # This is a lightweight operation that just creates a reference
                    logger.info(f"Queue service connected to Firestore in project: {self.project_id}")
                    return self.db
                except Exception as test_error:
                    logger.warning(f"Queue service connection test failed (attempt {attempt + 1}): {test_error}")
                    if attempt == max_attempts - 1:
                        raise test_error

            except Exception as e:
                wait_time = min(2 ** attempt, 8)  # Exponential backoff, max 8 seconds
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Queue service initialization attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"All queue service initialization attempts failed: {e}. Queue will be disabled.")
                    return None

        return None

    async def enqueue_video(
        self,
        url: str,
        request_id: str,
        priority: str = "normal",
        localization: Optional[str] = None,
    ) -> str:
        """Add video to processing queue"""
        if not self.db:
            raise Exception("Queue service not available")

        job_id = f"{request_id}_{int(time.time() * 1000)}"

        # Convert priority to numeric value for sorting
        priority_values = {"high": 1, "normal": 2, "low": 3}
        priority_value = priority_values.get(priority, 2)  # Default to normal

        job_data = {
            "url": url,
            "request_id": request_id,
            "job_id": job_id,
            "status": "pending",
            "priority": priority,
            "priority_value": priority_value,
            "created_at": datetime.now(timezone.utc),
            "attempts": 0,
            "max_attempts": 3,
            "last_error": None,
            "worker_id": None,
            "localization": localization,
        }

        try:
            self.queue_collection.document(job_id).set(
                job_data, 
                timeout=self.operation_timeout, 
                retry=self.retry_policy
            )
            logger.info(f"Enqueued video job: {job_id} for URL: {url[:50]}...")
            return job_id
        except exceptions.DeadlineExceeded as e:
            logger.error(f"Queue enqueue timeout after {self.operation_timeout}s for job: {job_id} - {e}")
            raise Exception(f"Failed to enqueue job due to timeout: {e}")
        except exceptions.ServiceUnavailable as e:
            logger.error(f"Firestore service unavailable for queue enqueue: {e}")
            raise Exception(f"Queue service unavailable: {e}")
        except Exception as e:
            logger.error(f"Error enqueuing video job: {e}")
            raise Exception(f"Failed to enqueue job: {e}")

    async def get_job_by_url(self, url: str, status: Optional[str] = None, localization: Optional[str] = None) -> Optional[Dict]:
        """Check if URL+localization combo is already in queue with optional status filter"""
        if not self.db:
            return None

        try:
            query = self.queue_collection.where(filter=FieldFilter("url", "==", url))

            # Add localization filter if provided
            if localization:
                query = query.where(filter=FieldFilter("localization", "==", localization))
            else:
                # If no localization specified, only match jobs with no localization
                query = query.where(filter=FieldFilter("localization", "==", None))

            if status:
                query = query.where(filter=FieldFilter("status", "==", status))

            # Get most recent job for this URL+localization combo
            query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(1)

            docs = query.stream(timeout=self.connection_timeout, retry=self.retry_policy)
            for doc in docs:
                return {"job_id": doc.id, **doc.to_dict()}

            return None

        except exceptions.DeadlineExceeded as e:
            logger.error(f"Queue job lookup timeout after {self.connection_timeout}s for URL: {url[:50]}... - {e}")
            return None
        except exceptions.ServiceUnavailable as e:
            logger.error(f"Firestore service unavailable for queue job lookup: {e}")
            return None
        except Exception as e:
            logger.error(f"Error checking job by URL+localization: {e}")
            return None

    async def get_next_job(self, worker_id: str) -> Optional[Dict]:
        """Get next pending job for worker to process using atomic transactions"""
        if not self.db:
            return None

        # Try up to 3 times to claim a job (in case of race conditions)
        for attempt in range(3):
            try:
                # Find pending jobs - fallback to simple query if index not ready
                current_time = datetime.now(timezone.utc)
                try:
                    # Try priority-based query first (requires composite index)
                    query = (
                        self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
                        .order_by("priority_value")  # High priority first (1 < 2 < 3)
                        .order_by("created_at")      # Then oldest first
                        .limit(10)  # Get more to account for retry delays
                    )
                    docs = list(query.stream(timeout=self.connection_timeout, retry=self.retry_policy))
                except Exception as index_error:
                    # Fallback to simple query if composite index not ready
                    if "index" in str(index_error).lower():
                        logger.debug(f"Composite index not ready, using fallback query: {index_error}")
                        query = (
                            self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
                            .order_by("created_at")  # Simple query - just oldest first
                            .limit(10)
                        )
                        docs = list(query.stream(timeout=self.connection_timeout, retry=self.retry_policy))
                    else:
                        logger.error(f"Error getting next job: {index_error}")
                        raise index_error

                if not docs:
                    return None

                # Try to claim each job until we succeed using transactions
                for doc in docs:
                    job_id = doc.id
                    job_data = doc.to_dict()
                    
                    # Check if job is ready to retry (respect retry delays)
                    retry_after = job_data.get("retry_after")
                    if retry_after and current_time < retry_after:
                        logger.debug(f"Job {job_id} not ready for retry until {retry_after}")
                        continue
                    
                    # Use atomic transaction to prevent race conditions
                    transaction = self.db.transaction()
                    job_ref = self.queue_collection.document(job_id)
                    
                    try:
                        @firestore.transactional
                        def claim_job_transaction(transaction, job_ref):
                            # Get current job state within transaction
                            job_snapshot = job_ref.get(transaction=transaction)
                            if not job_snapshot.exists:
                                return None
                            
                            job_data = job_snapshot.to_dict()
                            current_status = job_data.get("status")
                            
                            # Only claim if still pending
                            if current_status != "pending":
                                return None
                            
                            # Double-check retry delay within transaction
                            retry_after = job_data.get("retry_after")
                            if retry_after and current_time < retry_after:
                                return None
                            
                            # Atomically update to processing
                            transaction.update(job_ref, {
                                "status": "processing",
                                "worker_id": worker_id,
                                "started_at": datetime.now(timezone.utc),
                                "attempts": job_data.get("attempts", 0) + 1,
                                "retry_after": None,  # Clear retry delay
                            })
                            
                            return {"job_id": job_id, **job_data}
                        
                        # Execute transaction
                        result = claim_job_transaction(transaction, job_ref)
                        if result:
                            logger.info(f"Worker {worker_id} claimed job {job_id}")
                            return result
                            
                    except Exception as e:
                        # Transaction failed (likely another worker claimed it)
                        logger.debug(f"Failed to claim job {job_id}: {e}")
                        continue

                # If we get here, all jobs were already claimed
                if attempt < 2:
                    # Exponential backoff
                    backoff_time = 0.1 * (2 ** attempt)
                    await asyncio.sleep(backoff_time)

            except Exception as e:
                logger.error(f"Error getting next job: {e}")
                return None

        return None

    async def mark_job_complete(self, job_id: str, result: Dict):
        """Mark job as complete and store result"""
        if not self.db:
            return

        try:
            # Store result with timeout and retry
            self.results_collection.document(job_id).set(
                {
                    "job_id": job_id,
                    "result": result,
                    "completed_at": datetime.now(timezone.utc),
                    "status": "completed",
                },
                timeout=self.operation_timeout,
                retry=self.retry_policy
            )

            # Update queue status with timeout and retry
            self.queue_collection.document(job_id).update(
                {"status": "completed", "completed_at": datetime.now(timezone.utc)},
                timeout=self.operation_timeout,
                retry=self.retry_policy
            )

            logger.info(f"Job {job_id} marked as complete")

        except exceptions.DeadlineExceeded as e:
            logger.error(f"Job completion timeout after {self.operation_timeout}s for job: {job_id} - {e}")
            raise Exception(f"Failed to mark job complete due to timeout: {e}")
        except exceptions.ServiceUnavailable as e:
            logger.error(f"Firestore service unavailable for job completion: {e}")
            raise Exception(f"Queue service unavailable: {e}")
        except Exception as e:
            logger.error(f"Error marking job complete: {e}")
            raise

    async def mark_job_failed(self, job_id: str, error: str):
        """Mark job as failed with dead letter queue support"""
        if not self.db:
            return

        try:
            job_ref = self.queue_collection.document(job_id)
            job_doc = job_ref.get(timeout=self.connection_timeout, retry=self.retry_policy)

            if job_doc.exists:
                job_data = job_doc.to_dict()
                attempts = job_data.get("attempts", 0)
                max_attempts = job_data.get("max_attempts", 3)

                # Sanitize error message to ensure it's serializable
                try:
                    # Try to serialize the error to catch any non-serializable objects
                    import json
                    json.dumps(error)
                    sanitized_error = error
                except (TypeError, ValueError):
                    # If error contains non-serializable objects, create a clean string
                    sanitized_error = f"Error occurred: {type(error).__name__}"
                
                update_data = {
                    "last_error": sanitized_error,
                    "failed_at": datetime.now(timezone.utc),
                    "worker_id": None,
                }

                # If we've exceeded max attempts, move to dead letter queue
                if attempts >= max_attempts:
                    # Move to dead letter queue for investigation
                    dead_letter_data = {
                        **job_data,
                        "final_error": sanitized_error,
                        "total_attempts": attempts,
                        "moved_to_dlq_at": datetime.now(timezone.utc),
                        "original_job_id": job_id,
                    }
                    
                    # Add to dead letter queue with timeout and retry
                    self.dead_letter_collection.document(job_id).set(
                        dead_letter_data,
                        timeout=self.operation_timeout,
                        retry=self.retry_policy
                    )
                    
                    # Remove from main queue with timeout and retry
                    job_ref.delete(timeout=self.operation_timeout, retry=self.retry_policy)
                    
                    logger.error(f"Job {job_id} moved to dead letter queue after {attempts} attempts: {error}")
                else:
                    # Otherwise, mark as pending for retry with exponential backoff
                    retry_delay = min(300, 30 * (2 ** (attempts - 1)))  # Max 5 minutes
                    update_data["status"] = "pending"
                    update_data["retry_after"] = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                    job_ref.update(update_data, timeout=self.operation_timeout, retry=self.retry_policy)
                    logger.warning(f"Job {job_id} failed attempt {attempts}, will retry in {retry_delay}s: {error}")

        except exceptions.DeadlineExceeded as e:
            logger.error(f"Job failure handling timeout after {self.operation_timeout}s for job: {job_id} - {e}")
        except exceptions.ServiceUnavailable as e:
            logger.error(f"Firestore service unavailable for job failure handling: {e}")
        except Exception as e:
            logger.error(f"Error marking job failed: {e}")

    async def get_dead_letter_jobs(self, limit: int = 100) -> List[Dict]:
        """Get jobs from dead letter queue for investigation"""
        if not self.db:
            return []

        try:
            docs = (
                self.dead_letter_collection
                .order_by("moved_to_dlq_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            
            return [{"job_id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"Error getting dead letter jobs: {e}")
            return []

    async def retry_dead_letter_job(self, job_id: str) -> bool:
        """Move job from dead letter queue back to main queue for retry"""
        if not self.db:
            return False

        try:
            # Get job from dead letter queue
            dlq_doc = self.dead_letter_collection.document(job_id).get()
            if not dlq_doc.exists:
                logger.warning(f"Job {job_id} not found in dead letter queue")
                return False

            dlq_data = dlq_doc.to_dict()
            
            # Reset job for retry
            retry_job_data = {
                "url": dlq_data["url"],
                "request_id": dlq_data["request_id"],
                "job_id": job_id,
                "status": "pending",
                "priority": dlq_data.get("priority", "normal"),
                "priority_value": dlq_data.get("priority_value", 2),
                "created_at": datetime.now(timezone.utc),
                "attempts": 0,
                "max_attempts": 3,
                "last_error": None,
                "worker_id": None,
                "localization": dlq_data.get("localization"),
                "retried_from_dlq": True,
                "original_failure": dlq_data.get("final_error"),
            }

            # Add back to main queue
            self.queue_collection.document(job_id).set(retry_job_data)
            
            # Remove from dead letter queue
            self.dead_letter_collection.document(job_id).delete()
            
            logger.info(f"Job {job_id} moved from dead letter queue back to main queue")
            return True

        except Exception as e:
            logger.error(f"Error retrying dead letter job {job_id}: {e}")
            return False

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

    async def cleanup_old_jobs(self, days: int = 7, batch_size: int = 100):
        """Clean up old completed/failed jobs with optimized batching"""
        if not self.db:
            return 0

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            total_deleted = 0

            # Process in smaller batches to avoid timeouts
            while True:
                # Get a batch of old jobs
                old_jobs_query = (
                    self.queue_collection.where(
                        filter=FieldFilter("status", "in", ["completed", "failed"])
                    )
                    .where(filter=FieldFilter("created_at", "<", cutoff_date))
                    .limit(batch_size)
                )

                docs = list(old_jobs_query.stream(timeout=self.batch_timeout, retry=self.retry_policy))
                if not docs:
                    break  # No more jobs to clean up

                # Delete this batch
                batch = self.db.batch()
                batch_count = 0

                for doc in docs:
                    # Delete queue entry
                    batch.delete(doc.reference)
                    batch_count += 1

                    # Delete corresponding result if exists
                    result_ref = self.results_collection.document(doc.id)
                    batch.delete(result_ref)
                    batch_count += 1

                    # Commit when approaching Firestore limit
                    if batch_count >= 450:  # Leave some margin under 500 limit
                        batch.commit(timeout=self.batch_timeout, retry=self.retry_policy)
                        batch = self.db.batch()
                        batch_count = 0

                # Commit remaining deletions in this batch
                if batch_count > 0:
                    batch.commit(timeout=self.batch_timeout, retry=self.retry_policy)

                deleted_in_batch = len(docs)
                total_deleted += deleted_in_batch
                
                logger.debug(f"Cleaned up batch of {deleted_in_batch} jobs")

                # If we got fewer docs than requested, we're done
                if deleted_in_batch < batch_size:
                    break

                # Small delay between batches to avoid overwhelming Firestore
                await asyncio.sleep(0.1)

            # Also clean up old dead letter queue entries
            dlq_deleted = await self._cleanup_old_dead_letter_jobs(cutoff_date, batch_size)
            
            logger.info(f"Cleaned up {total_deleted} old jobs and {dlq_deleted} dead letter jobs")
            return total_deleted + dlq_deleted

        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")
            return 0

    async def _cleanup_old_dead_letter_jobs(self, cutoff_date: datetime, batch_size: int = 100):
        """Clean up old dead letter queue entries"""
        total_deleted = 0
        
        try:
            while True:
                # Get a batch of old dead letter jobs
                old_dlq_query = (
                    self.dead_letter_collection.where(
                        filter=FieldFilter("moved_to_dlq_at", "<", cutoff_date)
                    )
                    .limit(batch_size)
                )

                docs = list(old_dlq_query.stream())
                if not docs:
                    break

                # Delete this batch
                batch = self.db.batch()
                for doc in docs:
                    batch.delete(doc.reference)

                batch.commit()
                
                deleted_in_batch = len(docs)
                total_deleted += deleted_in_batch

                if deleted_in_batch < batch_size:
                    break

                await asyncio.sleep(0.1)

            return total_deleted

        except Exception as e:
            logger.error(f"Error cleaning up dead letter jobs: {e}")
            return 0

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics with optimized queries"""
        if not self.db:
            return {"status": "disabled"}

        try:
            stats = {
                "status": "active",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "queue_stats": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
                "priority_stats": {"high": 0, "normal": 0, "low": 0},
                "dead_letter_stats": {"total": 0},

            }

            # Count jobs by status (limit to avoid expensive queries)
            for status in ["pending", "processing"]:  # Only count active jobs
                count = len(
                    list(
                        self.queue_collection.where(filter=FieldFilter("status", "==", status))
                        .limit(1000)  # Reasonable limit for active monitoring
                        .stream()
                    )
                )
                stats["queue_stats"][status] = count

            # Count pending jobs by priority
            pending_jobs = (
                self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
                .limit(1000)
                .stream()
            )
            
            for doc in pending_jobs:
                job_data = doc.to_dict()
                priority = job_data.get("priority", "normal")
                stats["priority_stats"][priority] = stats["priority_stats"].get(priority, 0) + 1

            # Count dead letter queue entries
            dlq_count = len(
                list(
                    self.dead_letter_collection.limit(1000).stream()
                )
            )
            stats["dead_letter_stats"]["total"] = dlq_count



            return stats

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {"status": "error", "error": str(e)}

    def get_detailed_queue_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboards"""
        if not self.db:
            return {"status": "disabled"}

        try:
            metrics = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "queue_depth": 0,
                "processing_rate": 0,
                "error_rate": 0,
                "average_processing_time": 0,
                "oldest_pending_job_age": 0,
            }

            # Get queue depth (pending jobs)
            pending_count = len(
                list(
                    self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
                    .limit(1000)
                    .stream()
                )
            )
            metrics["queue_depth"] = pending_count

            # Get oldest pending job age
            if pending_count > 0:
                oldest_job = (
                    self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
                    .order_by("created_at")
                    .limit(1)
                    .stream()
                )
                
                for doc in oldest_job:
                    job_data = doc.to_dict()
                    created_at = job_data.get("created_at")
                    if created_at:
                        age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
                        metrics["oldest_pending_job_age"] = age_seconds
                    break

            # Calculate processing rate (jobs completed in last hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_completed = len(
                list(
                    self.queue_collection.where(filter=FieldFilter("status", "==", "completed"))
                    .where(filter=FieldFilter("completed_at", ">=", one_hour_ago))
                    .limit(1000)
                    .stream()
                )
            )
            metrics["processing_rate"] = recent_completed

            return metrics

        except Exception as e:
            logger.error(f"Error getting detailed queue metrics: {e}")
            return {"status": "error", "error": str(e)}
