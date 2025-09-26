import httpx
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
import os
from urllib.parse import urlparse
import re
from dataclasses import dataclass

from src.models.parser_result import VideoMetadata


"""
Instagram Scraper using ScrapeCreators API

This module provides a robust Instagram scraping service with comprehensive error handling,
retry logic, and best practices for production use.

Features:
- URL validation and normalization
- Exponential backoff retry logic
- Comprehensive error handling with custom exceptions
- Rate limiting and timeout handling
- Logging for monitoring and debugging
- Support for posts and reels
- Video content downloading

Environment Variables:
    SCRAPECREATORS_API_KEY: Your ScrapeCreators API key (required)

API Endpoints Used:
    - https://api.scrapecreators.com/v1/instagram/post (for posts and reels)
"""

# Configure logging
logger = logging.getLogger(__name__)


class InstagramScraperError(Exception):
    """Base exception for Instagram scraper errors"""

    pass


class APIError(InstagramScraperError):
    """API related errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ValidationError(InstagramScraperError):
    """Input validation errors"""

    pass


class NetworkError(InstagramScraperError):
    """Network related errors"""

    pass


@dataclass
class ScrapingOptions:
    """Options for Instagram scraping"""

    trim_response: bool = True
    max_retries: int = 3
    timeout: int = 30


class InstagramScraper:
    def __init__(self):
        """Initialize Instagram scraper with API key validation"""
        self.api_key = os.getenv("SCRAPECREATORS_API_KEY")

        # Validate required environment variables
        if not self.api_key or self.api_key == "your_actual_api_key_here":
            raise ValueError(
                "SCRAPECREATORS_API_KEY environment variable is required and must be set to a valid API key. "
                "Please update your .env file with your actual ScrapeCreators API key."
            )
        
        # Clean the API key to prevent header issues (remove whitespace and newlines)
        self.api_key = self.api_key.strip()

        self.base_url = "https://api.scrapecreators.com/v1/instagram/post"
        logger.info("Instagram scraper initialized with API key validation")

        # Default headers for all requests
        self.default_headers = {
            "x-api-key": self.api_key,
            "User-Agent": "InstagramScraper/1.0",
            "Accept": "application/json",
        }

    def _validate_instagram_url(self, url: str) -> str:
        """Validate and normalize Instagram URL"""
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")

        url = url.strip()
        if not url:
            raise ValidationError("URL cannot be empty")

        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
                parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}")

        # Check if it's an Instagram URL
        valid_domains = [
            "instagram.com",
            "www.instagram.com",
            "instagr.am",
            "www.instagr.am",
        ]
        if parsed.netloc.lower() not in valid_domains:
            raise ValidationError(
                f"URL domain '{parsed.netloc}' is not a recognized Instagram domain"
            )

        # Check if it's a valid Instagram post/reel URL pattern
        path = parsed.path
        valid_patterns = [
            r"^/p/[A-Za-z0-9_-]+/?$",  # Post URL
            r"^/reel/[A-Za-z0-9_-]+/?$",  # Reel URL
            r"^/reels?/[A-Za-z0-9_-]+/?$",  # Alternative reel URL
        ]

        if not any(re.match(pattern, path) for pattern in valid_patterns):
            logger.warning(f"URL path '{path}' doesn't match expected Instagram post/reel patterns")

        return url

    async def _make_request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        """Make HTTP request with exponential backoff retry logic"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                else:
                    response = await client.request(method, url, headers=headers, params=params)

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < max_retries:
                        logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        continue

                # Check for temporary server errors
                if 500 <= response.status_code < 600 and attempt < max_retries:
                    wait_time = (2**attempt) + 1  # Exponential backoff
                    logger.warning(
                        f"Server error {response.status_code}. Retrying in {wait_time} seconds..."
                    )
                    await asyncio.sleep(wait_time)
                    continue

                return response

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = (2**attempt) + 1
                    logger.warning(
                        f"Network error on attempt {attempt + 1}: {e}. Retrying in {wait_time} seconds..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                break

        # If we get here, all retries failed
        if last_exception:
            raise NetworkError(f"Request failed after {max_retries + 1} attempts: {last_exception}")
        else:
            raise NetworkError(f"Request failed after {max_retries + 1} attempts")

    async def scrape_instagram_complete(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Tuple[bytes, VideoMetadata, Optional[str]]:
        """Complete Instagram scraping - video, metadata, and caption"""
        if options is None:
            options = ScrapingOptions()

        logger.info(f"Starting complete Instagram scraping for URL: {url}")

        try:
            # Get post/reel metadata
            api_data = await self.fetch_instagram_data(url, options)
            metadata = self.extract_metadata(api_data)

            # Download video
            video_url = self.get_video_download_url(api_data)
            video_content = await self.download_video_content(video_url)

            # Caption is already in metadata
            caption = metadata.caption

            logger.info(
                f"Successfully scraped Instagram video. Video size: {len(video_content)} bytes"
            )
            return video_content, metadata, caption

        except Exception as e:
            logger.error(f"Failed to scrape Instagram video: {e}")
            raise

    async def fetch_instagram_data(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Dict[str, Any]:
        """
        Fetch Instagram data from ScrapCreators API with enhanced error handling and retry logic.

        Args:
            url: Instagram post or reel URL
            options: Scraping options (defaults to ScrapingOptions())

        Returns:
            Dict containing the API response data

        Raises:
            ValidationError: If URL is invalid
            APIError: If API returns an error
            NetworkError: If network request fails
        """
        if options is None:
            options = ScrapingOptions()

        # Validate and normalize URL
        validated_url = self._validate_instagram_url(url)
        logger.info(f"Fetching Instagram data for URL: {validated_url}")

        # Prepare request parameters
        params = {"url": validated_url, "trim": str(options.trim_response).lower()}

        try:
            async with httpx.AsyncClient(timeout=options.timeout) as client:
                response = await self._make_request_with_retry(
                    client=client,
                    method="GET",
                    url=self.base_url,
                    headers=self.default_headers,
                    params=params,
                    max_retries=options.max_retries,
                )

                # Handle different response status codes
                if response.status_code == 200:
                    try:
                        data = response.json()

                        # Validate response structure
                        if not isinstance(data, dict):
                            raise APIError("Invalid response format: expected JSON object")

                        # Check for API-level errors
                        # Instagram API returns errors with a "message" field
                        if "message" in data and "data" not in data:
                            error_msg = data.get("message", "Unknown API error")
                            raise APIError(f"API returned error: {error_msg}", response.status_code)

                        # Validate required fields
                        if "data" not in data:
                            raise APIError("Missing 'data' in response")

                        logger.info(
                            f"Successfully fetched Instagram data. Response size: {len(response.content)} bytes"
                        )
                        return data

                    except ValueError as e:
                        raise APIError(
                            f"Invalid JSON response: {e}",
                            response.status_code,
                            response.text[:500],
                        )

                elif response.status_code == 400:
                    raise APIError(
                        "Bad request - invalid URL or parameters",
                        response.status_code,
                        response.text[:500],
                    )
                elif response.status_code == 401:
                    raise APIError("Unauthorized - check your API key", response.status_code)
                elif response.status_code == 403:
                    raise APIError(f"Forbidden - insufficient permissions (API key issue or rate limit). Response: {response.text[:200]}", response.status_code)
                elif response.status_code == 404:
                    raise APIError("Post/Reel not found or unavailable", response.status_code)
                elif response.status_code == 429:
                    raise APIError("Rate limit exceeded", response.status_code)
                else:
                    raise APIError(
                        f"HTTP {response.status_code}: {response.reason_phrase}",
                        response.status_code,
                        response.text[:500],
                    )

        except httpx.TimeoutException:
            raise NetworkError(f"Request timed out after {options.timeout} seconds")
        except httpx.NetworkError as e:
            raise NetworkError(f"Network error: {e}")
        except (APIError, NetworkError, ValidationError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error fetching Instagram data: {e}")
            raise APIError(f"Unexpected error: {e}")

    async def get_video_info(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Dict[str, Any]:
        """
        Get Instagram video information without downloading video content.

        This is a lightweight method that only fetches metadata.

        Args:
            url: Instagram post or reel URL
            options: Scraping options (defaults to ScrapingOptions())

        Returns:
            Dict containing video metadata

        Raises:
            ValidationError: If URL is invalid
            APIError: If API returns an error
            NetworkError: If network request fails
        """
        if options is None:
            options = ScrapingOptions()

        logger.info(f"Fetching video info for URL: {url}")

        try:
            # Get video metadata from API
            api_data = await self.fetch_instagram_data(url, options)

            # Extract structured metadata
            metadata = self.extract_metadata(api_data)

            # Return structured response
            result = {
                "metadata": metadata.__dict__,
                "raw_api_data": api_data if not options.trim_response else None,
                "video_download_url": self.get_video_download_url(api_data),
            }

            logger.info("Successfully fetched video info")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch video info: {e}")
            raise

    def extract_metadata(self, api_data: Dict[str, Any]) -> VideoMetadata:
        """Extract metadata from API response"""
        media_data = api_data["data"]["xdt_shortcode_media"]

        # Extract caption/description
        caption_edges = media_data.get("edge_media_to_caption", {}).get("edges", [])
        caption = ""
        if caption_edges:
            caption = caption_edges[0].get("node", {}).get("text", "")

        # Extract hashtags from caption
        hashtags = re.findall(r"#\w+", caption) if caption else []

        # Owner info
        owner = media_data.get("owner", {})

        # Stats
        like_count = media_data.get("edge_media_preview_like", {}).get("count", 0)
        comment_count = media_data.get("edge_media_to_parent_comment", {}).get("count", 0)
        view_count = media_data.get("video_view_count", 0)

        # Duration (in seconds)
        duration_seconds = media_data.get("video_duration")

        # Timestamp
        taken_at = media_data.get("taken_at_timestamp")

        # Extract music info if available
        music_info = media_data.get("clips_music_attribution_info", {})
        sound_title = music_info.get("song_name")
        sound_author = music_info.get("artist_name")

        return VideoMetadata(
            title=caption[:100] + "..." if len(caption) > 100 else caption,
            description=caption,
            caption=caption,
            author=owner.get("full_name") or owner.get("username"),
            author_id=owner.get("username"),
            duration_seconds=duration_seconds,
            view_count=view_count,
            like_count=like_count,
            comment_count=comment_count,
            share_count=None,  # Instagram doesn't provide share count in this API
            upload_date=None,  # Could convert timestamp if needed
            hashtags=list(set(hashtags)) if hashtags else None,
            sound_title=sound_title,
            sound_author=sound_author,
            file_size_bytes=None,
        )

    def get_video_download_url(self, api_data: Dict[str, Any]) -> str:
        """Get video URL from API response"""
        media_data = api_data["data"]["xdt_shortcode_media"]

        # Check if it's a video
        if not media_data.get("is_video", False):
            raise APIError("Content is not a video")

        # Get video URL
        video_url = media_data.get("video_url")
        if not video_url:
            raise APIError("No video URL found in response")

        return video_url

    async def download_video_content(self, download_url: str) -> bytes:
        """Download video content"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.instagram.com/",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(download_url, headers=headers)
            response.raise_for_status()
            return response.content
