from google.cloud import speech
import structlog
from typing import Optional
import io

logger = structlog.get_logger()


class SpeechService:
    def __init__(self):
        self.client = speech.SpeechClient()
    
    async def transcribe_audio(self, audio_content: bytes) -> Optional[str]:
        try:
            audio = speech.RecognitionAudio(content=audio_content)
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="en-US",
                model="latest_long",
                enable_automatic_punctuation=True,
                enable_word_confidence=True,
                enable_word_time_offsets=True,
            )
            
            response = self.client.recognize(config=config, audio=audio)
            
            transcript_parts = []
            total_confidence = 0
            word_count = 0
            
            for result in response.results:
                transcript_parts.append(result.alternatives[0].transcript)
                
                # Calculate average confidence
                for word in result.alternatives[0].words:
                    total_confidence += word.confidence
                    word_count += 1
            
            if not transcript_parts:
                return None
            
            transcript = " ".join(transcript_parts)
            avg_confidence = total_confidence / word_count if word_count > 0 else 0
            
            logger.info(
                "Audio transcribed",
                transcript_length=len(transcript),
                confidence=avg_confidence,
                word_count=word_count
            )
            
            return transcript
            
        except Exception as e:
            logger.error("Speech transcription failed", error=str(e))
            raise