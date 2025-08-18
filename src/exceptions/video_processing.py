"""
Video processing specific exceptions
"""
from typing import Optional, Dict, Any
from .base import SetsAIException, ErrorCode


class VideoProcessingError(SetsAIException):
    """Base class for video processing errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.VIDEO_PROCESSING_ERROR,
        url: Optional[str] = None,
        platform: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if url:
            details["url"] = url
        if platform:
            details["platform"] = platform
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details,
            cause=cause
        )


class VideoDownloadError(VideoProcessingError):
    """Raised when video download fails"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        platform: Optional[str] = None,
        http_status: Optional[int] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if http_status:
            details["http_status"] = http_status
            
        super().__init__(
            message=message,
            error_code=ErrorCode.VIDEO_PROCESSING_ERROR,
            url=url,
            platform=platform,
            cause=cause
        )
        
        if details:
            self.details.update(details)


class VideoFormatError(VideoProcessingError):
    """Raised when video format is unsupported or invalid"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        format_info: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if format_info:
            details["format_info"] = format_info
            
        super().__init__(
            message=message,
            error_code=ErrorCode.VIDEO_PROCESSING_ERROR,
            url=url,
            cause=cause
        )
        
        if details:
            self.details.update(details)


class TranscriptionError(VideoProcessingError):
    """Raised when video transcription fails"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        platform: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.TRANSCRIPTION_ERROR,
            url=url,
            platform=platform,
            cause=cause
        )


class UnsupportedPlatformError(VideoProcessingError):
    """Raised when video platform is not supported"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        detected_platform: Optional[str] = None
    ):
        details = {}
        if detected_platform:
            details["detected_platform"] = detected_platform
            details["supported_platforms"] = ["tiktok", "instagram"]
            
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            url=url,
            cause=None
        )
        
        # Override status code for client error
        self.status_code = 422
        
        if details:
            self.details.update(details)
