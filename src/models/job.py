from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid


class JobStatus(str, Enum):
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_DOWNLOAD = "FAILED_DOWNLOAD"
    FAILED_STT = "FAILED_STT"
    FAILED_OCR = "FAILED_OCR"
    FAILED_LLM = "FAILED_LLM"
    INVALID_SCHEMA = "INVALID_SCHEMA"


class ParseRequest(BaseModel):
    url: str = Field(..., pattern=r'https://.*tiktok\.com/.*')


class ParseResponse(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    progress: Optional[int] = Field(None, ge=0, le=100)
    workout_json: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessingMetrics(BaseModel):
    latency_seconds: float
    cost_usd: float
    video_duration_seconds: Optional[float] = None
    keyframes_extracted: Optional[int] = None
    stt_confidence: Optional[float] = None
    ocr_text_length: Optional[int] = None
    extraction_method: Optional[str] = None  # "caption", "transcript", or "full_ocr"