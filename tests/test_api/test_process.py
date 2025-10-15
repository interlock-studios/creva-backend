"""
Tests for video processing endpoints
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_process_endpoint_valid_url(
    client: TestClient, 
    valid_tiktok_url: str,
    sample_workout_json: dict,
    mock_cache_service,
    mock_video_processor,
    mock_genai_service
):
    """Test process endpoint with valid TikTok URL"""
    with patch('src.api.process.cache_service', mock_cache_service), \
         patch('src.api.process.video_processor', mock_video_processor), \
         patch('src.api.process.genai_service', mock_genai_service):
        
        # Setup mocks
        mock_cache_service.get_cached_bucket_list.return_value = None  # No cache hit
        mock_genai_service.analyze_video_with_transcript.return_value = sample_workout_json
        
        response = client.post("/process", json={
            "url": valid_tiktok_url
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == sample_workout_json["title"]
        assert data["workout_type"] == sample_workout_json["workout_type"]
        assert len(data["exercises"]) == len(sample_workout_json["exercises"])


@pytest.mark.unit
def test_process_endpoint_invalid_url(client: TestClient, invalid_url: str):
    """Test process endpoint with invalid URL"""
    response = client.post("/process", json={
        "url": invalid_url
    })
    
    assert response.status_code == 422  # Validation error


@pytest.mark.unit
def test_process_endpoint_missing_url(client: TestClient):
    """Test process endpoint with missing URL"""
    response = client.post("/process", json={})
    
    assert response.status_code == 422  # Validation error


@pytest.mark.unit
def test_process_endpoint_cached_result(
    client: TestClient, 
    valid_tiktok_url: str,
    sample_workout_json: dict,
    mock_cache_service
):
    """Test process endpoint returns cached result when available"""
    with patch('src.api.process.cache_service', mock_cache_service):
        mock_cache_service.get_cached_bucket_list.return_value = sample_workout_json
        
        response = client.post("/process", json={
            "url": valid_tiktok_url
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == sample_workout_json["title"]
        
        # Verify cache was checked
        mock_cache_service.get_cached_bucket_list.assert_called_once_with(valid_tiktok_url, None)


@pytest.mark.unit
def test_process_endpoint_with_localization(
    client: TestClient, 
    valid_tiktok_url: str,
    mock_cache_service,
    mock_queue_service,
    mock_genai_service,
    mock_video_processor
):
    """Test process endpoint with localization parameter"""
    with patch('src.api.process.cache_service', mock_cache_service), \
         patch('src.api.process.queue_service', mock_queue_service), \
         patch('src.api.process.genai_service', mock_genai_service), \
         patch('src.api.process.video_processor', mock_video_processor), \
         patch('src.api.process.active_direct_processing', 0), \
         patch('src.api.process.MAX_DIRECT_PROCESSING', 5):
        
        # Mock cache miss (async method)
        mock_cache_service.get_cached_bucket_list = AsyncMock(return_value=None)
        
        # Mock no existing job (async method)
        mock_queue_service.get_job_by_url = AsyncMock(return_value=None)
        
        # Mock successful video processing (async methods)
        mock_video_processor.download_video = AsyncMock(return_value=(
            b"fake_video_content",
            {"is_slideshow": False, "transcript_text": "test transcript", "caption": "test caption"}
        ))
        mock_video_processor.remove_audio = AsyncMock(return_value=b"silent_video")
        
        # Mock successful GenAI analysis (async method)
        mock_genai_service.analyze_video_with_transcript = AsyncMock(return_value={
            "title": "Test Workout",
            "exercises": []
        })
        
        # Mock cache write (async method)
        mock_cache_service.cache_bucket_list = AsyncMock(return_value=None)
        
        response = client.post("/process", json={
            "url": valid_tiktok_url,
            "localization": "es"
        })
        
        # Should return workout data
        assert response.status_code == 200
        
        # Verify cache was checked with localization
        mock_cache_service.get_cached_bucket_list.assert_called_once_with(valid_tiktok_url, "es")


@pytest.mark.unit
def test_process_endpoint_queue_fallback(
    client: TestClient, 
    valid_tiktok_url: str,
    mock_cache_service,
    mock_queue_service
):
    """Test process endpoint falls back to queue when direct processing fails"""
    with patch('src.api.process.cache_service', mock_cache_service), \
         patch('src.api.process.queue_service', mock_queue_service), \
         patch('src.api.process.active_direct_processing', 10):  # At capacity
        
        mock_cache_service.get_cached_bucket_list.return_value = None
        mock_queue_service.get_job_by_url.return_value = None  # No existing job
        mock_queue_service.enqueue_video.return_value = "test_job_123"
        
        response = client.post("/process", json={
            "url": valid_tiktok_url
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_id"] == "test_job_123"
        assert "check_url" in data


@pytest.mark.unit
def test_process_endpoint_existing_job(
    client: TestClient, 
    valid_tiktok_url: str,
    mock_cache_service,
    mock_queue_service
):
    """Test process endpoint returns existing job when video already queued"""
    with patch('src.api.process.cache_service', mock_cache_service), \
         patch('src.api.process.queue_service', mock_queue_service):
        
        mock_cache_service.get_cached_bucket_list.return_value = None
        mock_queue_service.get_job_by_url.return_value = {
            "job_id": "existing_job_456",
            "status": "pending"
        }
        
        response = client.post("/process", json={
            "url": valid_tiktok_url
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_id"] == "existing_job_456"


@pytest.mark.unit
def test_get_job_status_success(client: TestClient, mock_queue_service):
    """Test get job status endpoint with valid job ID"""
    with patch('src.api.process.queue_service', mock_queue_service):
        mock_queue_service.get_job_result.return_value = {
            "status": "completed",
            "result": {"title": "Test Workout"}
        }
        
        response = client.get("/status/test_job_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data


@pytest.mark.unit
def test_get_job_status_not_found(client: TestClient, mock_queue_service):
    """Test get job status endpoint with non-existent job ID"""
    with patch('src.api.process.queue_service', mock_queue_service):
        mock_queue_service.get_job_result.return_value = {"status": "not_found"}
        
        response = client.get("/status/nonexistent_job")
        
        assert response.status_code == 404


@pytest.mark.unit
def test_process_endpoint_request_validation():
    """Test request model validation"""
    from src.models.requests import ProcessRequest
    from pydantic import ValidationError
    
    # Valid request
    valid_request = ProcessRequest(url="https://www.tiktok.com/@user/video/123")
    assert valid_request.url == "https://www.tiktok.com/@user/video/123"
    assert valid_request.localization is None
    
    # Valid request with localization
    valid_with_loc = ProcessRequest(
        url="https://www.tiktok.com/@user/video/123", 
        localization="es"
    )
    assert valid_with_loc.localization == "es"
    
    # Invalid URL
    with pytest.raises(ValidationError):
        ProcessRequest(url="not-a-url")
    
    # Empty URL
    with pytest.raises(ValidationError):
        ProcessRequest(url="")
    
    # Missing URL
    with pytest.raises(ValidationError):
        ProcessRequest()
