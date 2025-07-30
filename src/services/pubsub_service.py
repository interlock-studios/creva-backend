from google.cloud import pubsub_v1
import json
import structlog
import os
from typing import Dict, Any

logger = structlog.get_logger()


class PubSubService:
    def __init__(self):
        self.publisher = pubsub_v1.PublisherClient()
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "sets-ai")
        self.topic_name = "parse-request"
    
    async def publish_parse_request(self, message_data: Dict[str, Any]) -> None:
        try:
            topic_path = self.publisher.topic_path(
                self.project_id, 
                self.topic_name
            )
            
            message_json = json.dumps(message_data)
            message_bytes = message_json.encode("utf-8")
            
            future = self.publisher.publish(topic_path, message_bytes)
            message_id = future.result()
            
            logger.info(
                "Message published to Pub/Sub",
                message_id=message_id,
                job_id=message_data.get("job_id")
            )
            
        except Exception as e:
            logger.error("Failed to publish message", error=str(e))
            raise