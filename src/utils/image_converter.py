import logging
import subprocess
from typing import Optional


logger = logging.getLogger(__name__)


def _is_jpeg(image_bytes: bytes) -> bool:
    """Lightweight check to determine if bytes are already JPEG."""
    if not image_bytes or len(image_bytes) < 3:
        return False
    # JPEG starts with 0xFF 0xD8 0xFF
    return image_bytes[0] == 0xFF and image_bytes[1] == 0xD8 and image_bytes[2] == 0xFF


def convert_image_to_jpeg(image_bytes: bytes) -> Optional[bytes]:
    """Convert arbitrary image bytes (e.g., HEIC/WEBP/PNG) to JPEG using ffmpeg.

    Returns JPEG bytes on success, or None on failure.
    """
    if not image_bytes:
        return None

    if _is_jpeg(image_bytes):
        return image_bytes

    try:
        # Use ffmpeg to transcode to MJPEG with good quality
        # -nostdin to avoid waiting for input on TTY-less envs
        # -f mjpeg and -qscale:v 2 for high quality JPEG
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-f",
                "mjpeg",
                "-qscale:v",
                "2",
                "pipe:1",
            ],
            input=image_bytes,
            capture_output=True,
            check=True,
        )
        if not result.stdout:
            logger.error("ffmpeg produced no output while converting to JPEG")
            return None
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed to convert image to JPEG: {e}")
        return None


