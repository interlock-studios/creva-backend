import structlog
from typing import Dict, Any, List, Optional, Tuple
import time
from datetime import datetime

from src.worker.video_processor import VideoProcessor
from src.services.storage_service import StorageService
from src.services.speech_service import SpeechService
from src.services.vision_service import VisionService
from src.services.vertex_ai_service import VertexAIService
from src.services.firestore_service import FirestoreService
from src.models.job import JobStatus, ProcessingMetrics
from src.utils.validation import validate_workout_json, sanitize_workout_data
from src.utils.errors import (
    VideoDownloadError, SpeechTranscriptionError, VisionError, 
    LLMError, SchemaValidationError, ProcessingError
)
from src.utils.retry import exponential_backoff, timeout
from src.utils.monitoring import measure_time, metrics

logger = structlog.get_logger()


class ProcessingPipeline:
    def __init__(self):
        self.video_processor = VideoProcessor()
        self.storage_service = StorageService()
        self.speech_service = SpeechService()
        self.vision_service = VisionService()
        self.vertex_ai_service = VertexAIService()
        self.firestore_service = FirestoreService()
    
    async def process_video(self, job_id: str, url: str, user_id: str) -> None:
        start_time = time.time()
        total_cost = 0.0
        
        try:
            logger.info("Starting optimized video processing pipeline", job_id=job_id, url=url)
            
            # Step 1: Download Video & Extract Metadata (DL)
            await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=10)
            video_content, metadata = await self._step_download_video(job_id, url)
            
            # FAST PATH: Try caption/description parsing first
            caption_text = self._extract_caption_text(metadata)
            if caption_text:
                logger.info("Found caption text, trying fast extraction", job_id=job_id, text_length=len(caption_text))
                
                # Step 2: Try Gemini with caption only
                await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=30)
                try:
                    workout_json, llm_cost = await self._step_extract_json_from_text(job_id, caption_text, source="caption")
                    total_cost += llm_cost
                    
                    # Step 3: Validate Schema (VAL)
                    await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=80)
                    validated_json = await self._step_validate_schema(job_id, workout_json)
                    
                    logger.info("Fast path successful - caption parsing worked!", job_id=job_id)
                    await self._save_results(job_id, validated_json, start_time, total_cost, metadata, "caption")
                    return
                    
                except Exception as e:
                    logger.info("Caption parsing failed, trying audio transcription", job_id=job_id, error=str(e))
            
            # MEDIUM PATH: Try audio transcription
            await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=40)
            has_speech = await self._step_detect_speech(job_id, video_content)
            
            if has_speech:
                try:
                    transcript, stt_cost = await self._step_transcribe_audio(job_id, video_content)
                    total_cost += stt_cost
                    
                    if transcript and len(transcript.strip()) > 20:  # Meaningful transcript
                        logger.info("Found meaningful transcript, trying extraction", job_id=job_id, text_length=len(transcript))
                        
                        # Try Gemini with transcript
                        await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=60)
                        workout_json, llm_cost = await self._step_extract_json_from_text(job_id, transcript, source="transcript")
                        total_cost += llm_cost
                        
                        # Validate Schema
                        await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=80)
                        validated_json = await self._step_validate_schema(job_id, workout_json)
                        
                        logger.info("Medium path successful - transcript parsing worked!", job_id=job_id)
                        await self._save_results(job_id, validated_json, start_time, total_cost, metadata, "transcript")
                        return
                        
                except Exception as e:
                    logger.info("Transcript parsing failed, falling back to OCR", job_id=job_id, error=str(e))
            
            # SLOW PATH: Full OCR extraction (last resort)
            logger.info("Using full OCR path as last resort", job_id=job_id)
            
            # Extract Keyframes
            await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=50)
            keyframes = await self._step_extract_keyframes(job_id, video_content)
            
            # OCR Keyframes
            await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=65)
            ocr_texts, ocr_cost = await self._step_ocr_keyframes(job_id, keyframes)
            total_cost += ocr_cost
            
            # Aggregate all available text
            all_texts = [caption_text] if caption_text else []
            if 'has_speech' in locals() and has_speech and 'transcript' in locals():
                all_texts.append(transcript)
            all_texts.extend(ocr_texts)
            
            aggregated_text = await self._step_aggregate_text("", all_texts)
            
            # Extract JSON with LLM
            await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=80)
            workout_json, llm_cost = await self._step_extract_json_from_text(job_id, aggregated_text, source="full_ocr")
            total_cost += llm_cost
            
            # Validate Schema
            await self.firestore_service.update_job_status(job_id, JobStatus.PROCESSING, progress=90)
            validated_json = await self._step_validate_schema(job_id, workout_json)
            
            logger.info("Slow path completed - full OCR extraction", job_id=job_id)
            await self._save_results(job_id, validated_json, start_time, total_cost, metadata, "full_ocr", len(keyframes))
        
        except ProcessingError as e:
            processing_time = time.time() - start_time
            
            # Map processing error to job status
            error_to_status = {
                "FAILED_DOWNLOAD": JobStatus.FAILED_DOWNLOAD,
                "FAILED_STT": JobStatus.FAILED_STT,
                "FAILED_OCR": JobStatus.FAILED_OCR,
                "FAILED_LLM": JobStatus.FAILED_LLM,
                "INVALID_SCHEMA": JobStatus.INVALID_SCHEMA,
            }
            
            status = error_to_status.get(e.code.value, JobStatus.FAILED_DOWNLOAD)
            error_msg = e.message
            
        except Exception as e:
            processing_time = time.time() - start_time
            status = JobStatus.FAILED_DOWNLOAD  # Default for unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            metrics.record_error(job_id, "unexpected_error", "pipeline")
            
            await self.firestore_service.update_job_status(
                job_id=job_id,
                status=status,
                message=error_msg,
                metrics={"latency_seconds": processing_time, "cost_usd": total_cost}
            )
            
            logger.error(
                "Pipeline failed",
                job_id=job_id,
                error=error_msg,
                processing_time=processing_time,
                status=status.value
            )
    
    def _extract_caption_text(self, metadata: Dict[str, Any]) -> str:
        """Extract available text from TikTok metadata (captions, description, etc.)"""
        texts = []
        
        # Try various metadata fields - prioritize caption and description
        for field in ['caption', 'description', 'title']:
            value = metadata.get(field, '')
            if value and isinstance(value, str) and len(value.strip()) > 10:
                texts.append(value.strip())
        
        # Also try to extract hashtags which might contain workout info
        tags_list = metadata.get('tags', [])
        if tags_list and isinstance(tags_list, list):
            hashtag_text = ' '.join([f"#{tag}" if not tag.startswith('#') else tag for tag in tags_list])
            if hashtag_text:
                texts.append(hashtag_text)
        
        # Combine and clean up
        combined = ' '.join(texts)
        
        # Enhanced filtering - look for workout-related keywords
        workout_keywords = ['workout', 'exercise', 'fitness', 'gym', 'training', 'reps', 'sets', 'squat', 'push', 'pull', 'cardio', 'hiit', 'abs', 'core', 'strength']
        combined_lower = combined.lower()
        
        # If we have meaningful text with workout keywords, prefer it
        has_workout_content = any(keyword in combined_lower for keyword in workout_keywords)
        
        if len(combined) > 20 and has_workout_content:
            logger.info("Found workout-related caption text", text_length=len(combined), has_workout_keywords=True)
            return combined
        elif len(combined) > 50:  # Accept longer text even without keywords
            logger.info("Found substantial caption text", text_length=len(combined), has_workout_keywords=False)
            return combined
        else:
            logger.info("Caption text too short or not workout-related", text_length=len(combined))
            return ""
    
    async def _save_results(self, job_id: str, validated_json: Dict[str, Any], start_time: float, 
                           total_cost: float, metadata: Dict[str, Any], extraction_method: str, 
                           keyframes_count: int = 0):
        """Save successful processing results"""
        processing_time = time.time() - start_time
        
        metrics = ProcessingMetrics(
            latency_seconds=processing_time,
            cost_usd=total_cost,
            video_duration_seconds=metadata.get('duration'),
            keyframes_extracted=keyframes_count,
            extraction_method=extraction_method
        )
        
        await self.firestore_service.update_job_status(
            job_id=job_id,
            status=JobStatus.SUCCEEDED,
            progress=100,
            workout_json=validated_json,
            metrics=metrics.dict()
        )
        
        logger.info(
            "Pipeline completed successfully",
            job_id=job_id,
            processing_time=processing_time,
            total_cost=total_cost,
            method=extraction_method
        )
    
    @exponential_backoff(max_retries=3, base_delay=2.0)
    @timeout(20)
    async def _step_download_video(self, job_id: str, url: str) -> Tuple[bytes, dict]:
        async with measure_time(job_id, "download_video"):
            try:
                video_content, metadata = await self.video_processor.download_video(url)
                await self.storage_service.upload_video(job_id, video_content)
                return video_content, metadata
            except Exception as e:
                metrics.record_error(job_id, "download_failed", "download_video")
                raise VideoDownloadError(f"Failed to download video: {str(e)}", job_id)
    
    async def _step_extract_keyframes(self, job_id: str, video_content: bytes) -> List[bytes]:
        try:
            keyframes = await self.video_processor.extract_keyframes(video_content)
            await self.storage_service.upload_keyframes(job_id, keyframes)
            return keyframes
        except Exception as e:
            raise Exception(f"Keyframe extraction failed: {str(e)}")
    
    async def _step_detect_speech(self, job_id: str, video_content: bytes) -> bool:
        try:
            return await self.video_processor.detect_speech(video_content)
        except Exception as e:
            logger.warning("Speech detection failed, assuming no speech", error=str(e))
            return False
    
    async def _step_transcribe_audio(self, job_id: str, video_content: bytes) -> Tuple[str, float]:
        try:
            audio_content = await self.video_processor.extract_audio(video_content)
            transcript = await self.speech_service.transcribe_audio(audio_content)
            
            # Estimate cost: $0.006 per 15-second increment
            audio_size_mb = len(audio_content) / (1024 * 1024)
            estimated_duration = audio_size_mb * 60  # Rough estimate
            cost = max(0.006, (estimated_duration / 15) * 0.006)
            
            return transcript or "", cost
        except Exception as e:
            raise Exception(f"Speech transcription failed: {str(e)}")
    
    async def _step_ocr_keyframes(self, job_id: str, keyframes: List[bytes]) -> Tuple[List[str], float]:
        try:
            ocr_texts = await self.vision_service.extract_text_batch(keyframes, batch_size=20)
            
            # Estimate cost: $1.50 per 1000 images
            cost = (len(keyframes) / 1000) * 1.50
            
            return ocr_texts, cost
        except Exception as e:
            raise Exception(f"OCR failed: {str(e)}")
    
    async def _step_aggregate_text(self, transcript: str, ocr_texts: List[str]) -> str:
        try:
            # Simple aggregation: deduplicate and combine
            all_texts = [transcript] + ocr_texts
            unique_texts = []
            seen = set()
            
            for text in all_texts:
                if text and text.strip():
                    text_lower = text.lower().strip()
                    if text_lower not in seen:
                        seen.add(text_lower)
                        unique_texts.append(text.strip())
            
            aggregated = " ".join(unique_texts)
            logger.info("Text aggregated", total_length=len(aggregated), unique_texts=len(unique_texts))
            
            return aggregated
        except Exception as e:
            logger.warning("Text aggregation failed, using raw texts", error=str(e))
            return f"{transcript} {' '.join(ocr_texts)}"
    
    async def _step_extract_json_from_text(self, job_id: str, text: str, source: str) -> Tuple[Dict[str, Any], float]:
        """Extract workout JSON from any text source using Gemini"""
        try:
            logger.info(f"Extracting JSON from {source}", job_id=job_id, text_length=len(text))
            
            # Use single text input for faster processing
            workout_json = await self.vertex_ai_service.extract_workout_json_from_text(text)
            
            if not workout_json:
                raise Exception(f"LLM returned empty response from {source}")
            
            # Cost is the same regardless of source: ~$0.03 per request
            cost = 0.03
            
            logger.info(f"JSON extraction successful from {source}", job_id=job_id, json_keys=list(workout_json.keys()))
            return workout_json, cost
            
        except Exception as e:
            logger.error(f"LLM extraction failed from {source}", job_id=job_id, error=str(e))
            raise Exception(f"LLM extraction failed from {source}: {str(e)}")
    
    # Legacy method for backward compatibility during full OCR
    async def _step_extract_json(self, job_id: str, transcript: str, ocr_texts: List[str]) -> Tuple[Dict[str, Any], float]:
        combined_text = f"{transcript} {' '.join(ocr_texts)}"
        return await self._step_extract_json_from_text(job_id, combined_text, "legacy_combined")
    
    async def _step_validate_schema(self, job_id: str, workout_json: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Sanitize data first
            sanitized_json = sanitize_workout_data(workout_json)
            
            # Validate against schema
            is_valid, errors = validate_workout_json(sanitized_json)
            
            if not is_valid:
                logger.error("Schema validation failed", job_id=job_id, errors=errors)
                raise Exception(f"Schema validation failed: {', '.join(errors)}")
            
            return sanitized_json
        except Exception as e:
            raise Exception(f"Validation failed: {str(e)}")