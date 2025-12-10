"""
Search Service - Provides fast full-text search across the global video library.

This service abstracts the search backend, supporting:
1. Algolia - Fastest setup, great for production (free tier: 10K searches/month)
2. Typesense - Self-hosted, free at scale
3. Firestore fallback - Basic queries when no search service configured

The search index contains:
- Full-text search on: title, description, transcript, hook
- Faceted filtering by: format, niche, platform, creator
- Sorted by: save_count, created_at

Usage:
    search_service = SearchService()
    results = await search_service.search(
        query="fitness hooks",
        format="voiceover",
        niche="fitness",
        limit=20
    )
"""

import logging
import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class SearchBackend(ABC):
    """Abstract base class for search backends."""
    
    @abstractmethod
    async def index_video(self, video_id: str, video_data: Dict[str, Any]) -> bool:
        """Add or update a video in the search index."""
        pass
    
    @abstractmethod
    async def delete_video(self, video_id: str) -> bool:
        """Remove a video from the search index."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query: Optional[str] = None,
        format: Optional[str] = None,
        niche: Optional[str] = None,
        platform: Optional[str] = None,
        creator: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search videos with optional filters."""
        pass
    
    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if the search backend is healthy."""
        pass


class AlgoliaBackend(SearchBackend):
    """Algolia search backend implementation."""
    
    def __init__(self):
        self.app_id = os.getenv("ALGOLIA_APP_ID")
        self.api_key = os.getenv("ALGOLIA_API_KEY")
        self.index_name = os.getenv("ALGOLIA_INDEX_NAME", "creva_videos")
        self.client = None
        self.index = None
        
        if self.app_id and self.api_key:
            try:
                from algoliasearch.search_client import SearchClient
                self.client = SearchClient.create(self.app_id, self.api_key)
                self.index = self.client.init_index(self.index_name)
                
                # Configure index settings for optimal search
                self.index.set_settings({
                    "searchableAttributes": [
                        "title",
                        "hook",
                        "transcript",
                        "description",
                        "creator",
                    ],
                    "attributesForFaceting": [
                        "filterOnly(format)",
                        "filterOnly(niche)",
                        "filterOnly(platform)",
                        "filterOnly(creator)",
                        "searchable(niche_detail)",
                    ],
                    "customRanking": [
                        "desc(save_count)",
                        "desc(created_at_timestamp)",
                    ],
                    "attributesToRetrieve": [
                        "video_id",
                        "title",
                        "description",
                        "hook",
                        "format",
                        "niche",
                        "niche_detail",
                        "creator",
                        "platform",
                        "save_count",
                        "image",
                    ],
                })
                logger.info(f"Algolia backend initialized with index: {self.index_name}")
            except ImportError:
                logger.warning("algoliasearch package not installed. Run: pip install algoliasearch")
            except Exception as e:
                logger.error(f"Failed to initialize Algolia: {e}")
    
    async def index_video(self, video_id: str, video_data: Dict[str, Any]) -> bool:
        if not self.index:
            return False
        
        try:
            # Prepare record for Algolia
            record = {
                "objectID": video_id,
                "video_id": video_id,
                "title": video_data.get("title", ""),
                "description": video_data.get("description", ""),
                "transcript": video_data.get("transcript", "")[:9500] if video_data.get("transcript") else "",  # Algolia limit
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
                "created_at_timestamp": video_data.get("created_at").timestamp() if video_data.get("created_at") else 0,
            }
            
            self.index.save_object(record)
            logger.debug(f"Indexed video {video_id} in Algolia")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index video {video_id} in Algolia: {e}")
            return False
    
    async def delete_video(self, video_id: str) -> bool:
        if not self.index:
            return False
        
        try:
            self.index.delete_object(video_id)
            logger.debug(f"Deleted video {video_id} from Algolia")
            return True
        except Exception as e:
            logger.error(f"Failed to delete video {video_id} from Algolia: {e}")
            return False
    
    async def search(
        self,
        query: Optional[str] = None,
        format: Optional[str] = None,
        niche: Optional[str] = None,
        platform: Optional[str] = None,
        creator: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        if not self.index:
            return {"hits": [], "total": 0, "error": "Algolia not configured"}
        
        try:
            # Build filter string
            filters = []
            if format:
                filters.append(f"format:{format}")
            if niche:
                filters.append(f"niche:{niche}")
            if platform:
                filters.append(f"platform:{platform}")
            if creator:
                filters.append(f"creator:{creator}")
            
            search_params = {
                "hitsPerPage": limit,
                "page": offset // limit if limit > 0 else 0,
            }
            
            if filters:
                search_params["filters"] = " AND ".join(filters)
            
            result = self.index.search(query or "", search_params)
            
            return {
                "hits": result.get("hits", []),
                "total": result.get("nbHits", 0),
                "page": result.get("page", 0),
                "pages": result.get("nbPages", 0),
            }
            
        except Exception as e:
            logger.error(f"Algolia search failed: {e}")
            return {"hits": [], "total": 0, "error": str(e)}
    
    def is_healthy(self) -> bool:
        return self.index is not None


class TypesenseBackend(SearchBackend):
    """Typesense search backend implementation."""
    
    def __init__(self):
        self.host = os.getenv("TYPESENSE_HOST", "localhost")
        self.port = os.getenv("TYPESENSE_PORT", "8108")
        self.protocol = os.getenv("TYPESENSE_PROTOCOL", "http")
        self.api_key = os.getenv("TYPESENSE_API_KEY")
        self.collection_name = os.getenv("TYPESENSE_COLLECTION", "creva_videos")
        self.client = None
        
        if self.api_key:
            try:
                import typesense
                self.client = typesense.Client({
                    "nodes": [{
                        "host": self.host,
                        "port": self.port,
                        "protocol": self.protocol,
                    }],
                    "api_key": self.api_key,
                    "connection_timeout_seconds": 10,
                })
                
                # Create collection if it doesn't exist
                self._ensure_collection()
                logger.info(f"Typesense backend initialized with collection: {self.collection_name}")
            except ImportError:
                logger.warning("typesense package not installed. Run: pip install typesense")
            except Exception as e:
                logger.error(f"Failed to initialize Typesense: {e}")
    
    def _ensure_collection(self):
        """Create the collection schema if it doesn't exist."""
        if not self.client:
            return
        
        schema = {
            "name": self.collection_name,
            "fields": [
                {"name": "video_id", "type": "string"},
                {"name": "title", "type": "string"},
                {"name": "description", "type": "string", "optional": True},
                {"name": "transcript", "type": "string", "optional": True},
                {"name": "hook", "type": "string", "optional": True},
                {"name": "format", "type": "string", "facet": True, "optional": True},
                {"name": "niche", "type": "string", "facet": True, "optional": True},
                {"name": "niche_detail", "type": "string", "optional": True},
                {"name": "creator", "type": "string", "facet": True, "optional": True},
                {"name": "platform", "type": "string", "facet": True, "optional": True},
                {"name": "hashtags", "type": "string[]", "optional": True},
                {"name": "image", "type": "string", "optional": True},
                {"name": "save_count", "type": "int32", "optional": True},
                {"name": "created_at_timestamp", "type": "int64", "optional": True},
            ],
            "default_sorting_field": "save_count",
        }
        
        try:
            self.client.collections[self.collection_name].retrieve()
        except Exception:
            # Collection doesn't exist, create it
            try:
                self.client.collections.create(schema)
                logger.info(f"Created Typesense collection: {self.collection_name}")
            except Exception as e:
                logger.error(f"Failed to create Typesense collection: {e}")
    
    async def index_video(self, video_id: str, video_data: Dict[str, Any]) -> bool:
        if not self.client:
            return False
        
        try:
            document = {
                "id": video_id,
                "video_id": video_id,
                "title": video_data.get("title", ""),
                "description": video_data.get("description", ""),
                "transcript": (video_data.get("transcript", "") or "")[:50000],  # Typesense limit
                "hook": video_data.get("hook", ""),
                "format": video_data.get("format") or "",
                "niche": video_data.get("niche") or "",
                "niche_detail": video_data.get("niche_detail") or "",
                "creator": video_data.get("creator") or "",
                "platform": video_data.get("platform") or "",
                "hashtags": video_data.get("hashtags") or [],
                "image": video_data.get("image") or "",
                "save_count": video_data.get("save_count", 0),
                "created_at_timestamp": int(video_data.get("created_at").timestamp()) if video_data.get("created_at") else 0,
            }
            
            self.client.collections[self.collection_name].documents.upsert(document)
            logger.debug(f"Indexed video {video_id} in Typesense")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index video {video_id} in Typesense: {e}")
            return False
    
    async def delete_video(self, video_id: str) -> bool:
        if not self.client:
            return False
        
        try:
            self.client.collections[self.collection_name].documents[video_id].delete()
            logger.debug(f"Deleted video {video_id} from Typesense")
            return True
        except Exception as e:
            logger.error(f"Failed to delete video {video_id} from Typesense: {e}")
            return False
    
    async def search(
        self,
        query: Optional[str] = None,
        format: Optional[str] = None,
        niche: Optional[str] = None,
        platform: Optional[str] = None,
        creator: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        if not self.client:
            return {"hits": [], "total": 0, "error": "Typesense not configured"}
        
        try:
            # Build filter string
            filters = []
            if format:
                filters.append(f"format:={format}")
            if niche:
                filters.append(f"niche:={niche}")
            if platform:
                filters.append(f"platform:={platform}")
            if creator:
                filters.append(f"creator:={creator}")
            
            search_params = {
                "q": query or "*",
                "query_by": "title,hook,transcript,description",
                "per_page": limit,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "sort_by": "save_count:desc,created_at_timestamp:desc",
            }
            
            if filters:
                search_params["filter_by"] = " && ".join(filters)
            
            result = self.client.collections[self.collection_name].documents.search(search_params)
            
            return {
                "hits": [hit["document"] for hit in result.get("hits", [])],
                "total": result.get("found", 0),
                "page": result.get("page", 1) - 1,
                "pages": (result.get("found", 0) + limit - 1) // limit if limit > 0 else 0,
            }
            
        except Exception as e:
            logger.error(f"Typesense search failed: {e}")
            return {"hits": [], "total": 0, "error": str(e)}
    
    def is_healthy(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.health.retrieve()
            return True
        except Exception:
            return False


class FirestoreBackend(SearchBackend):
    """
    Firestore fallback backend for basic queries.
    Limited functionality - no full-text search, only filter queries.
    """
    
    def __init__(self):
        from src.services.video_service import VideoService
        self.video_service = VideoService()
        logger.info("Using Firestore fallback for search (limited functionality)")
    
    async def index_video(self, video_id: str, video_data: Dict[str, Any]) -> bool:
        # Videos are already in Firestore via VideoService
        return True
    
    async def delete_video(self, video_id: str) -> bool:
        # Deletion handled by VideoService
        return True
    
    async def search(
        self,
        query: Optional[str] = None,
        format: Optional[str] = None,
        niche: Optional[str] = None,
        platform: Optional[str] = None,
        creator: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Basic Firestore query - limited to filter queries only.
        No full-text search capability.
        """
        try:
            # Priority: format > niche > platform (Firestore only supports one inequality filter)
            if format:
                videos = await self.video_service.get_videos_by_format(format, limit=limit)
            elif niche:
                videos = await self.video_service.get_videos_by_niche(niche, limit=limit)
            else:
                # Get recent videos
                if not self.video_service.db:
                    return {"hits": [], "total": 0, "error": "Firestore not available"}
                
                docs = (
                    self.video_service.videos_collection
                    .order_by("save_count", direction="DESCENDING")
                    .limit(limit)
                    .offset(offset)
                    .stream()
                )
                videos = [{"video_id": doc.id, **doc.to_dict()} for doc in docs]
            
            # Apply additional filters in memory (not ideal but works for fallback)
            if platform:
                videos = [v for v in videos if v.get("platform") == platform]
            if creator:
                videos = [v for v in videos if v.get("creator") == creator]
            
            # Basic text search in memory (very limited)
            if query:
                query_lower = query.lower()
                videos = [
                    v for v in videos
                    if query_lower in (v.get("title", "") or "").lower()
                    or query_lower in (v.get("hook", "") or "").lower()
                    or query_lower in (v.get("description", "") or "").lower()
                ]
            
            return {
                "hits": videos,
                "total": len(videos),
                "page": 0,
                "pages": 1,
                "warning": "Using Firestore fallback - limited search functionality",
            }
            
        except Exception as e:
            logger.error(f"Firestore search failed: {e}")
            return {"hits": [], "total": 0, "error": str(e)}
    
    def is_healthy(self) -> bool:
        return self.video_service.is_healthy()


class SearchService:
    """
    Main search service that auto-selects the best available backend.
    
    Priority:
    1. Algolia (if configured)
    2. Typesense (if configured)
    3. Firestore fallback
    """
    
    def __init__(self):
        self.backend: SearchBackend = self._select_backend()
        self.backend_name = self.backend.__class__.__name__
        logger.info(f"Search service initialized with backend: {self.backend_name}")
    
    def _select_backend(self) -> SearchBackend:
        """Select the best available search backend."""
        
        # Try Algolia first
        if os.getenv("ALGOLIA_APP_ID") and os.getenv("ALGOLIA_API_KEY"):
            backend = AlgoliaBackend()
            if backend.is_healthy():
                return backend
            logger.warning("Algolia configured but not healthy, falling back")
        
        # Try Typesense
        if os.getenv("TYPESENSE_API_KEY"):
            backend = TypesenseBackend()
            if backend.is_healthy():
                return backend
            logger.warning("Typesense configured but not healthy, falling back")
        
        # Fall back to Firestore
        return FirestoreBackend()
    
    async def index_video(self, video_id: str, video_data: Dict[str, Any]) -> bool:
        """Add or update a video in the search index."""
        return await self.backend.index_video(video_id, video_data)
    
    async def delete_video(self, video_id: str) -> bool:
        """Remove a video from the search index."""
        return await self.backend.delete_video(video_id)
    
    async def search(
        self,
        query: Optional[str] = None,
        format: Optional[str] = None,
        niche: Optional[str] = None,
        platform: Optional[str] = None,
        creator: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Search videos with optional filters.
        
        Args:
            query: Full-text search query
            format: Filter by video format (e.g., 'voiceover', 'talking_head')
            niche: Filter by content niche (e.g., 'fitness', 'business')
            platform: Filter by platform ('tiktok' or 'instagram')
            creator: Filter by creator username
            limit: Number of results to return (default 20)
            offset: Pagination offset
        
        Returns:
            Dict with 'hits', 'total', 'page', 'pages', and optionally 'error' or 'warning'
        """
        result = await self.backend.search(
            query=query,
            format=format,
            niche=niche,
            platform=platform,
            creator=creator,
            limit=limit,
            offset=offset,
        )
        
        # Add backend info
        result["backend"] = self.backend_name
        
        return result
    
    def get_available_formats(self) -> List[str]:
        """Get list of available video formats for filtering."""
        from src.services.genai_service import VIDEO_FORMATS
        return VIDEO_FORMATS
    
    def get_available_niches(self) -> List[str]:
        """Get list of available content niches for filtering."""
        from src.services.genai_service import CONTENT_NICHES
        return CONTENT_NICHES
    
    def is_healthy(self) -> bool:
        """Check if search service is healthy."""
        return self.backend.is_healthy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get search service status."""
        return {
            "backend": self.backend_name,
            "healthy": self.is_healthy(),
            "features": {
                "full_text_search": self.backend_name != "FirestoreBackend",
                "faceted_filtering": True,
                "relevance_ranking": self.backend_name != "FirestoreBackend",
            },
        }

