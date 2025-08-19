"""
Base exception classes for the application
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(Enum):
    """Standard error codes for the application"""

    # Validation errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_URL = "INVALID_URL"
    INVALID_LOCALIZATION = "INVALID_LOCALIZATION"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Authentication/Authorization errors (4xx)
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    APPCHECK_REQUIRED = "APPCHECK_REQUIRED"
    APPCHECK_INVALID = "APPCHECK_INVALID"

    # Rate limiting (4xx)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Not found errors (4xx)
    NOT_FOUND = "NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    VIDEO_NOT_FOUND = "VIDEO_NOT_FOUND"

    # Processing errors (5xx)
    PROCESSING_ERROR = "PROCESSING_ERROR"
    VIDEO_PROCESSING_ERROR = "VIDEO_PROCESSING_ERROR"
    TRANSCRIPTION_ERROR = "TRANSCRIPTION_ERROR"

    # External service errors (5xx)
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    TIKTOK_API_ERROR = "TIKTOK_API_ERROR"
    INSTAGRAM_API_ERROR = "INSTAGRAM_API_ERROR"
    GENAI_SERVICE_ERROR = "GENAI_SERVICE_ERROR"

    # Infrastructure errors (5xx)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    CACHE_ERROR = "CACHE_ERROR"
    QUEUE_ERROR = "QUEUE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Internal errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"


class SetsAIException(Exception):
    """Base exception for all application-specific errors"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "code": self.error_code.value,
            "message": self.message,
            "status_code": self.status_code,
        }

        if self.details:
            result["details"] = self.details

        if self.cause:
            result["cause"] = str(self.cause)

        return result

    def __str__(self) -> str:
        return f"{self.error_code.value}: {self.message}"


class ValidationError(SetsAIException):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)

        super().__init__(
            message=message, error_code=ErrorCode.VALIDATION_ERROR, status_code=422, details=details
        )


class NotFoundError(SetsAIException):
    """Raised when a requested resource is not found"""

    def __init__(
        self, message: str, resource_type: Optional[str] = None, resource_id: Optional[str] = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message, error_code=ErrorCode.NOT_FOUND, status_code=404, details=details
        )


class ServiceUnavailableError(SetsAIException):
    """Raised when a service is temporarily unavailable"""

    def __init__(
        self, message: str, service_name: Optional[str] = None, retry_after: Optional[int] = None
    ):
        details = {}
        if service_name:
            details["service_name"] = service_name
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=503,
            details=details,
        )


class RateLimitExceededError(SetsAIException):
    """Raised when rate limits are exceeded"""

    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        retry_after: Optional[int] = None,
    ):
        details = {}
        if limit:
            details["limit"] = limit
        if window_seconds:
            details["window_seconds"] = window_seconds
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            details=details,
        )


class AuthenticationError(SetsAIException):
    """Raised when authentication fails"""

    def __init__(self, message: str, auth_type: Optional[str] = None):
        details = {}
        if auth_type:
            details["auth_type"] = auth_type

        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            status_code=401,
            details=details,
        )


class ProcessingError(SetsAIException):
    """Raised when processing operations fail"""

    def __init__(
        self, message: str, operation: Optional[str] = None, cause: Optional[Exception] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.PROCESSING_ERROR,
            status_code=500,
            details=details,
            cause=cause,
        )
