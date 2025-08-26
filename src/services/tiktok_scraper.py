import httpx
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple, List
import os
from urllib.parse import urlparse
import re
from dataclasses import dataclass


from src.models.parser_result import VideoMetadata, SlideshowImage


"""
Enhanced TikTok Scraper using ScrapeCreators API

This module provides a robust TikTok scraping service with comprehensive error handling,
retry logic, and best practices for production use.

Features:
- URL validation and normalization
- Exponential backoff retry logic
- Comprehensive error handling with custom exceptions
- Rate limiting and timeout handling
- Logging for monitoring and debugging
- Support for transcripts
- Video content downloading

Usage Examples:

Basic usage:
    scraper = TikTokScraper()

    # Get video info only (no video download)
    info = await scraper.get_video_info("https://www.tiktok.com/@user/video/123")

    # Complete scraping (video + metadata + transcript)
    video_content, metadata, transcript = await scraper.scrape_tiktok_complete(
        "https://www.tiktok.com/@user/video/123"
    )

Advanced usage with options:
    options = ScrapingOptions(
        get_transcript=True,
        trim_response=True,
        max_retries=5,
        timeout=60
    )

    try:
        video_content, metadata, transcript = await scraper.scrape_tiktok_complete(
            "https://www.tiktok.com/@user/video/123",
            options
        )
    except ValidationError as e:
        logger.error(f"Invalid URL: {e}")
    except APIError as e:
        logger.error(f"API error: {e}, Status: {e.status_code}")
    except NetworkError as e:
        logger.error(f"Network error: {e}")

Environment Variables:
    SCRAPECREATORS_API_KEY: Your ScrapeCreators API key (required)

API Endpoints Used:
    - https://api.scrapecreators.com/v2/tiktok/video (main endpoint including transcript)
"""

# Configure logging
logger = logging.getLogger(__name__)


class TikTokScraperError(Exception):
    """Base exception for TikTok scraper errors"""

    pass


class APIError(TikTokScraperError):
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


class ValidationError(TikTokScraperError):
    """Input validation errors"""

    pass


class NetworkError(TikTokScraperError):
    """Network related errors"""

    pass


@dataclass
class ScrapingOptions:
    """Options for TikTok scraping"""

    get_transcript: bool = True
    trim_response: bool = True
    max_retries: int = 3
    timeout: int = 30


