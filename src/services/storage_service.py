from google.cloud import storage
import structlog
from typing import Optional
import os
from datetime import datetime, timedelta

logger = structlog.get_logger()


class StorageService:
    def __init__(self):
        self.client = storage.Client()
        self.raw_videos_bucket = "sets-ai-raw-videos"
        self.keyframes_bucket = "sets-ai-keyframes"
    
    async def upload_video(self, job_id: str, video_content: bytes) -> str:
        try:
            bucket = self.client.bucket(self.raw_videos_bucket)
            blob_name = f"{job_id}/video.mp4"
            blob = bucket.blob(blob_name)
            
            # Set 24-hour retention
            blob.upload_from_string(
                video_content,
                content_type="video/mp4"
            )
            
            # Set metadata
            blob.metadata = {
                "job_id": job_id,
                "uploaded_at": datetime.utcnow().isoformat()
            }
            blob.patch()
            
            logger.info(
                "Video uploaded",
                job_id=job_id,
                size_bytes=len(video_content),
                blob_name=blob_name
            )
            
            return f"gs://{self.raw_videos_bucket}/{blob_name}"
            
        except Exception as e:
            logger.error("Failed to upload video", job_id=job_id, error=str(e))
            raise
    
    async def upload_keyframes(self, job_id: str, keyframes: list) -> list:
        try:
            bucket = self.client.bucket(self.keyframes_bucket)
            uploaded_paths = []
            
            for i, keyframe_content in enumerate(keyframes):
                blob_name = f"{job_id}/keyframe_{i:04d}.jpg"
                blob = bucket.blob(blob_name)
                
                blob.upload_from_string(
                    keyframe_content,
                    content_type="image/jpeg"
                )
                
                # Set metadata
                blob.metadata = {
                    "job_id": job_id,
                    "frame_index": str(i),
                    "uploaded_at": datetime.utcnow().isoformat()
                }
                blob.patch()
                
                uploaded_paths.append(f"gs://{self.keyframes_bucket}/{blob_name}")
            
            logger.info(
                "Keyframes uploaded",
                job_id=job_id,
                keyframes_count=len(keyframes)
            )
            
            return uploaded_paths
            
        except Exception as e:
            logger.error("Failed to upload keyframes", job_id=job_id, error=str(e))
            raise
    
    async def download_blob(self, bucket_name: str, blob_name: str) -> bytes:
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            content = blob.download_as_bytes()
            
            logger.debug(
                "Blob downloaded",
                bucket=bucket_name,
                blob=blob_name,
                size_bytes=len(content)
            )
            
            return content
            
        except Exception as e:
            logger.error("Failed to download blob", bucket=bucket_name, blob=blob_name, error=str(e))
            raise
    
    async def cleanup_job_files(self, job_id: str) -> None:
        try:
            # Clean up raw videos (should be done after 24h automatically)
            raw_bucket = self.client.bucket(self.raw_videos_bucket)
            raw_blobs = raw_bucket.list_blobs(prefix=f"{job_id}/")
            
            for blob in raw_blobs:
                blob.delete()
            
            # Clean up keyframes (should be done after 7d automatically)
            keyframes_bucket = self.client.bucket(self.keyframes_bucket)
            keyframe_blobs = keyframes_bucket.list_blobs(prefix=f"{job_id}/")
            
            for blob in keyframe_blobs:
                blob.delete()
            
            logger.info("Job files cleaned up", job_id=job_id)
            
        except Exception as e:
            logger.error("Failed to cleanup job files", job_id=job_id, error=str(e))