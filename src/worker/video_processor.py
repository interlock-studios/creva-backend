import ffmpeg
from pydub import AudioSegment
import tempfile
import os
import structlog
from typing import List, Tuple, Optional, Dict, Any
import subprocess
import io

from src.services.simple_tiktok_scraper import SimpleTikTokScraper

logger = structlog.get_logger()


class VideoProcessor:
    def __init__(self):
        self.max_size_mb = 100
        self.max_duration_s = 180
        self.max_frames = 100
        self.scraper = SimpleTikTokScraper()
    
    async def download_video(self, url: str) -> Tuple[bytes, dict]:
        """
        Simplified video download using ScrapCreators API
        No more yt-dlp complexity!
        """
        try:
            # Use simplified scraper to get video content and metadata
            video_content, metadata_obj, transcript_url = await self.scraper.scrape_tiktok_complete(url)
            
            # Check size constraints
            size_mb = len(video_content) / (1024 * 1024)
            if size_mb > self.max_size_mb:
                raise Exception(f"Video too large: {size_mb:.1f}MB > {self.max_size_mb}MB")
            
            # Convert metadata object to dict format expected by pipeline
            metadata = {
                'title': metadata_obj.title or 'Unknown',
                'duration': metadata_obj.duration_seconds or 0,
                'uploader': metadata_obj.author or 'Unknown',
                'description': metadata_obj.description or '',
                'caption': metadata_obj.caption or metadata_obj.description or '',
                'tags': metadata_obj.hashtags or [],
                'size_bytes': len(video_content),
                'view_count': metadata_obj.view_count,
                'like_count': metadata_obj.like_count,
                'comment_count': metadata_obj.comment_count,
                'share_count': metadata_obj.share_count,
                'sound_title': metadata_obj.sound_title,
                'sound_author': metadata_obj.sound_author,
                'transcript_url': transcript_url  # Store for potential future use
            }
            
            logger.info(
                "Video downloaded via ScrapCreators API",
                title=metadata['title'][:50] + "..." if len(metadata['title']) > 50 else metadata['title'],
                duration=metadata['duration'],
                size_mb=size_mb,
                author=metadata['uploader']
            )
            
            return video_content, metadata
        
        except Exception as e:
            logger.error("Video download failed", url=url, error=str(e))
            raise
    
    async def extract_keyframes(self, video_content: bytes) -> List[bytes]:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, "input.mp4")
                output_pattern = os.path.join(temp_dir, "keyframe_%04d.jpg")
                
                # Write video to temp file
                with open(input_path, 'wb') as f:
                    f.write(video_content)
                
                # Extract keyframes using ffmpeg
                (
                    ffmpeg
                    .input(input_path)
                    .filter('select', 'gt(scene,0.3)')
                    .filter('fps', fps=1)
                    .output(output_pattern, vframes=self.max_frames)
                    .overwrite_output()
                    .run(quiet=True)
                )
                
                # Read extracted keyframes
                keyframes = []
                for filename in sorted(os.listdir(temp_dir)):
                    if filename.startswith('keyframe_') and filename.endswith('.jpg'):
                        filepath = os.path.join(temp_dir, filename)
                        with open(filepath, 'rb') as f:
                            keyframes.append(f.read())
                
                logger.info("Keyframes extracted", count=len(keyframes))
                return keyframes
        
        except Exception as e:
            logger.error("Keyframe extraction failed", error=str(e))
            raise
    
    async def detect_speech(self, video_content: bytes) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(video_content)
                temp_video_path = temp_video.name
            
            try:
                # Extract audio using ffmpeg
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                    temp_audio_path = temp_audio.name
                
                (
                    ffmpeg
                    .input(temp_video_path)
                    .output(temp_audio_path, acodec='pcm_s16le', ac=1, ar='16000')
                    .overwrite_output()
                    .run(quiet=True)
                )
                
                # Load audio with pydub
                audio = AudioSegment.from_wav(temp_audio_path)
                
                # Detect speech by analyzing non-silent segments
                non_silent_segments = audio.split_on_silence(
                    min_silence_len=500,  # 500ms of silence
                    silence_thresh=audio.dBFS - 16,
                    keep_silence=100
                )
                
                total_speech_duration = sum(len(segment) for segment in non_silent_segments)
                has_speech = total_speech_duration >= 5000  # At least 5 seconds of speech
                
                logger.info(
                    "Speech detection completed",
                    has_speech=has_speech,
                    speech_duration_ms=total_speech_duration,
                    segments_count=len(non_silent_segments)
                )
                
                return has_speech
            
            finally:
                # Cleanup temp files
                if os.path.exists(temp_video_path):
                    os.unlink(temp_video_path)
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
        
        except Exception as e:
            logger.error("Speech detection failed", error=str(e))
            raise
    
    async def extract_audio(self, video_content: bytes) -> bytes:
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(video_content)
                temp_video_path = temp_video.name
            
            try:
                with tempfile.NamedTemporaryFile(suffix='.opus', delete=False) as temp_audio:
                    temp_audio_path = temp_audio.name
                
                # Extract audio in OPUS format for Speech-to-Text
                (
                    ffmpeg
                    .input(temp_video_path)
                    .output(
                        temp_audio_path,
                        acodec='libopus',
                        ac=1,
                        ar='48000',
                        format='opus'
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
                
                with open(temp_audio_path, 'rb') as f:
                    audio_content = f.read()
                
                logger.info("Audio extracted", size_bytes=len(audio_content))
                return audio_content
            
            finally:
                if os.path.exists(temp_video_path):
                    os.unlink(temp_video_path)
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
        
        except Exception as e:
            logger.error("Audio extraction failed", error=str(e))
            raise