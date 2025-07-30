from google.cloud import aiplatform
import structlog
from typing import Dict, Any, Optional, List
import json

logger = structlog.get_logger()


class VertexAIService:
    def __init__(self):
        aiplatform.init(location="us-central1")
        self.model = "gemini-pro"
    
    def get_extraction_prompt(self, transcript: str, ocr_texts: List[str]) -> str:
        combined_text = f"TRANSCRIPT: {transcript}\n\nOCR TEXT: {' '.join(ocr_texts)}"
        
        return f"""You are an expert fitness instructor analyzing a TikTok workout video. Extract structured workout information from the provided transcript and OCR text.

INPUT TEXT:
{combined_text}

TASK: Extract workout information and return ONLY valid JSON matching this exact schema:

{{
  "title": "string (1-200 chars)",
  "description": "string or null (max 1000 chars)",
  "workout_type": "strength|cardio|hiit|yoga|stretching|bodyweight|mixed",
  "duration_minutes": integer or null (1-480),
  "difficulty_level": integer (1-10),
  "exercises": [
    {{
      "name": "string (1-200 chars)",
      "muscle_groups": ["chest|back|shoulders|biceps|triceps|legs|glutes|core|full_body"],
      "equipment": "none|dumbbells|barbell|resistance_bands|kettlebell|machine|bodyweight|other",
      "sets": [
        {{
          "reps": integer or null (1-1000),
          "weight_lbs": number or null (0-10000),
          "duration_seconds": integer or null (1-7200),
          "distance_miles": number or null (0-1000),
          "rest_seconds": integer or null (0-3600)
        }}
      ],
      "instructions": "string or null (max 1000 chars)"
    }}
  ],
  "tags": ["string"] or null (max 20 items, 50 chars each),
  "creator": "string or null (max 100 chars)"
}}

RULES:
1. Return ONLY valid JSON, no explanations
2. Infer missing information reasonably
3. Use "bodyweight" equipment for bodyweight exercises
4. Set difficulty 1-3 for beginners, 4-6 for intermediate, 7-10 for advanced
5. Extract all exercises mentioned
6. For time-based exercises, use duration_seconds instead of reps

JSON OUTPUT:"""
    
    async def extract_workout_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Fast extraction from any text source (caption, transcript, etc.)"""
        try:
            prompt = self.get_text_extraction_prompt(text)
            
            model = aiplatform.GenerativeModel(self.model)
            response = model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": 512,
                    "temperature": 0.1,
                    "top_p": 0.8,
                }
            )
            
            response_text = response.text.strip()
            
            # Try to parse JSON response
            try:
                workout_json = json.loads(response_text)
                logger.info(
                    "Workout JSON extracted from text",
                    exercises_count=len(workout_json.get("exercises", [])),
                    workout_type=workout_json.get("workout_type"),
                    text_length=len(text)
                )
                return workout_json
                
            except json.JSONDecodeError as e:
                logger.error("Failed to parse LLM JSON response", error=str(e), response=response_text[:500])
                return None
            
        except Exception as e:
            logger.error("Vertex AI text extraction failed", error=str(e))
            raise
    
    def get_text_extraction_prompt(self, text: str) -> str:
        """Optimized prompt for single text input"""
        return f"""You are an expert fitness instructor analyzing TikTok workout content. Extract structured workout information from the text below.

INPUT TEXT:
{text}

TASK: Extract workout information and return ONLY valid JSON matching this exact schema:

{{
  "title": "string (1-200 chars)",
  "description": "string or null (max 1000 chars)",
  "workout_type": "strength|cardio|hiit|yoga|stretching|bodyweight|mixed",
  "duration_minutes": integer or null (1-480),
  "difficulty_level": integer (1-10),
  "exercises": [
    {{
      "name": "string (1-200 chars)",
      "muscle_groups": ["chest|back|shoulders|biceps|triceps|legs|glutes|core|full_body"],
      "equipment": "none|dumbbells|barbell|resistance_bands|kettlebell|machine|bodyweight|other",
      "sets": [
        {{
          "reps": integer or null (1-1000),
          "weight_lbs": number or null (0-10000),
          "duration_seconds": integer or null (1-7200),
          "distance_miles": number or null (0-1000),
          "rest_seconds": integer or null (0-3600)
        }}
      ],
      "instructions": "string or null (max 1000 chars)"
    }}
  ],
  "tags": ["string"] or null (max 20 items, 50 chars each),
  "creator": "string or null (max 100 chars)"
}}

RULES:
1. Return ONLY valid JSON, no explanations
2. Infer missing information reasonably from context
3. Use "bodyweight" equipment for bodyweight exercises
4. Set difficulty 1-3 for beginners, 4-6 for intermediate, 7-10 for advanced
5. Extract all exercises mentioned
6. For time-based exercises, use duration_seconds instead of reps
7. If text is insufficient, create a minimal valid workout structure

JSON OUTPUT:"""

    async def extract_workout_json(self, transcript: str, ocr_texts: List[str]) -> Optional[Dict[str, Any]]:
        """Legacy method - combines transcript and OCR for backward compatibility"""
        combined_text = f"TRANSCRIPT: {transcript}\n\nOCR TEXT: {' '.join(ocr_texts)}"
        return await self.extract_workout_json_from_text(combined_text)