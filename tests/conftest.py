"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json

# Set test environment variables before importing the app
os.environ.update({
    "GOOGLE_CLOUD_PROJECT_ID": "test-project",
    "SCRAPECREATORS_API_KEY": "test-api-key",
    "ENVIRONMENT": "test",
    "CACHE_TTL_HOURS": "24",
    "MAX_DIRECT_PROCESSING": "3",
    "RATE_LIMIT_REQUESTS": "1000",  # High limit for tests
    "RATE_LIMIT_WINDOW": "3600",   # 1 hour window for tests
    "APPCHECK_REQUIRED": "false"
})

# Import the main app
from main import app
from src.services.genai_service import GenAIService
from src.services.cache_service import CacheService
from src.services.tiktok_scraper import TikTokScraper
from src.services.instagram_scraper import InstagramScraper
from src.services.queue_service import QueueService
from src.worker.video_processor import VideoProcessor


# Event loop fixture removed - using pytest-asyncio default with function scope


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async HTTP client for testing"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_genai_service():
    """Mock GenAI service for testing"""
    mock = AsyncMock(spec=GenAIService)
    mock.analyze_video_with_transcript.return_value = {
        "title": "Test Workout",
        "description": "A test workout routine",
        "workout_type": "strength",
        "duration_minutes": 30,
        "difficulty_level": 5,
        "exercises": [{
            "name": "Push-ups",
            "muscle_groups": ["chest", "arms"],
            "equipment": "Bodyweight",
            "sets": [{"reps": 10, "rest_seconds": 60}],
            "instructions": "Standard push-ups"
        }],
        "tags": ["strength", "bodyweight"],
        "creator": "test_user"
    }
    
    mock.analyze_slideshow_with_transcript.return_value = {
        "title": "Test Slideshow Workout",
        "description": "A test slideshow workout",
        "workout_type": "full body",
        "duration_minutes": 20,
        "difficulty_level": 4,
        "exercises": [{
            "name": "Burpees",
            "muscle_groups": ["legs", "chest", "core"],
            "equipment": "Bodyweight",
            "sets": [{"reps": 5, "rest_seconds": 30}],
            "instructions": "Full body burpee movement"
        }],
        "tags": ["hiit", "bodyweight"],
        "creator": "test_user"
    }
    
    return mock


@pytest.fixture
def mock_tiktok_scraper():
    """Mock TikTok scraper for testing"""
    with patch('src.services.tiktok_scraper.TikTokScraper') as mock_class:
        mock = AsyncMock(spec=TikTokScraper)
        mock_class.return_value = mock
        
        # Mock metadata object
        mock_metadata = MagicMock()
        mock_metadata.title = "Test TikTok Video"
        mock_metadata.duration_seconds = 30
        mock_metadata.author = "test_user"
        mock_metadata.description = "Test video description"
        mock_metadata.caption = "Test caption"
        mock_metadata.hashtags = ["#workout", "#fitness"]
        mock_metadata.is_slideshow = False
        mock_metadata.image_count = None
        mock_metadata.slideshow_duration = None
        
        mock.scrape_tiktok_complete.return_value = (
            b"fake_video_content",  # video_content
            mock_metadata,  # metadata
            "This is a test transcript"  # transcript
        )
    
        # Mock slideshow scraping
        mock_slideshow_metadata = MagicMock()
        mock_slideshow_metadata.title = "Test Slideshow"
        mock_slideshow_metadata.is_slideshow = True
        mock_slideshow_metadata.image_count = 3
        mock_slideshow_metadata.slideshow_duration = 15
        
        mock.scrape_tiktok_slideshow.return_value = (
            [b"image1", b"image2", b"image3"],  # slideshow_images
            mock_slideshow_metadata,  # metadata
            "Slideshow transcript"  # transcript
        )
        
        # Mock get_video_info
        mock.get_video_info.return_value = {
            "metadata": {
                "title": "Test Video",
                "author": "test_user",
                "duration_seconds": 30
            },
            "transcript": "Test transcript"
        }
        
        yield mock


@pytest.fixture
def mock_instagram_scraper():
    """Mock Instagram scraper for testing"""
    mock = AsyncMock(spec=InstagramScraper)
    
    mock_metadata = MagicMock()
    mock_metadata.title = "Test Instagram Video"
    mock_metadata.duration_seconds = 25
    mock_metadata.author = "insta_user"
    mock_metadata.description = "Instagram test video"
    mock_metadata.caption = "Instagram caption"
    mock_metadata.hashtags = ["#fitness", "#reel"]
    mock_metadata.is_slideshow = False
    
    mock.scrape_instagram_complete.return_value = (
        b"fake_instagram_video",
        mock_metadata,
        "Instagram caption text"
    )
    
    mock.get_video_info.return_value = {
        "metadata": {
            "title": "Test Instagram Video",
            "author": "insta_user",
            "duration_seconds": 25
        }
    }
    
    return mock


