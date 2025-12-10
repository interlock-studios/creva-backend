"""
Cloud Functions for Creva - Firestore to Search Index Sync

These functions automatically sync videos from Firestore to the search index
(Algolia or Typesense) whenever a video is created, updated, or deleted.

Deployment:
    gcloud functions deploy sync_video_to_search \
        --runtime python311 \
        --trigger-event providers/cloud.firestore/eventTypes/document.write \
        --trigger-resource "projects/creva-e6435/databases/(default)/documents/videos/{videoId}" \
        --project creva-e6435 \
        --region us-central1 \
        --set-env-vars ALGOLIA_APP_ID=xxx,ALGOLIA_API_KEY=xxx

Or with Typesense:
    gcloud functions deploy sync_video_to_search \
        --runtime python311 \
        --trigger-event providers/cloud.firestore/eventTypes/document.write \
        --trigger-resource "projects/creva-e6435/databases/(default)/documents/videos/{videoId}" \
        --project creva-e6435 \
        --region us-central1 \
        --set-env-vars TYPESENSE_HOST=xxx,TYPESENSE_API_KEY=xxx
"""

import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Search backend configuration
ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY")
ALGOLIA_INDEX_NAME = os.getenv("ALGOLIA_INDEX_NAME", "creva_videos")

TYPESENSE_HOST = os.getenv("TYPESENSE_HOST")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY")
TYPESENSE_COLLECTION = os.getenv("TYPESENSE_COLLECTION", "creva_videos")


def get_search_client():
    """Get the appropriate search client based on configuration."""
    if ALGOLIA_APP_ID and ALGOLIA_API_KEY:
        try:
            from algoliasearch.search_client import SearchClient
            client = SearchClient.create(ALGOLIA_APP_ID, ALGOLIA_API_KEY)
            return ("algolia", client.init_index(ALGOLIA_INDEX_NAME))
        except ImportError:
            logger.error("algoliasearch not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Algolia: {e}")
    
    if TYPESENSE_HOST and TYPESENSE_API_KEY:
        try:
            import typesense
            client = typesense.Client({
                "nodes": [{
                    "host": TYPESENSE_HOST,
                    "port": os.getenv("TYPESENSE_PORT", "8108"),
                    "protocol": os.getenv("TYPESENSE_PROTOCOL", "https"),
                }],
                "api_key": TYPESENSE_API_KEY,
                "connection_timeout_seconds": 10,
            })
            return ("typesense", client)
        except ImportError:
            logger.error("typesense not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Typesense: {e}")
    
    return (None, None)


def sync_video_to_search(event, context):
    """
    Cloud Function triggered by Firestore write events on videos collection.
    
    Syncs video data to the search index (Algolia or Typesense).
    
    Args:
        event: Firestore event data containing old and new document values
        context: Event context with resource path information
    """
    # Extract video ID from resource path
    # Format: projects/{project}/databases/(default)/documents/videos/{videoId}
    resource_path = context.resource
    video_id = resource_path.split("/")[-1]
    
    logger.info(f"Processing sync for video: {video_id}")
    
    # Get search client
    backend_type, client = get_search_client()
    
    if not client:
        logger.warning("No search backend configured, skipping sync")
        return {"status": "skipped", "reason": "No search backend configured"}
    
    # Check if this is a delete event
    old_value = event.get("oldValue", {})
    new_value = event.get("value", {})
    
    if not new_value or not new_value.get("fields"):
        # Document was deleted
        logger.info(f"Deleting video {video_id} from {backend_type} index")
        try:
            if backend_type == "algolia":
                client.delete_object(video_id)
            elif backend_type == "typesense":
                client.collections[TYPESENSE_COLLECTION].documents[video_id].delete()
            
            logger.info(f"Successfully deleted video {video_id} from {backend_type}")
            return {"status": "deleted", "video_id": video_id, "backend": backend_type}
        except Exception as e:
            logger.error(f"Failed to delete video {video_id} from {backend_type}: {e}")
            return {"status": "error", "error": str(e)}
    
    # Extract fields from Firestore document
    fields = new_value.get("fields", {})
    video_data = _extract_firestore_fields(fields)
    
    logger.info(f"Indexing video {video_id} to {backend_type}: {video_data.get('title', 'Untitled')}")
    
    try:
        if backend_type == "algolia":
            _index_to_algolia(client, video_id, video_data)
        elif backend_type == "typesense":
            _index_to_typesense(client, video_id, video_data)
        
        logger.info(f"Successfully indexed video {video_id} to {backend_type}")
        return {"status": "indexed", "video_id": video_id, "backend": backend_type}
    
    except Exception as e:
        logger.error(f"Failed to index video {video_id} to {backend_type}: {e}")
        return {"status": "error", "error": str(e)}


