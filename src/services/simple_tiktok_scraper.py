import httpx
import structlog
from typing import Dict, Any, Optional, Tuple
import os
from urllib.parse import quote

from src.models.parser_result import VideoMetadata
from src.utils.retry import exponential_backoff

logger = structlog.get_logger()


class SimpleTikTokScraper:
    """
    Simplified TikTok scraper using ScrapCreators API
    No more yt-dlp complexity - just API calls
    """
    
    def __init__(self):
        self.api_key = os.getenv("SCRAPECREATORS_API_KEY", "TqHKAnqkrYcEQDRFDf2mjyPawR43")
        self.base_url = "https://api.scrapecreators.com/v2/tiktok/video"
        self.timeout = 30
        
    @exponential_backoff(max_retries=3, base_delay=2.0)
    async def fetch_tiktok_data(self, url: str) -> Dict[str, Any]:
        """
        Fetch TikTok data using ScrapCreators API
        
        Returns raw API response with all video data
        """
        encoded_url = quote(url, safe='')
        api_url = f"{self.base_url}?url={encoded_url}&get_transcript=true&trim=true"
        
        headers = {
            "x-api-key": self.api_key,
            "User-Agent": "TikTok-Parser/1.0"
        }
        
        logger.info("Fetching TikTok data", url=url, api_url=api_url)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or 'aweme_detail' not in data:
                raise Exception("Invalid API response - missing aweme_detail")
                
            logger.info(
                "TikTok data fetched successfully",
                aweme_id=data['aweme_detail']['aweme_id'],
                desc_length=len(data['aweme_detail'].get('desc', '')),
                has_video=bool(data['aweme_detail'].get('video'))
            )
            
            return data
    
    def extract_metadata(self, api_data: Dict[str, Any]) -> VideoMetadata:
        """Extract metadata from ScrapCreators API response"""
        aweme = api_data['aweme_detail']
        video_info = aweme.get('video', {})
        stats = aweme.get('statistics', {})
        
        # Extract hashtags from description
        description = aweme.get('desc', '') or ''
        hashtags = self._extract_hashtags(description)
        
        # Calculate duration from video info (convert from milliseconds)
        duration_ms = video_info.get('duration', 0)
        duration_seconds = duration_ms / 1000 if duration_ms else None
        
        return VideoMetadata(
            title=description[:100] + "..." if len(description) > 100 else description,
            description=description,
            caption=description,
            author=aweme.get('author', {}).get('nickname'),
            author_id=aweme.get('author', {}).get('unique_id'),
            duration_seconds=duration_seconds,
            view_count=stats.get('play_count'),
            like_count=stats.get('digg_count'),
            comment_count=stats.get('comment_count'),
            share_count=stats.get('share_count'),
            upload_date=None,  # Not directly available in this format
            hashtags=hashtags if hashtags else None,
            sound_title=aweme.get('music', {}).get('title'),
            sound_author=aweme.get('music', {}).get('author'),
            file_size_bytes=None  # Will be set after download
        )
    
    def get_video_download_url(self, api_data: Dict[str, Any]) -> str:
        """Get the best video download URL (no watermark)"""
        video_info = api_data['aweme_detail'].get('video', {})
        
        # Try no-watermark download first
        download_no_wm = video_info.get('download_no_watermark_addr', {})
        if download_no_wm and download_no_wm.get('url_list'):
            logger.info("Using no-watermark video URL")
            return download_no_wm['url_list'][0]
        
        # Fallback to regular play address
        play_addr = video_info.get('play_addr', {})
        if play_addr and play_addr.get('url_list'):
            logger.info("Using regular play address (may have watermark)")
            return play_addr['url_list'][0]
        
        raise Exception("No video download URL found in API response")
    
    def get_transcript_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Get audio transcript URL if available"""
        # ScrapCreators API includes transcript in play_addr for audio extraction
        video_info = api_data['aweme_detail'].get('video', {})
        play_addr = video_info.get('play_addr', {})
        
        if play_addr and play_addr.get('url_list'):
            # The same video URL can be used for audio extraction
            return play_addr['url_list'][0]
        
        return None
    
    @exponential_backoff(max_retries=3, base_delay=1.0)
    async def download_video_content(self, download_url: str) -> bytes:
        """Download video content from URL"""
        logger.info("Downloading video content", url=download_url)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/"
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(download_url, headers=headers)
            response.raise_for_status()
            
            content = response.content
            size_mb = len(content) / (1024 * 1024)
            
            logger.info(
                "Video downloaded successfully",
                size_mb=round(size_mb, 2),
                content_type=response.headers.get('content-type')
            )
            
            return content
    
    async def scrape_tiktok_complete(self, url: str) -> Tuple[bytes, VideoMetadata, Optional[str]]:
        """
        Complete TikTok scraping workflow
        
        Returns:
            Tuple of (video_content, metadata, transcript_url)
        """
        # Fetch all data from API
        api_data = await self.fetch_tiktok_data(url)
        
        # Extract metadata
        metadata = self.extract_metadata(api_data)
        
        # Get download URLs
        video_url = self.get_video_download_url(api_data)
        transcript_url = self.get_transcript_url(api_data)
        
        # Download video content
        video_content = await self.download_video_content(video_url)
        
        # Update metadata with file size
        metadata.file_size_bytes = len(video_content)
        
        logger.info(
            "TikTok scraping completed",
            title=metadata.title[:50] + "..." if len(metadata.title or "") > 50 else metadata.title,
            author=metadata.author,
            duration=metadata.duration_seconds,
            size_mb=round(len(video_content) / (1024 * 1024), 2)
        )
        
        return video_content, metadata, transcript_url
    
    def _extract_hashtags(self, text: str) -> list[str]:
        """Extract hashtags from text"""
        import re
        hashtag_pattern = r'#\w+'
        hashtags = re.findall(hashtag_pattern, text)
        return list(set(hashtags))  # Remove duplicates
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get scraper stats for monitoring"""
        return {
            "scraper_type": "scrapecreators_api",
            "api_key_configured": bool(self.api_key),
            "timeout_seconds": self.timeout,
            "base_url": self.base_url
        }