from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED_DOWNLOAD = "FAILED_DOWNLOAD"
    FAILED_STT = "FAILED_STT"
    FAILED_OCR = "FAILED_OCR"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class VideoMetadata(BaseModel):
    """TikTok video metadata extracted from yt-dlp"""
    title: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None
    author: Optional[str] = None
    author_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    upload_date: Optional[str] = None
    hashtags: Optional[List[str]] = None
    sound_title: Optional[str] = None
    sound_author: Optional[str] = None
    file_size_bytes: Optional[int] = None


class TranscriptSegment(BaseModel):
    """Time-stamped speech segment from Whisper STT"""
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text")
    confidence: Optional[float] = Field(None, description="Confidence score 0-1")
    speaker_id: Optional[str] = Field(None, description="Speaker identification if available")


class OCRBlock(BaseModel):
    """Text block detected in video frame"""
    text: str = Field(..., description="Detected text content")
    confidence: float = Field(..., description="OCR confidence score 0-1")
    timestamp: float = Field(..., description="Time in video when text appears (seconds)")
    frame_number: int = Field(..., description="Video frame number")
    bounding_box: Optional[Dict[str, int]] = Field(None, description="Text location coordinates")


class ProcessingMetrics(BaseModel):
    """Cost and performance metrics"""
    total_latency_seconds: float
    download_time_seconds: float
    stt_time_seconds: Optional[float] = None
    ocr_time_seconds: Optional[float] = None
    
    total_cost_usd: float
    stt_cost_usd: Optional[float] = None
    ocr_cost_usd: Optional[float] = None
    storage_cost_usd: Optional[float] = None
    
    video_file_size_mb: Optional[float] = None
    audio_duration_seconds: Optional[float] = None
    keyframes_extracted: Optional[int] = None
    stt_method: Optional[str] = Field(None, description="whisper-local, whisper-api, or gcp-stt")
    ocr_method: Optional[str] = Field(None, description="gcp-vision or tesseract")


class TikTokParseResult(BaseModel):
    """Complete TikTok parsing result"""
    job_id: str
    url: str
    status: ProcessingStatus
    
    # Core extracted data
    metadata: Optional[VideoMetadata] = None
    transcript_segments: Optional[List[TranscriptSegment]] = None
    ocr_blocks: Optional[List[OCRBlock]] = None
    
    # Processing info
    metrics: Optional[ProcessingMetrics] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class ParseRequest(BaseModel):
    """API request to parse TikTok video"""
    url: str = Field(..., pattern=r'https://.*tiktok\.com/.*')
    priority: Optional[str] = Field("normal", description="normal, high, or low")
    webhook_url: Optional[str] = Field(None, description="Optional webhook for completion notification")
    include_stt: bool = Field(True, description="Include speech-to-text transcription")
    include_ocr: bool = Field(True, description="Include OCR text extraction") 
    stt_method: Optional[str] = Field("auto", description="whisper-local, whisper-api, gcp-stt, or auto")


class ParseResponse(BaseModel):
    """API response with job ID"""
    job_id: str
    status: ProcessingStatus
    estimated_completion_seconds: Optional[int] = None
    webhook_url: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, str]  # service_name -> status
    gpu_available: bool
    whisper_model_loaded: bool