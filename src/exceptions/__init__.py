"""
Custom exceptions for the application
"""

from .base import (
    SetsAIException,
    ValidationError,
    NotFoundError,
    ServiceUnavailableError,
    RateLimitExceededError,
    AuthenticationError,
    ProcessingError
)

from .video_processing import (
    VideoProcessingError,
    VideoDownloadError,
    VideoFormatError,
    TranscriptionError,
    UnsupportedPlatformError
)

from .external_services import (
    ExternalServiceError,
    TikTokAPIError,
    InstagramAPIError,
    GenAIServiceError,
    CacheServiceError,
    QueueServiceError
)

__all__ = [
    # Base exceptions
    'SetsAIException',
    'ValidationError',
    'NotFoundError', 
    'ServiceUnavailableError',
    'RateLimitExceededError',
    'AuthenticationError',
    'ProcessingError',
    
    # Video processing exceptions
    'VideoProcessingError',
    'VideoDownloadError',
    'VideoFormatError',
    'TranscriptionError',
    'UnsupportedPlatformError',
    
    # External service exceptions
    'ExternalServiceError',
    'TikTokAPIError',
    'InstagramAPIError',
    'GenAIServiceError',
    'CacheServiceError',
    'QueueServiceError'
]
