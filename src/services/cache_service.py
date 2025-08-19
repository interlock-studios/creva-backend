from google.cloud import firestore
from google.cloud.firestore import Client
import hashlib
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        """Initialize Firestore cache service"""
        # Get project ID from environment
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not self.project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT_ID not set. Cache will be disabled.")
            self.db = None
            return

        # Default TTL for cached workouts (1 week)
        self.default_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "168"))  # 24 * 7 = 168 hours

        try:
            # Initialize Firestore client
            self.db = firestore.Client(project=self.project_id)
            self.collection_name = "workout_cache"

            # Test connection by attempting to get collection reference
            self.cache_collection = self.db.collection(self.collection_name)
            logger.info(f"Connected to Firestore in project: {self.project_id}")

        except Exception as e:
            logger.warning(f"Firestore connection failed: {e}. Cache will be disabled.")
            self.db = None

    def _normalize_tiktok_url(self, url: str) -> str:
        """
        Normalize TikTok URL to ensure consistent caching.

        Examples:
        - https://www.tiktok.com/@user/video/123?param=value -> tiktok.com/@user/video/123
        - https://vm.tiktok.com/abc123/ -> vm.tiktok.com/abc123
        """
        try:
            parsed = urlparse(url.strip())

            # Remove common query parameters that don't affect video content
            ignored_params = {"utm_source", "utm_medium", "utm_campaign", "share_id", "timestamp"}

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

    def _generate_cache_key(self, tiktok_url: str, localization: Optional[str] = None) -> str:
        """Generate cache key from TikTok URL and optional localization (Firestore document ID)"""
        normalized_url = self._normalize_tiktok_url(tiktok_url)

        # Include localization in cache key if provided
        cache_input = normalized_url
        if localization:
            # Normalize localization to lowercase for consistent caching
            normalized_localization = localization.lower().strip()
            cache_input = f"{normalized_url}|{normalized_localization}"

        url_hash = hashlib.sha256(cache_input.encode()).hexdigest()[:16]
        return url_hash  # Just the hash, no prefix needed for Firestore

    async def get_cached_workout(
        self, tiktok_url: str, localization: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached workout data for a TikTok URL and localization.

        Args:
            tiktok_url: The TikTok video URL
            localization: Optional localization parameter (e.g., "Spanish", "es")

        Returns:
            Cached workout JSON if found, None otherwise
        """
        if not self.db:
            return None

        try:
            cache_key = self._generate_cache_key(tiktok_url, localization)
            doc_ref = self.cache_collection.document(cache_key)
            doc = doc_ref.get()

            if doc.exists:
                cached_data = doc.to_dict()

                # Check if document has expired
                expires_at = cached_data.get("expires_at")
                if expires_at:
                    # Convert Firestore timestamp to naive datetime for comparison
                    now = datetime.utcnow()

                    # Handle Firestore timestamp objects
                    if hasattr(expires_at, "timestamp"):
                        # Firestore timestamp - convert to datetime
                        expires_at = (
                            expires_at.replace(tzinfo=None)
                            if hasattr(expires_at, "tzinfo")
                            else expires_at
                        )
                    elif hasattr(expires_at, "tzinfo") and expires_at.tzinfo is not None:
                        # Timezone-aware datetime - make naive
                        expires_at = expires_at.replace(tzinfo=None)

                    if now > expires_at:
                        # Document expired, delete it
                        doc_ref.delete()
                        logger.info(f"Cache EXPIRED for URL: {tiktok_url[:50]}...")
                        return None

                # Log cache hit
                created_at = cached_data.get("created_at")
                localization_info = f" [{localization}]" if localization else ""
                logger.info(
                    f"Cache HIT{localization_info} for URL: {tiktok_url[:50]}... (cached at: {created_at})"
                )

                return cached_data.get("workout_json")
            else:
                localization_info = f" [{localization}]" if localization else ""
                logger.info(f"Cache MISS{localization_info} for URL: {tiktok_url[:50]}...")
                return None

        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None

    async def cache_workout(
        self,
        tiktok_url: str,
        workout_json: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        localization: Optional[str] = None,
    ) -> bool:
        """
        Cache workout data for a TikTok URL and localization.

        Args:
            tiktok_url: The TikTok video URL
            workout_json: The processed workout JSON
            metadata: Optional metadata about the video
            localization: Optional localization parameter (e.g., "Spanish", "es")

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.db:
            return False

        try:
            cache_key = self._generate_cache_key(tiktok_url, localization)

            now = datetime.utcnow()
            expires_at = now + timedelta(hours=self.default_ttl_hours)

            cache_data = {
                "workout_json": workout_json,
                "metadata": metadata or {},
                "created_at": now,
                "expires_at": expires_at,
                "tiktok_url": tiktok_url,
                "localization": localization,
                "ttl_hours": self.default_ttl_hours,
            }

            # Store in Firestore
            doc_ref = self.cache_collection.document(cache_key)
            doc_ref.set(cache_data)

            localization_info = f" [{localization}]" if localization else ""
            logger.info(
                f"Cache STORED{localization_info} for URL: {tiktok_url[:50]}... (TTL: {self.default_ttl_hours}h)"
            )
            return True

        except Exception as e:
            logger.error(f"Error caching workout: {e}")
            return False

    def invalidate_cache(self, tiktok_url: str, localization: Optional[str] = None) -> bool:
        """
        Invalidate cached workout for a specific TikTok URL and localization.

        Args:
            tiktok_url: The TikTok video URL
            localization: Optional localization parameter (e.g., "Spanish", "es")

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.db:
            return False

        try:
            cache_key = self._generate_cache_key(tiktok_url, localization)
            doc_ref = self.cache_collection.document(cache_key)

            # Check if document exists before deleting
            if doc_ref.get().exists:
                doc_ref.delete()
                localization_info = f" [{localization}]" if localization else ""
                logger.info(f"Cache INVALIDATED{localization_info} for URL: {tiktok_url[:50]}...")
                return True
            else:
                localization_info = f" [{localization}]" if localization else ""
                logger.info(
                    f"No cache entry found to invalidate{localization_info} for URL: {tiktok_url[:50]}..."
                )
                return False

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and health information"""
        if not self.db:
            return {"status": "disabled", "reason": "Firestore not connected"}

        try:
            # Get count of cached documents
            docs = self.cache_collection.limit(1000).stream()  # Limit to avoid expensive queries
            total_docs = sum(1 for _ in docs)

            # Get sample of recent documents for stats
            recent_docs = (
                self.cache_collection.order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(10)
                .stream()
            )

            recent_count = 0
            expired_count = 0
            now = datetime.utcnow()

            for doc in recent_docs:
                recent_count += 1
                data = doc.to_dict()
                expires_at = data.get("expires_at")
                if expires_at:
                    # Handle Firestore timestamp objects
                    if hasattr(expires_at, "timestamp"):
                        expires_at = (
                            expires_at.replace(tzinfo=None)
                            if hasattr(expires_at, "tzinfo")
                            else expires_at
                        )
                    elif hasattr(expires_at, "tzinfo") and expires_at.tzinfo is not None:
                        expires_at = expires_at.replace(tzinfo=None)

                    if now > expires_at:
                        expired_count += 1

            return {
                "status": "active",
                "firestore_info": {
                    "project_id": self.project_id,
                    "collection": self.collection_name,
                },
                "workout_cache": {
                    "total_cached_workouts": total_docs,
                    "recent_sample_size": recent_count,
                    "expired_in_sample": expired_count,
                    "default_ttl_hours": self.default_ttl_hours,
                },
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}

    def clear_all_workout_cache(self) -> int:
        """
        Clear all cached workout data. Use with caution!

        Returns:
            Number of documents deleted
        """
        if not self.db:
            return 0

        try:
            # Get all documents in the collection
            docs = self.cache_collection.stream()
            deleted_count = 0

            # Delete in batches to avoid timeout
            batch = self.db.batch()
            batch_size = 0

            for doc in docs:
                batch.delete(doc.reference)
                batch_size += 1
                deleted_count += 1

                # Commit batch every 500 deletes
                if batch_size >= 500:
                    batch.commit()
                    batch = self.db.batch()
                    batch_size = 0

            # Commit remaining deletions
            if batch_size > 0:
                batch.commit()

            logger.warning(f"CLEARED {deleted_count} workout cache entries")
            return deleted_count

        except Exception as e:
            logger.error(f"Error clearing workout cache: {e}")
            return 0

    def is_healthy(self) -> bool:
        """Check if cache service is healthy"""
        if not self.db:
            return False

        try:
            # Test connection by attempting to get collection reference
            self.cache_collection.limit(1).get()
            return True
        except Exception:
            return False
