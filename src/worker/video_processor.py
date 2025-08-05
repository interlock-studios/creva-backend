import ffmpeg
import tempfile
import os
from typing import Tuple
import logging

from src.services.tiktok_scraper import TikTokScraper
from src.services.instagram_scraper import InstagramScraper
from src.services.url_router import URLRouter

logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self):
        self.tiktok_scraper = TikTokScraper()
        self.instagram_scraper = InstagramScraper()
        self.url_router = URLRouter()

    async def download_video(self, url: str) -> Tuple[bytes, dict]:
        """Download video using appropriate scraper based on platform"""
        # Detect platform
        platform = self.url_router.detect_platform(url)
        
        if platform is None:
            raise ValueError(f"Unsupported URL: {url}. Only TikTok and Instagram URLs are supported.")
        
        logger.info(f"Processing {platform} video: {url}")
        
        # Use appropriate scraper
        if platform == "tiktok":
            video_content, metadata_obj, transcript_text = await self.tiktok_scraper.scrape_tiktok_complete(url)
        else:  # instagram
            video_content, metadata_obj, caption_text = await self.instagram_scraper.scrape_instagram_complete(url)
            # Instagram returns caption instead of transcript, but we'll treat it similarly
            transcript_text = caption_text

        # Convert metadata to dict format (same format for both platforms)
        metadata = {
            "platform": platform,
            "title": metadata_obj.title or "Unknown",
            "duration": metadata_obj.duration_seconds or 0,
            "uploader": metadata_obj.author or "Unknown",
            "description": metadata_obj.description or "",
            "caption": metadata_obj.caption or metadata_obj.description or "",
            "tags": metadata_obj.hashtags or [],
            "transcript_text": transcript_text,
            # Slideshow-specific metadata
            "is_slideshow": getattr(metadata_obj, 'is_slideshow', False),
            "image_count": getattr(metadata_obj, 'image_count', None),
            "slideshow_duration": getattr(metadata_obj, 'slideshow_duration', None),
        }

        return video_content, metadata

    async def remove_audio(self, video_content: bytes) -> bytes:
        """Remove audio from video"""
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as input_file:
            input_path = input_file.name
            input_file.write(video_content)

        output_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Remove audio using ffmpeg
            (
                ffmpeg.input(input_path)
                .output(
                    output_path,
                    an=None,  # Remove audio
                    vcodec="copy",  # Copy video codec
                    movflags="faststart",
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Read output
            with open(output_path, "rb") as f:
                silent_video = f.read()

            return silent_video

        finally:
            # Clean up
            try:
                os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except Exception:
                pass
