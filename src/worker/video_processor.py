import ffmpeg
import tempfile
import os
from typing import Tuple, Generator
import logging
from contextlib import contextmanager
import shutil

from src.services.tiktok_scraper import TikTokScraper
from src.services.instagram_scraper import InstagramScraper
from src.services.url_router import URLRouter
from src.exceptions import (
    VideoProcessingError, VideoDownloadError, VideoFormatError, 
    UnsupportedPlatformError, TikTokAPIError, InstagramAPIError
)

logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self):
        self.tiktok_scraper = TikTokScraper()
        self.instagram_scraper = InstagramScraper()
        self.url_router = URLRouter()

    @contextmanager
    def temp_file(self, suffix: str = ".mp4") -> Generator[str, None, None]:
        """Context manager for temporary files with guaranteed cleanup"""
        temp_fd = None
        temp_path = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
            os.close(temp_fd)  # Close file descriptor, keep path
            logger.debug(f"Created temp file: {temp_path}")
            yield temp_path
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temp file: {temp_path}")
                except OSError as e:
                    logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")

    @contextmanager
    def temp_directory(self) -> Generator[str, None, None]:
        """Context manager for temporary directories with guaranteed cleanup"""
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="video_processing_")
            logger.debug(f"Created temp directory: {temp_dir}")
            yield temp_dir
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except OSError as e:
                    logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")

    async def download_video(self, url: str) -> Tuple[bytes, dict]:
        """Download video using appropriate scraper based on platform"""
        # Detect platform
        platform = self.url_router.detect_platform(url)

        if platform is None:
            raise UnsupportedPlatformError(
                message=f"Unsupported URL: {url}. Only TikTok and Instagram URLs are supported.",
                url=url,
                detected_platform=None
            )

        logger.info(f"Processing {platform} video: {url}")

        # Use appropriate scraper
        try:
            if platform == "tiktok":
                video_content, metadata_obj, transcript_text = (
                    await self.tiktok_scraper.scrape_tiktok_complete(url)
                )
            else:  # instagram
                video_content, metadata_obj, caption_text = (
                    await self.instagram_scraper.scrape_instagram_complete(url)
                )
                # Instagram returns caption instead of transcript, but we'll treat it similarly
                transcript_text = caption_text
        except Exception as e:
            if platform == "tiktok":
                raise TikTokAPIError(
                    message=f"Failed to download TikTok video: {str(e)}",
                    url=url,
                    cause=e
                )
            else:
                raise InstagramAPIError(
                    message=f"Failed to download Instagram video: {str(e)}",
                    url=url,
                    cause=e
                )

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
            "is_slideshow": getattr(metadata_obj, "is_slideshow", False),
            "image_count": getattr(metadata_obj, "image_count", None),
            "slideshow_duration": getattr(metadata_obj, "slideshow_duration", None),
        }

        return video_content, metadata

    async def remove_audio(self, video_content: bytes) -> bytes:
        """Remove audio from video with guaranteed cleanup"""
        with self.temp_file(suffix=".mp4") as input_path, \
             self.temp_file(suffix=".mp4") as output_path:
            
            # Write input video
            try:
                with open(input_path, "wb") as f:
                    f.write(video_content)
            except IOError as e:
                logger.error(f"Failed to write input video file: {e}")
                raise VideoProcessingError(
                    message=f"Failed to write video content: {e}",
                    cause=e
                )
            
            # Process with ffmpeg
            try:
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
                try:
                    with open(output_path, "rb") as f:
                        silent_video = f.read()
                    
                    if not silent_video:
                        raise VideoFormatError(
                            message="FFmpeg produced empty output file",
                            format_info="Empty output after audio removal"
                        )
                    
                    logger.debug(f"Successfully processed video: {len(silent_video)} bytes")
                    return silent_video
                    
                except IOError as e:
                    logger.error(f"Failed to read processed video file: {e}")
                    raise VideoProcessingError(
                        message=f"Failed to read processed video: {e}",
                        cause=e
                    )
                    
            except ffmpeg.Error as e:
                stderr_output = e.stderr.decode() if e.stderr else "No error details"
                logger.error(f"FFmpeg processing failed: {stderr_output}")
                raise VideoFormatError(
                    message=f"Video processing failed: {stderr_output}",
                    format_info="FFmpeg processing error",
                    cause=e
                )
            except Exception as e:
                logger.error(f"Unexpected error during video processing: {e}")
                raise VideoProcessingError(
                    message=f"Video processing failed: {str(e)}",
                    cause=e
                )
        
        # Temp files automatically cleaned up by context managers
