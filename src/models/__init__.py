"""
Data models for the application
"""

# Import all models for easy access
from .parser_result import SlideshowImage, VideoMetadata
from .requests import ProcessRequest, CacheInvalidationRequest
from .responses import (
    ExerciseSet, Exercise, WorkoutData, QueuedResponse,
    HealthResponse, StatusResponse, JobStatusResponse, ErrorResponse,
    TestAPIResponse, CacheInvalidationResponse, AppCheckStatusResponse
)

__all__ = [
    # Parser result models
    'SlideshowImage', 'VideoMetadata',
    # Request models
    'ProcessRequest', 'CacheInvalidationRequest',
    # Response models
    'ExerciseSet', 'Exercise', 'WorkoutData', 'QueuedResponse',
    'HealthResponse', 'StatusResponse', 'JobStatusResponse', 'ErrorResponse',
    'TestAPIResponse', 'CacheInvalidationResponse', 'AppCheckStatusResponse'
]
