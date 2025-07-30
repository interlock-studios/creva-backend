import whisper
import torch
import structlog
from typing import List, Optional, Dict, Any, Tuple
import tempfile
import os
import time
from datetime import timedelta

from src.models.parser_result import TranscriptSegment
from src.utils.retry import exponential_backoff

logger = structlog.get_logger()


class WhisperService:
    """OpenAI Whisper speech-to-text service with GPU optimization"""
    
    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        self.model_size = model_size
        self.device = self._get_device(device)
        self.model = None
        self._model_loaded = False
        
        logger.info(
            "WhisperService initialized", 
            model_size=model_size, 
            device=self.device,
            gpu_available=torch.cuda.is_available()
        )
    
    def _get_device(self, device: str) -> str:
        """Determine best device for Whisper processing"""
        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"  # Apple Silicon
            else:
                return "cpu"
        return device
    
    async def load_model(self) -> None:
        """Load Whisper model (lazy loading for memory efficiency)"""
        if self._model_loaded:
            return
            
        try:
            start_time = time.time()
            logger.info("Loading Whisper model", model_size=self.model_size, device=self.device)
            
            self.model = whisper.load_model(
                self.model_size, 
                device=self.device,
                download_root=os.getenv("WHISPER_MODEL_PATH", None)
            )
            
            load_time = time.time() - start_time
            self._model_loaded = True
            
            logger.info(
                "Whisper model loaded successfully", 
                load_time_seconds=load_time,
                model_size=self.model_size
            )
            
        except Exception as e:
            logger.error("Failed to load Whisper model", error=str(e))
            raise
    
    @exponential_backoff(max_retries=2, base_delay=1.0)
    async def transcribe_audio(
        self, 
        audio_content: bytes, 
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Tuple[List[TranscriptSegment], Dict[str, Any]]:
        """
        Transcribe audio using Whisper with detailed timing
        
        Args:
            audio_content: Raw audio bytes
            language: Optional language code (auto-detect if None)
            task: "transcribe" or "translate"
            
        Returns:
            Tuple of (transcript_segments, metadata)
        """
        await self.load_model()
        
        start_time = time.time()
        
        try:
            # Write audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio.write(audio_content)
                temp_audio_path = temp_audio.name
            
            try:
                logger.info(
                    "Starting Whisper transcription", 
                    audio_size_mb=len(audio_content) / (1024 * 1024),
                    language=language,
                    task=task
                )
                
                # Transcribe with word-level timestamps
                result = self.model.transcribe(
                    temp_audio_path,
                    language=language,
                    task=task,
                    word_timestamps=True,
                    verbose=False,
                    temperature=0.0,  # Deterministic output
                    best_of=1,
                    beam_size=5,
                    patience=1.0,
                    condition_on_previous_text=True,
                    fp16=self.device == "cuda"  # Use FP16 on GPU for speed
                )
                
                processing_time = time.time() - start_time
                
                # Convert to structured segments
                segments = self._convert_to_segments(result["segments"])
                
                # Extract metadata
                metadata = {
                    "language": result.get("language"),
                    "duration_seconds": result.get("duration", 0.0),
                    "processing_time_seconds": processing_time,
                    "model_size": self.model_size,
                    "device": self.device,
                    "segments_count": len(segments),
                    "word_count": sum(len(seg.text.split()) for seg in segments)
                }
                
                logger.info(
                    "Whisper transcription completed",
                    processing_time=processing_time,
                    segments_count=len(segments),
                    detected_language=result.get("language"),
                    duration=result.get("duration", 0.0)
                )
                
                return segments, metadata
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
                    
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Whisper transcription failed", 
                error=str(e), 
                processing_time=processing_time
            )
            raise
    
    def _convert_to_segments(self, whisper_segments: List[Dict]) -> List[TranscriptSegment]:
        """Convert Whisper segments to our structured format"""
        segments = []
        
        for seg in whisper_segments:
            segment = TranscriptSegment(
                start_time=seg["start"],
                end_time=seg["end"],
                text=seg["text"].strip(),
                confidence=seg.get("avg_logprob", 0.0)  # Convert log prob to confidence-like score
            )
            segments.append(segment)
            
        return segments
    
    async def transcribe_with_speakers(
        self, 
        audio_content: bytes,
        language: Optional[str] = None
    ) -> Tuple[List[TranscriptSegment], Dict[str, Any]]:
        """
        Transcribe with speaker diarization (requires additional processing)
        Note: This is a placeholder for future speaker diarization integration
        """
        # For now, just do regular transcription
        # TODO: Integrate with pyannote.audio or similar for speaker diarization
        segments, metadata = await self.transcribe_audio(audio_content, language)
        
        # Add placeholder speaker IDs (could be enhanced with actual diarization)
        for i, segment in enumerate(segments):
            segment.speaker_id = f"speaker_{i % 2}"  # Simple alternating for demo
            
        metadata["speaker_diarization"] = "placeholder"
        return segments, metadata
    
    def estimate_cost(self, audio_duration_seconds: float) -> float:
        """
        Estimate processing cost for Whisper
        Local Whisper is free, but consider compute costs
        """
        # For local processing, cost is essentially GPU/CPU time
        # Estimate based on processing time ratio (usually 0.1-0.3x realtime)
        processing_time_estimate = audio_duration_seconds * 0.2
        
        if self.device == "cuda":
            # GPU cost estimate: ~$0.10/hour for basic GPU
            gpu_cost_per_second = 0.10 / 3600
            return gpu_cost_per_second * processing_time_estimate
        else:
            # CPU cost estimate: ~$0.02/hour for CPU
            cpu_cost_per_second = 0.02 / 3600  
            return cpu_cost_per_second * processing_time_estimate
    
    @property
    def is_model_loaded(self) -> bool:
        """Check if model is loaded and ready"""
        return self._model_loaded and self.model is not None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information for health checks"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "model_loaded": self._model_loaded,
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
        }