@pytest.fixture
def mock_cache_service():
    """Mock cache service for testing"""
    mock = AsyncMock(spec=CacheService)
    mock.get_cached_video.return_value = None  # No cache hit by default
    mock.cache_video.return_value = True
    mock.invalidate_cache.return_value = True
    mock.is_healthy.return_value = True
    mock.get_cache_stats.return_value = {
        "status": "active",
        "video_cache": {"total_cached_videos": 0}
    }
    return mock


@pytest.fixture
def mock_queue_service():
    """Mock queue service for testing"""
    mock = AsyncMock(spec=QueueService)
    mock.get_job_by_url.return_value = None  # No existing job by default
    mock.enqueue_video.return_value = "test_job_id_123"
    mock.get_job_result.return_value = {
        "status": "completed",
        "result": {"title": "Test Workout"}
    }
    mock.get_queue_stats.return_value = {
        "status": "active",
        "queue_stats": {"pending": 0, "processing": 0}
    }
    return mock


@pytest.fixture
def mock_video_processor():
    """Mock video processor for testing"""
    mock = AsyncMock(spec=VideoProcessor)
    
    mock.download_video.return_value = (
        b"fake_video_content",
        {
            "platform": "tiktok",
            "title": "Test Video",
            "duration": 30,
            "uploader": "test_user",
            "description": "Test description",
            "caption": "Test caption",
            "tags": ["#workout"],
            "transcript_text": "Test transcript",
            "is_slideshow": False,
            "image_count": None,
            "slideshow_duration": None
        }
    )
    
    mock.remove_audio.return_value = b"silent_video_content"
    
    return mock


@pytest.fixture
def temp_video_file():
    """Create a temporary video file for testing"""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"fake video content for testing")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_workout_json():
    """Sample workout JSON for testing"""
    return {
        "title": "Full Body HIIT Workout",
        "description": "High intensity interval training for full body",
        "workout_type": "HIIT",
        "duration_minutes": 25,
        "difficulty_level": 7,
        "exercises": [
            {
                "name": "Burpees",
                "muscle_groups": ["legs", "chest", "core"],
                "equipment": "Bodyweight",
                "sets": [
                    {"reps": 10, "rest_seconds": 30},
                    {"reps": 8, "rest_seconds": 30},
                    {"reps": 6, "rest_seconds": 60}
                ],
                "instructions": "Full body burpee with jump"
            },
            {
                "name": "Mountain Climbers",
                "muscle_groups": ["core", "legs"],
                "equipment": "Bodyweight",
                "sets": [
                    {"duration_seconds": 30, "rest_seconds": 30},
                    {"duration_seconds": 30, "rest_seconds": 30},
                    {"duration_seconds": 30, "rest_seconds": 60}
                ],
                "instructions": "Fast alternating knee drives"
            }
        ],
        "tags": ["hiit", "bodyweight", "cardio"],
        "creator": "fitness_guru"
    }


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing"""
    env_vars = {
        "GOOGLE_CLOUD_PROJECT_ID": "test-project",
        "SCRAPECREATORS_API_KEY": "test-api-key",
        "ENVIRONMENT": "test",
        "CACHE_TTL_HOURS": "24",
        "MAX_DIRECT_PROCESSING": "3",
        "RATE_LIMIT_REQUESTS": "5",
        "RATE_LIMIT_WINDOW": "30",
        "APPCHECK_REQUIRED": "false"
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture(autouse=True)
def mock_external_services():
    """Auto-mock external services for all tests"""
    with patch('src.services.genai_service.genai.Client'), \
         patch('src.services.cache_service.firestore.Client'), \
         patch('src.services.queue_service.firestore.Client'), \
         patch('httpx.AsyncClient'):
        yield


# Test data fixtures
@pytest.fixture
def valid_tiktok_url():
    """Valid TikTok URL for testing"""
    return "https://www.tiktok.com/@user/video/1234567890"


@pytest.fixture
def valid_instagram_url():
    """Valid Instagram URL for testing"""
    return "https://www.instagram.com/reel/ABC123DEF/"


@pytest.fixture
def invalid_url():
    """Invalid URL for testing"""
    return "not-a-valid-url"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
