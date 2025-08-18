"""
Tests for error handling system
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from src.exceptions import (
    SetsAIException, ValidationError, NotFoundError, 
    ProcessingError, VideoProcessingError, TikTokAPIError
)
from src.exceptions.base import ErrorCode


@pytest.mark.unit
def test_sets_ai_exception_creation():
    """Test SetsAI exception creation and serialization"""
    exc = SetsAIException(
        message="Test error",
        error_code=ErrorCode.PROCESSING_ERROR,
        status_code=500,
        details={"key": "value"}
    )
    
    assert exc.message == "Test error"
    assert exc.error_code == ErrorCode.PROCESSING_ERROR
    assert exc.status_code == 500
    assert exc.details == {"key": "value"}
    
    # Test serialization
    exc_dict = exc.to_dict()
    assert exc_dict["code"] == "PROCESSING_ERROR"
    assert exc_dict["message"] == "Test error"
    assert exc_dict["status_code"] == 500
    assert exc_dict["details"] == {"key": "value"}


@pytest.mark.unit
def test_validation_error():
    """Test ValidationError specific functionality"""
    exc = ValidationError(
        message="Invalid field",
        field="url",
        value="invalid-url"
    )
    
    assert exc.status_code == 422
    assert exc.error_code == ErrorCode.VALIDATION_ERROR
    assert exc.details["field"] == "url"
    assert exc.details["value"] == "invalid-url"


@pytest.mark.unit
def test_not_found_error():
    """Test NotFoundError specific functionality"""
    exc = NotFoundError(
        message="Resource not found",
        resource_type="job",
        resource_id="123"
    )
    
    assert exc.status_code == 404
    assert exc.error_code == ErrorCode.NOT_FOUND
    assert exc.details["resource_type"] == "job"
    assert exc.details["resource_id"] == "123"


@pytest.mark.unit
def test_video_processing_error():
    """Test VideoProcessingError functionality"""
    exc = VideoProcessingError(
        message="Video processing failed",
        url="https://tiktok.com/video/123",
        platform="tiktok"
    )
    
    assert exc.status_code == 500
    assert exc.error_code == ErrorCode.VIDEO_PROCESSING_ERROR
    assert exc.details["url"] == "https://tiktok.com/video/123"
    assert exc.details["platform"] == "tiktok"


@pytest.mark.unit
def test_tiktok_api_error():
    """Test TikTokAPIError functionality"""
    exc = TikTokAPIError(
        message="TikTok API failed",
        url="https://tiktok.com/video/123",
        http_status=429,
        api_error_code="RATE_LIMITED"
    )
    
    assert exc.status_code == 502  # Bad Gateway for external service errors
    assert exc.error_code == ErrorCode.TIKTOK_API_ERROR
    assert exc.details["service_name"] == "tiktok_api"
    assert exc.details["url"] == "https://tiktok.com/video/123"
    assert exc.details["http_status"] == 429
    assert exc.details["api_error_code"] == "RATE_LIMITED"


@pytest.mark.unit
def test_error_handler_sets_ai_exception(client: TestClient):
    """Test error handler for SetsAI exceptions"""
    
    # Mock an endpoint that raises a SetsAI exception
    with patch('src.api.process.queue_service') as mock_queue:
        mock_queue.get_job_result = AsyncMock(return_value={"status": "not_found"})
        
        response = client.get("/status/nonexistent_job")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "Job not found" in data["error"]["message"]
        assert "request_id" in data
        assert "timestamp" in data
        assert data["path"] == "/status/nonexistent_job"


@pytest.mark.unit
def test_error_handler_validation_error(client: TestClient):
    """Test error handler for validation errors"""
    
    # Send invalid request to trigger validation error
    response = client.post("/process", json={
        "url": "not-a-valid-url"
    })
    
    assert response.status_code == 422
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "validation_errors" in data["error"]["details"]
    assert "request_id" in data
    assert "timestamp" in data


@pytest.mark.unit
def test_error_handler_http_exception(client: TestClient):
    """Test error handler for HTTP exceptions"""
    
    # Request non-existent endpoint
    response = client.get("/nonexistent-endpoint")
    
    assert response.status_code == 404
    data = response.json()
    
    assert "error" in data
    # FastAPI returns "HTTP_ERROR" for generic HTTP exceptions
    assert data["error"]["code"] in ["NOT_FOUND", "HTTP_ERROR"]
    assert "request_id" in data
    assert "timestamp" in data


@pytest.mark.unit
def test_error_context_preservation():
    """Test that error context is preserved through exception chain"""
    
    original_error = ValueError("Original error")
    
    processing_error = ProcessingError(
        message="Processing failed",
        operation="video_analysis",
        cause=original_error
    )
    
    assert processing_error.cause == original_error
    
    exc_dict = processing_error.to_dict()
    assert exc_dict["cause"] == "Original error"
    assert exc_dict["details"]["operation"] == "video_analysis"


@pytest.mark.unit
def test_error_code_enum():
    """Test ErrorCode enum values"""
    
    # Test that all expected error codes exist
    assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
    assert ErrorCode.NOT_FOUND.value == "NOT_FOUND"
    assert ErrorCode.PROCESSING_ERROR.value == "PROCESSING_ERROR"
    assert ErrorCode.TIKTOK_API_ERROR.value == "TIKTOK_API_ERROR"
    assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
    
    # Test that error codes are unique
    error_codes = [code.value for code in ErrorCode]
    assert len(error_codes) == len(set(error_codes))