def _extract_firestore_fields(fields: dict) -> dict:
    """Extract values from Firestore field format."""
    result = {}
    
    for key, value in fields.items():
        if "stringValue" in value:
            result[key] = value["stringValue"]
        elif "integerValue" in value:
            result[key] = int(value["integerValue"])
        elif "doubleValue" in value:
            result[key] = float(value["doubleValue"])
        elif "booleanValue" in value:
            result[key] = value["booleanValue"]
        elif "timestampValue" in value:
            result[key] = value["timestampValue"]
        elif "arrayValue" in value:
            array_values = value["arrayValue"].get("values", [])
            result[key] = [
                v.get("stringValue", "") for v in array_values if "stringValue" in v
            ]
        elif "mapValue" in value:
            result[key] = _extract_firestore_fields(value["mapValue"].get("fields", {}))
        elif "nullValue" in value:
            result[key] = None
    
    return result


def _index_to_algolia(index, video_id: str, video_data: dict):
    """Index video to Algolia."""
    # Prepare record for Algolia
    record = {
        "objectID": video_id,
        "video_id": video_id,
        "title": video_data.get("title", ""),
        "description": video_data.get("description", ""),
        "transcript": (video_data.get("transcript", "") or "")[:9500],  # Algolia limit
        "hook": video_data.get("hook", ""),
        "format": video_data.get("format"),
        "niche": video_data.get("niche"),
        "niche_detail": video_data.get("niche_detail"),
        "secondary_niches": video_data.get("secondary_niches", []),
        "creator": video_data.get("creator"),
        "platform": video_data.get("platform"),
        "hashtags": video_data.get("hashtags", []),
        "image": video_data.get("image"),
        "save_count": video_data.get("save_count", 0),
    }
    
    # Handle timestamp
    created_at = video_data.get("created_at")
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                record["created_at_timestamp"] = int(dt.timestamp())
            elif isinstance(created_at, (int, float)):
                record["created_at_timestamp"] = int(created_at)
        except Exception:
            record["created_at_timestamp"] = 0
    
    index.save_object(record)


def _index_to_typesense(client, video_id: str, video_data: dict):
    """Index video to Typesense."""
    document = {
        "id": video_id,
        "video_id": video_id,
        "title": video_data.get("title", ""),
        "description": video_data.get("description", ""),
        "transcript": (video_data.get("transcript", "") or "")[:50000],
        "hook": video_data.get("hook", ""),
        "format": video_data.get("format") or "",
        "niche": video_data.get("niche") or "",
        "niche_detail": video_data.get("niche_detail") or "",
        "creator": video_data.get("creator") or "",
        "platform": video_data.get("platform") or "",
        "hashtags": video_data.get("hashtags") or [],
        "image": video_data.get("image") or "",
        "save_count": video_data.get("save_count", 0),
    }
    
    # Handle timestamp
    created_at = video_data.get("created_at")
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                document["created_at_timestamp"] = int(dt.timestamp())
            elif isinstance(created_at, (int, float)):
                document["created_at_timestamp"] = int(created_at)
            else:
                document["created_at_timestamp"] = 0
        except Exception:
            document["created_at_timestamp"] = 0
    else:
        document["created_at_timestamp"] = 0
    
    client.collections[TYPESENSE_COLLECTION].documents.upsert(document)


# For local testing
if __name__ == "__main__":
    # Mock event for testing
    test_event = {
        "value": {
            "fields": {
                "title": {"stringValue": "Test Video"},
                "description": {"stringValue": "A test video description"},
                "transcript": {"stringValue": "Hello this is a test transcript"},
                "hook": {"stringValue": "Hello this is a test hook"},
                "format": {"stringValue": "talking_head"},
                "niche": {"stringValue": "business"},
                "platform": {"stringValue": "tiktok"},
                "save_count": {"integerValue": "5"},
            }
        }
    }
    
    class MockContext:
        resource = "projects/test/databases/(default)/documents/videos/test123"
    
    result = sync_video_to_search(test_event, MockContext())
    print(f"Result: {result}")

