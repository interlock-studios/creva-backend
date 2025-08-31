from google import genai
from google.genai.types import HttpOptions, Part, GenerateContentConfig
from typing import Dict, Any, Optional, List
import json
import logging
import time
import random
import asyncio
from .genai_service_pool import get_genai_service_pool

logger = logging.getLogger(__name__)


class GenAIService:
    """Optimized GenAI service using connection pooling and multi-region support"""
    
    def __init__(self, config=None):
        # Get configuration
        if config is None:
            from src.services.config_validator import AppConfig
            config = AppConfig.from_env()

        self.config = config
        self.service_pool = None  # Will be initialized lazily
        
        # Backward compatibility settings
        self.model = "gemini-2.0-flash-lite"
        self.last_request_time = 0
        self.min_request_interval = config.rate_limiting.genai_min_interval
        self.max_retries = config.rate_limiting.genai_max_retries
    
    async def _get_service_pool(self):
        """Get or initialize the service pool"""
        if self.service_pool is None:
            self.service_pool = await get_genai_service_pool()
        return self.service_pool

    # Legacy methods for backward compatibility
    async def _retry_with_backoff(self, func, max_retries=None, base_delay=1):
        """Legacy retry method - now handled by service pool"""
        logger.warning("Using legacy retry method - consider updating to use service pool directly")
        if max_retries is None:
            max_retries = self.max_retries
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) reached for 429 error")
                        raise e

                    # Exponential backoff with jitter
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Got 429 error, retrying in {delay:.2f} seconds "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Non-429 error, don't retry
                    raise e
        return None

    async def _rate_limit(self):
        """Legacy rate limiting - now handled by service pool"""
        logger.debug("Using legacy rate limiting - service pool handles this more efficiently")
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.info(f"Rate limiting: waiting {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        self.last_request_time = time.time()
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """Get service pool statistics for monitoring"""
        try:
            service_pool = await self._get_service_pool()
            return service_pool.get_pool_stats()
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            return {"error": str(e)}

    async def analyze_video_with_transcript(
        self,
        video_content: bytes,
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
        prefer_region: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze video using optimized service pool with multi-region support"""
        
        try:
            service_pool = await self._get_service_pool()
            return await service_pool.analyze_video(
                video_content=video_content,
                transcript=transcript,
                caption=caption,
                localization=localization,
                prefer_region=prefer_region,
            )
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return None

    async def analyze_slideshow_with_transcript(
        self,
        slideshow_images: List[bytes],
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
        prefer_region: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze slideshow using optimized service pool with multi-region support"""
        
        try:
            service_pool = await self._get_service_pool()
            return await service_pool.analyze_slideshow(
                slideshow_images=slideshow_images,
                transcript=transcript,
                caption=caption,
                localization=localization,
                prefer_region=prefer_region,
            )
        except Exception as e:
            logger.error(f"Slideshow analysis failed: {e}")
            return None
