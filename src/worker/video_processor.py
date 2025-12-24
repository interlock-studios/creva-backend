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
    VideoProcessingError,
    VideoDownloadError,
    VideoFormatError,
    UnsupportedPlatformError,
    TikTokAPIError,
    InstagramAPIError,
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
                detected_platform=None,
            )

        logger.info(f"Processing {platform} video: {url}")

        # For Instagram, check if it's a slideshow first
        if platform == "instagram":
            try:
                # Get metadata first to check if it's a slideshow
                api_data = await self.instagram_scraper.fetch_instagram_data(url)
                metadata_obj = self.instagram_scraper.extract_metadata(api_data)
                
                if metadata_obj.is_slideshow:
                    # It's a slideshow, return empty video content and metadata
                    logger.info(f"Detected Instagram slideshow with {metadata_obj.image_count} images")
                    
                    metadata = {
                        "platform": platform,
                        "title": metadata_obj.title or "Unknown",
                        "duration": metadata_obj.duration_seconds or 0,
                        "uploader": metadata_obj.author or "Unknown",
                        "description": metadata_obj.description or "",
                        "caption": metadata_obj.caption or metadata_obj.description or "",
                        "tags": metadata_obj.hashtags or [],
                        "transcript_text": None,  # Instagram slideshows don't have transcripts
                        # Slideshow-specific metadata
                        "is_slideshow": True,
                        "image_count": metadata_obj.image_count,
                        "slideshow_duration": metadata_obj.slideshow_duration,
                    }
                    
                    # Return empty video content for slideshows
                    return b"", metadata
                else:
                    # It's a regular video, proceed with normal video download
                    # Pass api_data to avoid duplicate API call
                    video_content, metadata_obj, caption_text = await self.instagram_scraper.scrape_instagram_complete(url, api_data=api_data)
                    # Instagram doesn't have WebVTT transcripts, just caption text
                    transcript_text_or_data = caption_text
                    
            except Exception as e:
                raise InstagramAPIError(
                    message=f"Failed to download Instagram content: {str(e)}", url=url, cause=e
                )
        else:
            # TikTok handling
            try:
                video_content, metadata_obj, transcript_text_or_data = await self.tiktok_scraper.scrape_tiktok_complete(url)
            except Exception as e:
                raise TikTokAPIError(
                    message=f"Failed to download TikTok video: {str(e)}", url=url, cause=e
                )

        # Handle transcript data (can be dict with text/segments or None)
        transcript_text = None
        transcript_segments = None
        if isinstance(transcript_text_or_data, dict):
            transcript_text = transcript_text_or_data.get("text")
            transcript_segments = transcript_text_or_data.get("segments")
        elif transcript_text_or_data:
            transcript_text = transcript_text_or_data

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
            "transcript_segments": transcript_segments,
            # Slideshow-specific metadata
            "is_slideshow": getattr(metadata_obj, "is_slideshow", False),
            "image_count": getattr(metadata_obj, "image_count", None),
            "slideshow_duration": getattr(metadata_obj, "slideshow_duration", None),
        }

        return video_content, metadata

    async def remove_audio(self, video_content: bytes) -> bytes:
        """Remove audio from video with guaranteed cleanup"""
        with self.temp_file(suffix=".mp4") as input_path, self.temp_file(
            suffix=".mp4"
        ) as output_path:

            # Write input video
            try:
                with open(input_path, "wb") as f:
                    f.write(video_content)
            except IOError as e:
                logger.error(f"Failed to write input video file: {e}")
                raise VideoProcessingError(message=f"Failed to write video content: {e}", cause=e)

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
                            format_info="Empty output after audio removal",
                        )

                    logger.debug(f"Successfully processed video: {len(silent_video)} bytes")
                    return silent_video

                except IOError as e:
                    logger.error(f"Failed to read processed video file: {e}")
                    raise VideoProcessingError(
                        message=f"Failed to read processed video: {e}", cause=e
                    )

            except ffmpeg.Error as e:
                stderr_output = e.stderr.decode() if e.stderr else "No error details"
                logger.error(f"FFmpeg processing failed: {stderr_output}")
                raise VideoFormatError(
                    message=f"Video processing failed: {stderr_output}",
                    format_info="FFmpeg processing error",
                    cause=e,
                )
            except Exception as e:
                logger.error(f"Unexpected error during video processing: {e}")
                raise VideoProcessingError(message=f"Video processing failed: {str(e)}", cause=e)

        # Temp files automatically cleaned up by context managers

    async def extract_first_frame(self, video_content: bytes) -> bytes:
        """Extract first frame from video as JPEG

        Args:
            video_content: Raw video bytes

        Returns:
            JPEG bytes of the first frame

        Raises:
            VideoProcessingError: If frame extraction fails
        """
        with self.temp_file(suffix=".mp4") as input_path, self.temp_file(
            suffix=".jpg"
        ) as output_path:

            # Write input video
            try:
                with open(input_path, "wb") as f:
                    f.write(video_content)
            except IOError as e:
                logger.error(f"Failed to write input video file: {e}")
                raise VideoProcessingError(message=f"Failed to write video content: {e}", cause=e)

            # Extract first frame using ffmpeg
            try:
                (
                    ffmpeg.input(input_path)
                    .output(
                        output_path,
                        vframes=1,  # Extract only 1 frame
                        f="image2",  # Force image output format
                        vcodec="mjpeg",  # Use JPEG codec
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )

                # Read the extracted frame
                try:
                    with open(output_path, "rb") as f:
                        frame_data = f.read()

                    if not frame_data:
                        raise VideoFormatError(
                            message="FFmpeg produced empty frame file",
                            format_info="Empty output after frame extraction",
                        )

                    logger.debug(f"Successfully extracted first frame: {len(frame_data)} bytes")
                    return frame_data

                except IOError as e:
                    logger.error(f"Failed to read extracted frame file: {e}")
                    raise VideoProcessingError(
                        message=f"Failed to read extracted frame: {e}", cause=e
                    )

            except ffmpeg.Error as e:
                stderr_output = e.stderr.decode() if e.stderr else "No error details"
                logger.error(f"FFmpeg frame extraction failed: {stderr_output}")
                raise VideoFormatError(
                    message=f"Frame extraction failed: {stderr_output}",
                    format_info="FFmpeg frame extraction error",
                    cause=e,
                )
            except Exception as e:
                logger.error(f"Unexpected error during frame extraction: {e}")
                raise VideoProcessingError(message=f"Frame extraction failed: {str(e)}", cause=e)

    async def extract_image_from_slideshow(self, images: list[bytes], index: int = 0) -> bytes:
        """Extract a specific image from slideshow

        Args:
            images: List of image bytes from slideshow
            index: Index of image to extract (default: 0 for first image)

        Returns:
            JPEG bytes of the requested image

        Raises:
            VideoProcessingError: If image extraction fails
            IndexError: If index is out of bounds
        """
        if not images:
            raise VideoProcessingError(message="No images provided in slideshow")

        if index < 0 or index >= len(images):
            raise IndexError(f"Image index {index} out of bounds (0-{len(images)-1})")

        # Return the requested image directly (already in bytes format)
        image_data = images[index]

        if not image_data:
            raise VideoProcessingError(message=f"Image at index {index} is empty")

        logger.debug(f"Extracted image {index} from slideshow: {len(image_data)} bytes")
        return image_data
