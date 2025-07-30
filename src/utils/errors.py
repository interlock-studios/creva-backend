from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    # Client errors
    INVALID_URL = "INVALID_URL"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    RATE_LIMIT = "RATE_LIMIT"
    
    # Processing errors
    FAILED_DOWNLOAD = "FAILED_DOWNLOAD"
    FAILED_STT = "FAILED_STT"
    FAILED_OCR = "FAILED_OCR"
    FAILED_LLM = "FAILED_LLM"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    
    # System errors
    INTERNAL = "INTERNAL"
    TIMEOUT = "TIMEOUT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"


class ProcessingError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.job_id = job_id
        super().__init__(f"{code.value}: {message}")


class VideoDownloadError(ProcessingError):
    def __init__(self, message: str, job_id: Optional[str] = None, **details):
        super().__init__(ErrorCode.FAILED_DOWNLOAD, message, details, job_id)


class SpeechTranscriptionError(ProcessingError):
    def __init__(self, message: str, job_id: Optional[str] = None, **details):
        super().__init__(ErrorCode.FAILED_STT, message, details, job_id)


class VisionError(ProcessingError):
    def __init__(self, message: str, job_id: Optional[str] = None, **details):
        super().__init__(ErrorCode.FAILED_OCR, message, details, job_id)


class LLMError(ProcessingError):
    def __init__(self, message: str, job_id: Optional[str] = None, **details):
        super().__init__(ErrorCode.FAILED_LLM, message, details, job_id)


class SchemaValidationError(ProcessingError):
    def __init__(self, message: str, job_id: Optional[str] = None, **details):
        super().__init__(ErrorCode.INVALID_SCHEMA, message, details, job_id)


class RetryableError(ProcessingError):
    def __init__(self, code: ErrorCode, message: str, retry_after: int = 60, **details):
        super().__init__(code, message, details)
        self.retry_after = retry_after


class QuotaExceededError(RetryableError):
    def __init__(self, service: str, retry_after: int = 3600, **details):
        message = f"{service} quota exceeded"
        super().__init__(ErrorCode.QUOTA_EXCEEDED, message, retry_after, service=service, **details)