class TikTokScraper:
    def __init__(self):
        """Initialize TikTok scraper with API key validation"""
        self.api_key = os.getenv("SCRAPECREATORS_API_KEY")

        # Validate required environment variables
        if not self.api_key or self.api_key == "your_actual_api_key_here":
            raise ValueError(
                "SCRAPECREATORS_API_KEY environment variable is required and must be set to a valid API key. "
                "Please update your .env file with your actual ScrapeCreators API key."
            )

        self.base_url = "https://api.scrapecreators.com/v2/tiktok/video"
        logger.info("TikTok scraper initialized with API key validation")

        # Default headers for all requests
        self.default_headers = {
            "x-api-key": self.api_key,
            "User-Agent": "TikTokScraper/1.0",
            "Accept": "application/json",
        }

    def _validate_tiktok_url(self, url: str) -> str:
        """Validate and normalize TikTok URL"""
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

        # Check if it's a TikTok URL
        valid_domains = [
            "tiktok.com",
            "www.tiktok.com",
            "vm.tiktok.com",
            "m.tiktok.com",
        ]
        if parsed.netloc.lower() not in valid_domains:
            logger.warning(f"URL domain '{parsed.netloc}' is not a recognized TikTok domain")

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

    async def scrape_tiktok_complete(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Tuple[bytes, VideoMetadata, Optional[str]]:
        """Complete TikTok scraping - video, metadata, and transcript"""
        if options is None:
            options = ScrapingOptions()

        logger.info(f"Starting complete TikTok scraping for URL: {url}")

        try:
            # Get metadata
            api_data = await self.fetch_tiktok_data(url, options)
            metadata = self.extract_metadata(api_data)

            # Handle slideshow vs video content
            if metadata.is_slideshow:
                # For slideshows, we'll return the first image as the main content
                # and store all images in metadata
                slideshow_images = await self.download_slideshow_images(api_data)

                # Use the first image as the main content, or empty bytes if no images
                video_content = (
                    slideshow_images[0] if slideshow_images and slideshow_images[0] else b""
                )

                logger.info(
                    f"Successfully scraped TikTok slideshow. {len(slideshow_images)} images downloaded"
                )
            else:
                # Regular video handling
                video_url = self.get_video_download_url(api_data)
                video_content = await self.download_video_content(video_url)

                logger.info(
                    f"Successfully scraped TikTok video. Video size: {len(video_content)} bytes"
                )

            # Get transcript if requested
            transcript = None
            if options.get_transcript:
                transcript = self._extract_transcript_from_response(api_data)

            logger.info(f"Transcript: {'Yes' if transcript else 'No'}")
            return video_content, metadata, transcript

        except Exception as e:
            logger.error(f"Failed to scrape TikTok content: {e}")
            raise

    async def fetch_tiktok_data(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Dict[str, Any]:
        """
        Fetch TikTok data from ScrapCreators API with enhanced error handling and retry logic.

        Args:
            url: TikTok video URL
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
        validated_url = self._validate_tiktok_url(url)
        logger.info(f"Fetching TikTok data for URL: {validated_url}")

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
                        if data.get("status_code", 0) != 0:
                            error_msg = data.get("status_msg", "Unknown API error")
                            raise APIError(f"API returned error: {error_msg}", response.status_code)

                        # Validate required fields
                        if "aweme_detail" not in data:
                            raise APIError("Missing 'aweme_detail' in response")

                        logger.info(
                            f"Successfully fetched TikTok data. Response size: {len(response.content)} bytes"
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
                    raise APIError("Forbidden - insufficient permissions", response.status_code)
                elif response.status_code == 404:
                    raise APIError("Video not found or unavailable", response.status_code)
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
            logger.exception(f"Unexpected error fetching TikTok data: {e}")
            raise APIError(f"Unexpected error: {e}")

    # Keep the old method signature for backward compatibility
    async def fetch_tiktok_data_simple(self, url: str) -> Dict[str, Any]:
        """Simplified method for backward compatibility"""
        return await self.fetch_tiktok_data(url, ScrapingOptions())

    def _extract_transcript_from_response(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract and clean transcript from the video info API response.

        Args:
            api_data: The API response data

        Returns:
            Cleaned transcript text or None if not available
        """
        try:
            # First try to get transcript from the root level
            transcript = api_data.get("transcript")

            # If not found at root, try to extract from cla_info
            if not transcript:
                aweme_detail = api_data.get("aweme_detail", {})
                video_info = aweme_detail.get("video", {})
                cla_info = video_info.get("cla_info", {})
                caption_infos = cla_info.get("caption_infos", [])

                # Look for English transcript in caption_infos
                for caption_info in caption_infos:
                    if (
                        caption_info.get("language_code") == "en"
                        or caption_info.get("lang") == "eng-US"
                    ):
                        # We could fetch from the URL, but since transcript is at root level,
                        # this is just a fallback that won't be used in practice
                        break

            if transcript:
                cleaned_transcript = self._clean_transcript(transcript)
                if cleaned_transcript:
                    logger.info(
                        f"Successfully extracted transcript from response. Length: {len(cleaned_transcript)} characters"
                    )
                    return cleaned_transcript
                else:
                    logger.info("Transcript found but empty after cleaning")
                    return None
            else:
                logger.info("No transcript found in response")
                return None

        except Exception as e:
            logger.warning(f"Error extracting transcript from response: {e}")
            return None

    def _clean_transcript(self, transcript: str) -> str:
        """Clean up WEBVTT format transcript"""
        if not transcript:
            return ""

        # Handle WEBVTT format
        if transcript.startswith("WEBVTT"):
            lines = transcript.split("\n")
            text_lines = []
            for line in lines:
                line = line.strip()
                # Skip empty lines, timestamps, and WEBVTT headers
                if (
                    not line
                    or "-->" in line
                    or line.startswith("WEBVTT")
                    or line.isdigit()
                    or re.match(r"^\d{2}:\d{2}:\d{2}", line)
                ):
                    continue
                text_lines.append(line)
            transcript = " ".join(text_lines)

        return transcript.strip()

    async def get_video_info(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Dict[str, Any]:
        """
        Get TikTok video information without downloading video content.

        This is a lightweight method that only fetches metadata and optionally transcript.

        Args:
            url: TikTok video URL
            options: Scraping options (defaults to ScrapingOptions())

        Returns:
            Dict containing video metadata and optional transcript

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
            api_data = await self.fetch_tiktok_data(url, options)

            # Extract structured metadata
            metadata = self.extract_metadata(api_data)

            # Get transcript if requested
            transcript = None
            if options.get_transcript:
                transcript = self._extract_transcript_from_response(api_data)

            # Return structured response
            result = {
                "metadata": metadata.__dict__,
                "transcript": transcript,
                "raw_api_data": api_data if not options.trim_response else None,
            }

            # Only add video_download_url for regular videos, not slideshows
            if not metadata.is_slideshow:
                result["video_download_url"] = self.get_video_download_url(api_data)

            logger.info(
                f"Successfully fetched video info. Transcript: {'Yes' if transcript else 'No'}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to fetch video info: {e}")
            raise

    def extract_metadata(self, api_data: Dict[str, Any]) -> VideoMetadata:
        """Extract metadata from API response, handling both videos and slideshows"""
        aweme = api_data["aweme_detail"]
        video_info = aweme.get("video", {})
        stats = aweme.get("statistics", {})
        description = aweme.get("desc", "") or ""

        # Extract hashtags
        hashtags = re.findall(r"#\w+", description)

        # Check if this is a slideshow (image post)
        image_post_info = aweme.get("image_post_info")
        is_slideshow = image_post_info is not None

        slideshow_images = None
        slideshow_duration = None
        image_count = None
        duration_seconds = None

        if is_slideshow:
            # Extract slideshow-specific data
            slideshow_images = self._extract_slideshow_images(image_post_info)
            image_count = len(slideshow_images) if slideshow_images else 0
            # Calculate total slideshow duration (if available)
            slideshow_duration = (
                image_post_info.get("video", {}).get("duration", 0) / 1000
                if image_post_info.get("video")
                else None
            )
            duration_seconds = slideshow_duration
            logger.info(f"Detected slideshow with {image_count} images")
        else:
            # Regular video - extract duration
            duration_ms = video_info.get("duration", 0)
            duration_seconds = duration_ms / 1000 if duration_ms else None

        return VideoMetadata(
            title=description[:100] + "..." if len(description) > 100 else description,
            description=description,
            caption=description,
            author=aweme.get("author", {}).get("nickname"),
            author_id=aweme.get("author", {}).get("unique_id"),
            duration_seconds=duration_seconds,
            view_count=stats.get("play_count"),
            like_count=stats.get("digg_count"),
            comment_count=stats.get("comment_count"),
            share_count=stats.get("share_count"),
            upload_date=None,
            hashtags=list(set(hashtags)) if hashtags else None,
            sound_title=aweme.get("music", {}).get("title"),
            sound_author=aweme.get("music", {}).get("author"),
            file_size_bytes=None,
            # Slideshow-specific fields
            is_slideshow=is_slideshow,
            slideshow_images=slideshow_images,
            slideshow_duration=slideshow_duration,
            image_count=image_count,
        )

    def _extract_slideshow_images(self, image_post_info: Dict[str, Any]) -> List[SlideshowImage]:
        """Extract slideshow images from image_post_info"""
        images = []

        # Extract images from image_post_info
        images_data = image_post_info.get("images", [])

        for i, img_data in enumerate(images_data):
            # Look for different resolution options, prefer higher quality
            image_url = None
            width = None
            height = None

            # Try to get the best quality image URL
            url_list = img_data.get("display_image", {}).get("url_list", [])
            if not url_list:
                # Fallback to thumb
                url_list = img_data.get("thumb", {}).get("url_list", [])

            if url_list:
                image_url = url_list[0]  # Take the first URL

                # Extract dimensions if available
                width = img_data.get("display_image", {}).get("width")
                height = img_data.get("display_image", {}).get("height")

                if not width or not height:
                    # Fallback to thumb dimensions
                    width = img_data.get("thumb", {}).get("width")
                    height = img_data.get("thumb", {}).get("height")

                images.append(SlideshowImage(url=image_url, width=width, height=height, index=i))

        logger.info(f"Extracted {len(images)} slideshow images")
        return images

    def get_video_download_url(self, api_data: Dict[str, Any]) -> str:
        """Get no-watermark video URL (for regular videos only)"""
        aweme = api_data["aweme_detail"]

        # Check if this is a slideshow
        if aweme.get("image_post_info"):
            # For slideshows, return the slideshow video URL if available
            slideshow_video = aweme.get("image_post_info", {}).get("video", {})
            if slideshow_video and slideshow_video.get("play_addr", {}).get("url_list"):
                return slideshow_video["play_addr"]["url_list"][0]
            else:
                raise Exception("This is a slideshow - use get_slideshow_images() instead")

        # Regular video handling
        video_info = aweme.get("video", {})

        # Try no-watermark first
        download_no_wm = video_info.get("download_no_watermark_addr", {})
        if download_no_wm and download_no_wm.get("url_list"):
            return download_no_wm["url_list"][0]

        # Fallback to regular
        play_addr = video_info.get("play_addr", {})
        if play_addr and play_addr.get("url_list"):
            return play_addr["url_list"][0]

        raise Exception("No video download URL found")

    def get_slideshow_images(self, api_data: Dict[str, Any]) -> List[SlideshowImage]:
        """Get slideshow images from API response"""
        aweme = api_data["aweme_detail"]
        image_post_info = aweme.get("image_post_info")

        if not image_post_info:
            raise Exception("This is not a slideshow")

        return self._extract_slideshow_images(image_post_info)

    async def download_video_content(self, download_url: str) -> bytes:
        """Download video content"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(download_url, headers=headers)
            response.raise_for_status()
            return response.content

    async def download_slideshow_images(self, api_data: Dict[str, Any]) -> List[bytes]:
        """Download all images from a slideshow"""
        slideshow_images = self.get_slideshow_images(api_data)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        }

        image_contents = []

        async with httpx.AsyncClient(timeout=60) as client:
            for img in slideshow_images:
                try:
                    response = await client.get(img.url, headers=headers)
                    response.raise_for_status()
                    image_contents.append(response.content)
                    logger.info(
                        f"Downloaded slideshow image {img.index + 1}/{len(slideshow_images)}"
                    )
                except Exception as e:
                    logger.error(f"Failed to download slideshow image {img.index}: {e}")
                    # Add empty bytes as placeholder to maintain order
                    image_contents.append(b"")

        logger.info(
            f"Downloaded {len([c for c in image_contents if c])} out of {len(slideshow_images)} slideshow images"
        )
        return image_contents

    async def scrape_tiktok_slideshow(
        self, url: str, options: Optional[ScrapingOptions] = None
    ) -> Tuple[List[bytes], VideoMetadata, Optional[str]]:
        """Specialized method for scraping TikTok slideshows"""
        if options is None:
            options = ScrapingOptions()

        logger.info(f"Starting TikTok slideshow scraping for URL: {url}")

        try:
            # Get metadata
            api_data = await self.fetch_tiktok_data(url, options)
            metadata = self.extract_metadata(api_data)

            if not metadata.is_slideshow:
                raise Exception(
                    "URL does not contain a slideshow - use scrape_tiktok_complete() for regular videos"
                )

            # Download all slideshow images
            slideshow_images = await self.download_slideshow_images(api_data)

            # Get transcript if requested
            transcript = None
            if options.get_transcript:
                transcript = self._extract_transcript_from_response(api_data)

            logger.info(
                f"Successfully scraped TikTok slideshow. {len(slideshow_images)} images downloaded, Transcript: {'Yes' if transcript else 'No'}"
            )
            return slideshow_images, metadata, transcript

        except Exception as e:
            logger.error(f"Failed to scrape TikTok slideshow: {e}")
            raise
