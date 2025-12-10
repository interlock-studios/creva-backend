"""
Video Service - Handles the global videos collection and user-specific saved videos.

This service manages:
1. `videos/{video_id}` - Global video data (AI-detected format, niche, etc.)
2. `users/{user_id}/saved_videos/{video_id}` - Per-user tags, notes, collections

The video_id is a hash of the normalized URL for deduplication.
"""

from google.cloud import firestore
from google.api_core import retry
from google.api_core import exceptions
import hashlib
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class VideoService:
    """Service for managing videos and user-specific video data in Firestore."""

    def __init__(self):
        """Initialize Firestore video service."""
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not self.project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT_ID not set. Video service will be disabled.")
            self.db = None
            return

        # Connection configuration
        self.operation_timeout = 30
        self.connection_timeout = 10

        # Configure retry policy
        self.retry_policy = retry.Retry(
            initial=1.0,
            maximum=10.0,
            multiplier=2.0,
            deadline=30.0,
            predicate=retry.if_exception_type(
                exceptions.DeadlineExceeded,
                exceptions.ServiceUnavailable,
                exceptions.InternalServerError,
            ),
        )

        try:
            self.db = firestore.Client(project=self.project_id)
            self.videos_collection = self.db.collection("videos")
            self.users_collection = self.db.collection("users")
            logger.info(f"Video service connected to Firestore in project: {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize video service: {e}")
            self.db = None

    def _normalize_url(self, url: str) -> str:
        """
        Normalize video URL to ensure consistent identification.
        Removes tracking parameters and normalizes domain.
        """
        try:
            parsed = urlparse(url.strip())

            # Parameters that don't affect video content
            ignored_params = {
                "utm_source", "utm_medium", "utm_campaign", 
                "share_id", "timestamp", "ref", "source"
            }

            if parsed.query:
                query_params = parse_qs(parsed.query)
                filtered_params = {k: v for k, v in query_params.items() if k not in ignored_params}
                normalized_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
            else:
                normalized_query = ""

            # Normalize domain
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            # Build normalized URL
            normalized = f"{domain}{parsed.path}"
            if normalized_query:
                normalized += f"?{normalized_query}"

            return normalized.rstrip("/")

        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url.strip().lower()

    def _generate_video_id(self, url: str) -> str:
        """Generate a unique video ID from the normalized URL."""
        normalized_url = self._normalize_url(url)
        return hashlib.sha256(normalized_url.encode()).hexdigest()[:16]

    async def save_video(
        self,
        url: str,
        video_data: Dict[str, Any],
        user_id: Optional[str] = None,
        user_tags: Optional[List[str]] = None,
        user_notes: Optional[str] = None,
        user_collections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Save or update a video in the global videos collection.
        Optionally save user-specific data if user_id is provided.

        Args:
            url: Original video URL
            video_data: AI-extracted video data (title, transcript, format, niche, etc.)
            user_id: Optional user ID for saving user-specific data
            user_tags: Optional user-defined tags
            user_notes: Optional user notes
            user_collections: Optional collections/folders

        Returns:
            Dict with video_id and save status
        """
        if not self.db:
            logger.warning("Video service not available")
            return {"success": False, "error": "Service unavailable"}

        video_id = self._generate_video_id(url)
        now = datetime.now(timezone.utc)

        try:
            video_ref = self.videos_collection.document(video_id)
            existing_doc = video_ref.get(timeout=self.connection_timeout)

            if existing_doc.exists:
                # Update existing video - increment save count
                video_ref.update(
                    {
                        "save_count": firestore.Increment(1),
                        "last_saved_at": now,
                    },
                    timeout=self.operation_timeout,
                    retry=self.retry_policy
                )
                logger.info(f"Updated existing video {video_id}, incremented save_count")
            else:
                # Create new video entry
                video_entry = {
                    "video_id": video_id,
                    "url": url,
                    "normalized_url": self._normalize_url(url),
                    
                    # Core content from AI extraction
                    "title": video_data.get("title"),
                    "description": video_data.get("description"),
                    "transcript": video_data.get("transcript"),
                    "hook": video_data.get("hook"),
                    "image": video_data.get("image"),
                    
                    # Classification (AI-detected)
                    "format": video_data.get("format"),
                    "niche": video_data.get("niche"),
                    "niche_detail": video_data.get("niche_detail"),
                    "secondary_niches": video_data.get("secondary_niches"),
                    
                    # Metadata
                    "creator": video_data.get("creator"),
                    "platform": video_data.get("platform"),
                    "hashtags": video_data.get("tags"),  # Original hashtags from post
                    
                    # Timestamps and stats
                    "created_at": now,
                    "last_saved_at": now,
                    "save_count": 1,
                }

                video_ref.set(
                    video_entry,
                    timeout=self.operation_timeout,
                    retry=self.retry_policy
                )
                logger.info(f"Created new video entry {video_id}")

            # Save user-specific data if user_id provided
            if user_id:
                await self._save_user_video(
                    user_id=user_id,
                    video_id=video_id,
                    user_tags=user_tags,
                    user_notes=user_notes,
                    user_collections=user_collections,
                )

            return {
                "success": True,
                "video_id": video_id,
                "is_new": not existing_doc.exists,
            }

        except Exception as e:
            logger.error(f"Error saving video {url}: {e}")
            return {"success": False, "error": str(e)}

    async def _save_user_video(
        self,
        user_id: str,
        video_id: str,
        user_tags: Optional[List[str]] = None,
        user_notes: Optional[str] = None,
        user_collections: Optional[List[str]] = None,
    ) -> bool:
        """
        Save user-specific video data (tags, notes, collections).
        
        Stored in: users/{user_id}/saved_videos/{video_id}
        """
        if not self.db:
            return False

        try:
            now = datetime.now(timezone.utc)
            user_video_ref = (
                self.users_collection
                .document(user_id)
                .collection("saved_videos")
                .document(video_id)
            )

            existing = user_video_ref.get(timeout=self.connection_timeout)

            if existing.exists:
                # Update existing user save - merge tags/collections
                existing_data = existing.to_dict()
                
                update_data = {"updated_at": now}
                
                if user_tags:
                    existing_tags = existing_data.get("user_tags", [])
                    merged_tags = list(set(existing_tags + user_tags))
                    update_data["user_tags"] = merged_tags
                
                if user_notes:
                    update_data["user_notes"] = user_notes
                
                if user_collections:
                    existing_collections = existing_data.get("collections", [])
                    merged_collections = list(set(existing_collections + user_collections))
                    update_data["collections"] = merged_collections

                user_video_ref.update(
                    update_data,
                    timeout=self.operation_timeout,
                    retry=self.retry_policy
                )
                logger.info(f"Updated user {user_id} saved video {video_id}")
            else:
                # Create new user save
                user_video_data = {
                    "video_id": video_id,
                    "user_tags": user_tags or [],
                    "user_notes": user_notes,
                    "collections": user_collections or [],
                    "saved_at": now,
                    "updated_at": now,
                }

                user_video_ref.set(
                    user_video_data,
                    timeout=self.operation_timeout,
                    retry=self.retry_policy
                )
                logger.info(f"Created user {user_id} saved video {video_id}")

            return True

        except Exception as e:
            logger.error(f"Error saving user video data: {e}")
            return False

    async def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get a video by its ID."""
        if not self.db:
            return None

        try:
            doc = self.videos_collection.document(video_id).get(
                timeout=self.connection_timeout,
                retry=self.retry_policy
            )
            
            if doc.exists:
                return {"video_id": video_id, **doc.to_dict()}
            return None

        except Exception as e:
            logger.error(f"Error getting video {video_id}: {e}")
            return None

    async def get_video_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a video by its URL."""
        video_id = self._generate_video_id(url)
        return await self.get_video(video_id)

    async def get_user_saved_video(
        self, 
        user_id: str, 
        video_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get user-specific saved video data (tags, notes, etc.)."""
        if not self.db:
            return None

        try:
            doc = (
                self.users_collection
                .document(user_id)
                .collection("saved_videos")
                .document(video_id)
                .get(timeout=self.connection_timeout, retry=self.retry_policy)
            )
            
            if doc.exists:
                return {"video_id": video_id, **doc.to_dict()}
            return None

        except Exception as e:
            logger.error(f"Error getting user saved video: {e}")
            return None

    async def get_user_saved_videos(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get all videos saved by a user."""
        if not self.db:
            return []

        try:
            query = (
                self.users_collection
                .document(user_id)
                .collection("saved_videos")
                .order_by("saved_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .offset(offset)
            )

            docs = query.stream(timeout=self.connection_timeout)
            return [{"video_id": doc.id, **doc.to_dict()} for doc in docs]

        except Exception as e:
            logger.error(f"Error getting user saved videos: {e}")
            return []

    async def update_user_tags(
        self,
        user_id: str,
        video_id: str,
        tags: List[str],
        replace: bool = False,
    ) -> bool:
        """Update user tags for a saved video."""
        if not self.db:
            return False

        try:
            user_video_ref = (
                self.users_collection
                .document(user_id)
                .collection("saved_videos")
                .document(video_id)
            )

            if replace:
                user_video_ref.update(
                    {"user_tags": tags, "updated_at": datetime.now(timezone.utc)},
                    timeout=self.operation_timeout,
                    retry=self.retry_policy
                )
            else:
                # Merge with existing tags
                existing = user_video_ref.get(timeout=self.connection_timeout)
                if existing.exists:
                    existing_tags = existing.to_dict().get("user_tags", [])
                    merged_tags = list(set(existing_tags + tags))
                    user_video_ref.update(
                        {"user_tags": merged_tags, "updated_at": datetime.now(timezone.utc)},
                        timeout=self.operation_timeout,
                        retry=self.retry_policy
                    )

            return True

        except Exception as e:
            logger.error(f"Error updating user tags: {e}")
            return False

    async def remove_user_saved_video(self, user_id: str, video_id: str) -> bool:
        """Remove a video from user's saved list (doesn't delete the global video)."""
        if not self.db:
            return False

        try:
            user_video_ref = (
                self.users_collection
                .document(user_id)
                .collection("saved_videos")
                .document(video_id)
            )

            user_video_ref.delete(
                timeout=self.operation_timeout,
                retry=self.retry_policy
            )

            # Decrement save_count on global video
            video_ref = self.videos_collection.document(video_id)
            video_ref.update(
                {"save_count": firestore.Increment(-1)},
                timeout=self.operation_timeout,
                retry=self.retry_policy
            )

            logger.info(f"Removed video {video_id} from user {user_id}'s saved list")
            return True

        except Exception as e:
            logger.error(f"Error removing user saved video: {e}")
            return False

    async def get_videos_by_format(
        self,
        format_type: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get videos filtered by format type (for basic Firestore queries)."""
        if not self.db:
            return []

        try:
            query = (
                self.videos_collection
                .where("format", "==", format_type)
                .order_by("save_count", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )

            docs = query.stream(timeout=self.connection_timeout)
            return [{"video_id": doc.id, **doc.to_dict()} for doc in docs]

        except Exception as e:
            logger.error(f"Error getting videos by format: {e}")
            return []

    async def get_videos_by_niche(
        self,
        niche: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get videos filtered by niche (for basic Firestore queries)."""
        if not self.db:
            return []

        try:
            query = (
                self.videos_collection
                .where("niche", "==", niche)
                .order_by("save_count", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )

            docs = query.stream(timeout=self.connection_timeout)
            return [{"video_id": doc.id, **doc.to_dict()} for doc in docs]

        except Exception as e:
            logger.error(f"Error getting videos by niche: {e}")
            return []

    def get_video_stats(self) -> Dict[str, Any]:
        """Get statistics about the videos collection."""
        if not self.db:
            return {"status": "disabled"}

        try:
            # Count total videos (limited for performance)
            total_count = len(list(self.videos_collection.limit(10000).stream()))

            # Get most saved videos
            top_videos = list(
                self.videos_collection
                .order_by("save_count", direction=firestore.Query.DESCENDING)
                .limit(5)
                .stream()
            )

            return {
                "status": "active",
                "total_videos": total_count,
                "top_videos": [
                    {
                        "video_id": doc.id,
                        "title": doc.to_dict().get("title"),
                        "save_count": doc.to_dict().get("save_count", 0),
                    }
                    for doc in top_videos
                ],
            }

        except Exception as e:
            logger.error(f"Error getting video stats: {e}")
            return {"status": "error", "error": str(e)}

    def is_healthy(self) -> bool:
        """Check if video service is healthy."""
        if not self.db:
            return False

        try:
            self.videos_collection.limit(1).get()
            return True
        except Exception:
            return False

