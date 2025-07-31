import ffmpeg
import tempfile
import os
from typing import Tuple

from src.services.tiktok_scraper import TikTokScraper


class VideoProcessor:
    def __init__(self):
        self.scraper = TikTokScraper()

    async def download_video(self, url: str) -> Tuple[bytes, dict]:
        """Download video using ScrapCreators API"""
        video_content, metadata_obj, transcript_text = await self.scraper.scrape_tiktok_complete(
            url
        )

        # Convert metadata to dict format
        metadata = {
            "title": metadata_obj.title or "Unknown",
            "duration": metadata_obj.duration_seconds or 0,
            "uploader": metadata_obj.author or "Unknown",
            "description": metadata_obj.description or "",
            "caption": metadata_obj.caption or metadata_obj.description or "",
            "tags": metadata_obj.hashtags or [],
            "transcript_text": transcript_text,
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
