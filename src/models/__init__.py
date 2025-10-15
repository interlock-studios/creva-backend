"""
Data models for the application
"""

# Import all models for easy access
from .parser_result import SlideshowImage, VideoMetadata
from .requests import ProcessRequest, CacheInvalidationRequest
from .responses import (
    RelationshipContent,
    QueuedResponse,
    HealthResponse,
    StatusResponse,
    JobStatusResponse,
    ErrorResponse,
    TestAPIResponse,
    CacheInvalidationResponse,
    AppCheckStatusResponse,
)

__all__ = [
    # Parser result models
    "SlideshowImage",
    "VideoMetadata",
    # Request models
    "ProcessRequest",
    "CacheInvalidationRequest",
    # Response models
    "RelationshipContent",
    "QueuedResponse",
    "HealthResponse",
    "StatusResponse",
    "JobStatusResponse",
    "ErrorResponse",
    "TestAPIResponse",
    "CacheInvalidationResponse",
    "AppCheckStatusResponse",
]
