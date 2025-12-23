from google.cloud import firestore
from google.cloud.firestore import Client
from google.api_core import retry
from google.api_core import exceptions
import hashlib
import logging
import os
import asyncio
import time
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

        # Default TTL for cached content (365 days - video content is immutable)
        # If Joe saves a video Dec 10, Stacy saves same video April 15 = instant cache hit
        self.default_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "8760"))  # 24 * 365 = 8760 hours
        
        # Connection configuration with more aggressive timeouts
        self.operation_timeout = 30  # 30 seconds for operations
        self.connection_timeout = 10  # 10 seconds for initial connection
        
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
                self.collection_name = "parser_cache"
                self.cache_collection = self.db.collection(self.collection_name)
                
                # Test connection with a very simple operation and short timeout
                try:
                    # Just test if we can access the collection (no actual read/write)
                    test_doc_ref = self.cache_collection.document("__connection_test__")
                    # This is a lightweight operation that just creates a reference
                    logger.info(f"Firestore client initialized successfully for project: {self.project_id}")
                    return self.db
                except Exception as test_error:
                    logger.warning(f"Firestore connection test failed (attempt {attempt + 1}): {test_error}")
                    if attempt == max_attempts - 1:
                        raise test_error

            except Exception as e:
                wait_time = min(2 ** attempt, 8)  # Exponential backoff, max 8 seconds
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Firestore initialization attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"All Firestore initialization attempts failed: {e}. Cache will be disabled.")
                    return None

        return None

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

    async def get_cached_video(
        self, tiktok_url: str, localization: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached video data for a TikTok URL and localization.

        Args:
            tiktok_url: The TikTok video URL
            localization: Optional localization parameter (e.g., "Spanish", "es")

        Returns:
            Cached video JSON if found, None otherwise
        """
        if not self.db:
            return None

        try:
            cache_key = self._generate_cache_key(tiktok_url, localization)
            doc_ref = self.cache_collection.document(cache_key)
            
            # Use shorter timeout and retry policy to prevent long hangs
            doc = doc_ref.get(timeout=self.connection_timeout, retry=self.retry_policy)

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

                return cached_data.get("video_data")
            else:
                localization_info = f" [{localization}]" if localization else ""
                logger.info(f"Cache MISS{localization_info} for URL: {tiktok_url[:50]}...")
                return None

        except exceptions.DeadlineExceeded as e:
            logger.error(f"Cache retrieval timeout after {self.connection_timeout}s for URL: {tiktok_url[:50]}... - {e}")
            return None
        except exceptions.ServiceUnavailable as e:
            logger.error(f"Firestore service unavailable for cache retrieval: {e}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None

    async def cache_video(
        self,
        tiktok_url: str,
        video_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        localization: Optional[str] = None,
    ) -> bool:
        """
        Cache video data for a TikTok URL and localization.

        Args:
            tiktok_url: The TikTok video URL
            video_data: The processed video JSON
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
                "video_data": video_data,
                "metadata": metadata or {},
                "created_at": now,
                "expires_at": expires_at,
                "tiktok_url": tiktok_url,
                "localization": localization,
                "ttl_hours": self.default_ttl_hours,
            }

            # Store in Firestore with timeout and retry
            doc_ref = self.cache_collection.document(cache_key)
            doc_ref.set(cache_data, timeout=self.operation_timeout, retry=self.retry_policy)

            localization_info = f" [{localization}]" if localization else ""
            logger.info(
                f"Cache STORED{localization_info} for URL: {tiktok_url[:50]}... (TTL: {self.default_ttl_hours}h)"
            )
            return True

        except exceptions.DeadlineExceeded as e:
            logger.error(f"Cache storage timeout after {self.operation_timeout}s for URL: {tiktok_url[:50]}... - {e}")
            return False
        except exceptions.ServiceUnavailable as e:
            logger.error(f"Firestore service unavailable for cache storage: {e}")
            return False
        except Exception as e:
            logger.error(f"Error caching bucket list: {e}")
            return False

    def invalidate_cache(self, tiktok_url: str, localization: Optional[str] = None) -> bool:
        """
        Invalidate cached video for a specific TikTok URL and localization.

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
                "video_cache": {
                    "total_cached_videos": total_docs,
                    "recent_sample_size": recent_count,
                    "expired_in_sample": expired_count,
                    "default_ttl_hours": self.default_ttl_hours,
                },
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}

    def clear_all_video_cache(self) -> int:
        """
        Clear all cached video data. Use with caution!

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

            logger.warning(f"CLEARED {deleted_count} video cache entries")
            return deleted_count

        except Exception as e:
            logger.error(f"Error clearing video cache: {e}")
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
    
    def get_cache_stats_sync(self) -> Dict[str, Any]:
        """Synchronous version of get_cache_stats"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.get_cache_stats())
        except RuntimeError:
            # If no event loop is running, create a new one
            return asyncio.run(self.get_cache_stats())
