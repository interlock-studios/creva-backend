"""
Tests for video processor service
"""
import pytest
import tempfile
import os
from unittest.mock import patch, Mock, AsyncMock
from src.worker.video_processor import VideoProcessor
from src.exceptions import UnsupportedPlatformError


@pytest.mark.unit
def test_video_processor_init():
    """Test video processor initialization"""
    processor = VideoProcessor()
    assert processor.tiktok_scraper is not None
    assert processor.instagram_scraper is not None
    assert processor.url_router is not None


@pytest.mark.unit
def test_temp_file_context_manager():
    """Test temp file context manager creates and cleans up files"""
    processor = VideoProcessor()
    temp_path = None
    
    with processor.temp_file(suffix=".test") as path:
        temp_path = path
        assert os.path.exists(path)
        assert path.endswith(".test")
        
        # Write some data
        with open(path, "w") as f:
            f.write("test data")
    
    # File should be cleaned up
    assert not os.path.exists(temp_path)


@pytest.mark.unit
def test_temp_file_cleanup_on_exception():
    """Test temp file is cleaned up even if exception occurs"""
    processor = VideoProcessor()
    temp_path = None
    
    try:
        with processor.temp_file() as path:
            temp_path = path
            assert os.path.exists(path)
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    # File should still be cleaned up
    assert not os.path.exists(temp_path)


@pytest.mark.unit
def test_temp_directory_context_manager():
    """Test temp directory context manager"""
    processor = VideoProcessor()
    temp_dir = None
    
    with processor.temp_directory() as dir_path:
        temp_dir = dir_path
        assert os.path.exists(dir_path)
        assert os.path.isdir(dir_path)
        
        # Create a file in the directory
        test_file = os.path.join(dir_path, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        assert os.path.exists(test_file)
    
    # Directory and contents should be cleaned up
    assert not os.path.exists(temp_dir)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_video_tiktok_success(mock_tiktok_scraper):
    """Test successful TikTok video download"""
    processor = VideoProcessor()
    processor.tiktok_scraper = mock_tiktok_scraper
    
    with patch.object(processor.url_router, 'detect_platform', return_value='tiktok'):
        video_content, metadata = await processor.download_video(
            "https://www.tiktok.com/@user/video/123"
        )
        
        assert video_content == b"fake_video_content"
        assert metadata["title"] == "Test TikTok Video"
        assert metadata["platform"] == "tiktok"
        assert metadata["transcript_text"] == "This is a test transcript"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_video_instagram_success(mock_instagram_scraper):
    """Test successful Instagram video download"""
    processor = VideoProcessor()
    processor.instagram_scraper = mock_instagram_scraper
    
    with patch.object(processor.url_router, 'detect_platform', return_value='instagram'):
        video_content, metadata = await processor.download_video(
            "https://www.instagram.com/reel/ABC123/"
        )
        
        assert video_content == b"fake_instagram_video"
        assert metadata["title"] == "Test Instagram Video"
        assert metadata["platform"] == "instagram"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_video_unsupported_platform():
    """Test download video with unsupported platform"""
    processor = VideoProcessor()
    
    with patch.object(processor.url_router, 'detect_platform', return_value=None):
        with pytest.raises(UnsupportedPlatformError, match="Unsupported URL"):
            await processor.download_video("https://youtube.com/watch?v=123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_audio_success():
    """Test successful audio removal from video"""
    processor = VideoProcessor()
    test_video_content = b"fake video content with audio"
    processed_content = b"fake video content without audio"
    
    # Mock the temp_file context manager properly
    with patch.object(processor, 'temp_file') as mock_temp_file:
        # Create proper context manager mocks
        mock_input_cm = Mock()
        mock_input_cm.__enter__ = Mock(return_value='/tmp/input.mp4')
        mock_input_cm.__exit__ = Mock(return_value=None)
        
        mock_output_cm = Mock()
        mock_output_cm.__enter__ = Mock(return_value='/tmp/output.mp4')
        mock_output_cm.__exit__ = Mock(return_value=None)
        
        # Configure temp_file to return different context managers for each call
        mock_temp_file.side_effect = [mock_input_cm, mock_output_cm]
        
        # Mock file operations and ffmpeg
        with patch('builtins.open', create=True) as mock_open, \
             patch('ffmpeg.input') as mock_input, \
             patch('ffmpeg.output') as mock_output:
            
            # Mock file read/write operations
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            mock_file.read.return_value = processed_content
            mock_file.write = Mock()  # Mock write operation
            
            # Mock ffmpeg pipeline
            mock_stream = Mock()
            mock_input.return_value = mock_stream
            mock_output.return_value = mock_stream
            mock_stream.overwrite_output.return_value = mock_stream
            mock_stream.run = Mock()
            
            result = await processor.remove_audio(test_video_content)
            
            assert result == processed_content
            
            # Verify temp files were used
            assert mock_temp_file.call_count == 2
            # Verify context managers were entered
            mock_input_cm.__enter__.assert_called_once()
            mock_output_cm.__enter__.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_audio_ffmpeg_error():
    """Test audio removal with FFmpeg error"""
    processor = VideoProcessor()
    test_video_content = b"fake video content"
    
    with patch('ffmpeg.input'), \
         patch('ffmpeg.output'), \
         patch('ffmpeg.run') as mock_run:
        
        # Mock FFmpeg error
        import ffmpeg
        error = ffmpeg.Error("ffmpeg", "stdout", "stderr error message")
        mock_run.side_effect = error
        
        with pytest.raises(Exception, match="Video processing failed"):
            await processor.remove_audio(test_video_content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_audio_empty_output():
    """Test audio removal with empty output file"""
    processor = VideoProcessor()
    test_video_content = b"fake video content"
    
    with patch('ffmpeg.input'), \
         patch('ffmpeg.output'), \
         patch('ffmpeg.run'), \
         patch('builtins.open', create=True) as mock_open:
        
        # Mock empty output file
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b""  # Empty output
        
        with pytest.raises(Exception, match="FFmpeg produced empty output file"):
            await processor.remove_audio(test_video_content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_remove_audio_file_write_error():
    """Test audio removal with file write error"""
    processor = VideoProcessor()
    test_video_content = b"fake video content"
    
    with patch('builtins.open', create=True) as mock_open:
        # Mock file write error
        mock_open.side_effect = IOError("Permission denied")
        
        with pytest.raises(Exception, match="Failed to write video content"):
            await processor.remove_audio(test_video_content)
