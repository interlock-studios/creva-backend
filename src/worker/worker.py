import json
import asyncio
import structlog
from google.cloud import pubsub_v1
from concurrent.futures import ThreadPoolExecutor
import os
import signal
import sys
from typing import Dict, Any

from src.worker.pipeline import ProcessingPipeline
from src.utils.logging import setup_logging

logger = structlog.get_logger()


class WorkerService:
    def __init__(self):
        self.subscriber = pubsub_v1.SubscriberClient()
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.subscription_name = "worker-subscription"
        self.pipeline = ProcessingPipeline()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running = True
    
    def start(self):
        setup_logging()
        logger.info("Worker service starting up")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        subscription_path = self.subscriber.subscription_path(
            self.project_id, self.subscription_name
        )
        
        # Configure flow control
        flow_control = pubsub_v1.types.FlowControl(max_messages=10)
        
        logger.info("Starting message consumption", subscription=subscription_path)
        
        try:
            # Pull messages
            streaming_pull_future = self.subscriber.subscribe(
                subscription_path,
                callback=self._message_callback,
                flow_control=flow_control
            )
            
            logger.info("Worker listening for messages")
            
            # Keep the main thread running
            try:
                streaming_pull_future.result()
            except KeyboardInterrupt:
                streaming_pull_future.cancel()
                streaming_pull_future.result()
        
        except Exception as e:
            logger.error("Worker service error", error=str(e))
            sys.exit(1)
    
    def _signal_handler(self, signum, frame):
        logger.info("Received shutdown signal", signal=signum)
        self.running = False
        sys.exit(0)
    
    def _message_callback(self, message):
        try:
            # Parse message data
            message_data = json.loads(message.data.decode('utf-8'))
            job_id = message_data.get('job_id')
            url = message_data.get('url')
            user_id = message_data.get('user_id')
            
            if not all([job_id, url, user_id]):
                logger.error("Invalid message data", message_data=message_data)
                message.nack()
                return
            
            logger.info(
                "Processing message",
                job_id=job_id,
                url=url,
                user_id=user_id,
                message_id=message.message_id
            )
            
            # Process the video in a separate thread to avoid blocking
            future = self.executor.submit(self._process_video_sync, job_id, url, user_id)
            
            try:
                # Wait for completion with timeout
                future.result(timeout=300)  # 5 minute timeout
                message.ack()
                logger.info("Message processed successfully", job_id=job_id)
            
            except Exception as e:
                logger.error("Video processing failed", job_id=job_id, error=str(e))
                message.nack()
        
        except Exception as e:
            logger.error("Message callback error", error=str(e))
            message.nack()
    
    def _process_video_sync(self, job_id: str, url: str, user_id: str):
        """Synchronous wrapper for async video processing"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async pipeline
            loop.run_until_complete(
                self.pipeline.process_video(job_id, url, user_id)
            )
        
        except Exception as e:
            logger.error("Sync wrapper error", job_id=job_id, error=str(e))
            raise
        
        finally:
            loop.close()


if __name__ == "__main__":
    worker = WorkerService()
    worker.start()