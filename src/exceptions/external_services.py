"""
External service specific exceptions
"""
from typing import Optional, Dict, Any
from .base import SetsAIException, ErrorCode


class ExternalServiceError(SetsAIException):
    """Base class for external service errors"""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        http_status: Optional[int] = None,
        response_body: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {
            "service_name": service_name
        }
        if http_status:
            details["http_status"] = http_status
        if response_body:
            details["response_body"] = response_body[:500]  # Truncate long responses
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=502,  # Bad Gateway for external service errors
            details=details,
            cause=cause
        )


class TikTokAPIError(ExternalServiceError):
    """Raised when TikTok API calls fail"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        http_status: Optional[int] = None,
        api_error_code: Optional[str] = None,
        response_body: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if url:
            details["url"] = url
        if api_error_code:
            details["api_error_code"] = api_error_code
            
        super().__init__(
            message=message,
            service_name="tiktok_api",
            error_code=ErrorCode.TIKTOK_API_ERROR,
            http_status=http_status,
            response_body=response_body,
            cause=cause
        )
        
        if details:
            self.details.update(details)


class InstagramAPIError(ExternalServiceError):
    """Raised when Instagram API calls fail"""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        http_status: Optional[int] = None,
        api_error_code: Optional[str] = None,
        response_body: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if url:
            details["url"] = url
        if api_error_code:
            details["api_error_code"] = api_error_code
            
        super().__init__(
            message=message,
            service_name="instagram_api",
            error_code=ErrorCode.INSTAGRAM_API_ERROR,
            http_status=http_status,
            response_body=response_body,
            cause=cause
        )
        
        if details:
            self.details.update(details)


class GenAIServiceError(ExternalServiceError):
    """Raised when GenAI service calls fail"""
    
    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        prompt_length: Optional[int] = None,
        http_status: Optional[int] = None,
        response_body: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if model:
            details["model"] = model
        if prompt_length:
            details["prompt_length"] = prompt_length
            
        super().__init__(
            message=message,
            service_name="genai_service",
            error_code=ErrorCode.GENAI_SERVICE_ERROR,
            http_status=http_status,
            response_body=response_body,
            cause=cause
        )
        
        if details:
            self.details.update(details)


class CacheServiceError(ExternalServiceError):
    """Raised when cache service operations fail"""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        cache_key: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if cache_key:
            details["cache_key"] = cache_key
            
        super().__init__(
            message=message,
            service_name="cache_service",
            error_code=ErrorCode.CACHE_ERROR,
            cause=cause
        )
        
        if details:
            self.details.update(details)


class QueueServiceError(ExternalServiceError):
    """Raised when queue service operations fail"""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        job_id: Optional[str] = None,
        queue_name: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if job_id:
            details["job_id"] = job_id
        if queue_name:
            details["queue_name"] = queue_name
            
        super().__init__(
            message=message,
            service_name="queue_service",
            error_code=ErrorCode.QUEUE_ERROR,
            cause=cause
        )
        
        if details:
            self.details.update(details)
