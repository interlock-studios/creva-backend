from google import genai
from google.genai.types import HttpOptions, Part, GenerateContentConfig
from typing import Dict, Any, Optional, List
import json
import logging
import time
import random
import asyncio
import os

logger = logging.getLogger(__name__)


class GenAIService:
    def __init__(self, config=None):
        # Get configuration
        if config is None:
            from src.services.config_validator import AppConfig

            config = AppConfig.from_env()

        # Get project ID from configuration
        project_id = config.project_id
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID not set in configuration")

        # Get local region for GenAI calls (default to us-central1)
        local_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
        
        # Initialize Google Gen AI SDK with Vertex AI backend using local region
        self.client = genai.Client(
            project=project_id,
            location=local_region,
            vertexai=True,  # Use Vertex AI backend
            http_options=HttpOptions(api_version="v1"),
        )
        self.model = "gemini-2.0-flash-lite"
        self.last_request_time = 0
        self.min_request_interval = config.rate_limiting.genai_min_interval
        self.max_retries = config.rate_limiting.genai_max_retries

    async def _retry_with_backoff(self, func, max_retries=None, base_delay=1):
        """Retry function with exponential backoff for 429 errors"""
        if max_retries is None:
            max_retries = self.max_retries
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) reached for 429 error")
                        raise e

                    # Exponential backoff with jitter
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Got 429 error, retrying in {delay:.2f} seconds "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Non-429 error, don't retry
                    raise e
        return None

    async def _rate_limit(self):
        """Ensure minimum time between requests"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.info(f"Rate limiting: waiting {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        self.last_request_time = time.time()

    async def analyze_video_with_transcript(
        self,
        video_content: bytes,
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze video with Gemini 2.0 Flash using Google Gen AI SDK"""

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt
        prompt = "You are an expert fitness instructor analyzing a TikTok workout video."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, exercise names, instructions, AND equipment names) in {localization} language ONLY. Translate ALL human-readable text fields including equipment names consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        prompt += "\n\nAnalyze this workout video and extract the following information. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction
        prompt += """

Required JSON structure:
{
  "title": "descriptive workout title",
  "description": "brief description of the workout or null",
  "workout_type": "MUST be one of: push, pull, legs, upper body, lower body, full body, strength, cardio, HIIT, hypertrophy, endurance, power, mobility, flexibility",
  "duration_minutes": total workout duration in minutes (including rest periods) as integer or null,
  "difficulty_level": integer from 1 to 10 (1=beginner, 10=expert),
  "exercises": [
    {
      "name": "exercise name",
      "muscle_groups": ["MUST use exact values from: abs, arms, back, biceps, calves, chest, core, forearms, glutes, hamstrings, lats, legs, lower back, obliques, quads, shoulders, traps, triceps"],
      "equipment": "equipment needed - MUST be translated to the specified language if localization is provided (examples: Barbell, Dumbbells, Kettlebell, Machine, Cable, Bodyweight, Resistance Band, Medicine Ball, Pull-up Bar, Dip Station, None)",
      "sets": [
        {
          "set_type": "reps" or "duration" or "distance" (indicates the primary measurement type for this set),
          "reps": integer or null,
          "weight_lbs": number or null,
          "duration_seconds": integer or null,
          "distance_miles": number or null,
          "rest_seconds": integer or null (defaults to 90 if not specified)
        }
      ],
      "instructions": "brief instructions or null"
    }
  ],
  "tags": ["array of relevant tags"] or null,
  "creator": "creator name or null"
}

CRITICAL REQUIREMENTS:
- Each exercise MUST have at least 1 set
- Each set MUST include at least ONE measurement (reps, weight_lbs, duration_seconds, or distance_miles)
- Each set MUST include a set_type field that indicates the primary measurement:
  * "reps" when the primary measurement is repetitions (use with reps field)
  * "duration" when the primary measurement is time (use with duration_seconds field)
  * "distance" when the primary measurement is distance (use with distance_miles field)
- For exercises described with TIME (e.g., "30 seconds of jumping jacks", "hold plank for 45 seconds"): use duration_seconds and set_type: "duration"
- For exercises described with REPETITIONS (e.g., "10 jumping jacks", "15 push-ups"): use reps and set_type: "reps"
- For strength exercises with weights: use reps, weight_lbs, and set_type: "reps"
- For cardio exercises: use duration_seconds OR distance_miles with appropriate set_type ("duration" or "distance")
- The SAME exercise can use different measurement types in different sets (e.g., "10 jumping jacks" = reps + set_type: "reps", "jumping jacks for 30 seconds" = duration_seconds + set_type: "duration")
- muscle_groups must use EXACT values from the list above
- equipment should be descriptive (use common names like those in examples above)
- workout_type must use EXACT values from the list above

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, exercise names, instructions, equipment names) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""

        # Prepare content for Google Gen AI SDK
        contents = [prompt, Part.from_bytes(data=video_content, mime_type="video/mp4")]

        # Generate content using Google Gen AI SDK with retry logic
        def make_request():
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=GenerateContentConfig(
                    max_output_tokens=2048,  # Increased for more complex workouts
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",  # Force JSON response
                ),
            )

        response = await self._retry_with_backoff(make_request, max_retries=5, base_delay=2)

        # Parse response
        try:
            # Get the response text from the new API structure
            response_text = response.text.strip()
            logger.debug(f"Raw Gemini response: {response_text[:500]}...")  # Log first 500 chars

            # Try to extract JSON from the response
            # Sometimes Gemini adds markdown formatting or explanations
            if "```json" in response_text:
                # Extract JSON from markdown code block
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                # Extract from generic code block
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            try:
                logger.error(f"Full response object: {response}")
            except Exception:
                logger.error("Could not access response object")
            return None

    async def analyze_slideshow_with_transcript(
        self,
        slideshow_images: List[bytes],
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze slideshow images with Gemini 2.0 Flash"""

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt for slideshow analysis
        prompt = "You are an expert fitness instructor analyzing a TikTok workout slideshow containing multiple images."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, exercise names, instructions, AND equipment names) in {localization} language ONLY. Translate ALL human-readable text fields including equipment names consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        image_count = len(slideshow_images)
        prompt += f"\n\nThis is a slideshow with {image_count} images showing workout exercises, poses, or fitness content. Analyze ALL the images together to extract the following information. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction

        prompt += """

Required JSON structure:
{
  "title": "descriptive workout title",
  "description": "brief description of the workout or null",
  "workout_type": "MUST be one of: push, pull, legs, upper body, lower body, full body, strength, cardio, HIIT, hypertrophy, endurance, power, mobility, flexibility",
  "duration_minutes": estimated total workout duration in minutes (including rest periods) as integer or null,
  "difficulty_level": integer from 1 to 10 (1=beginner, 10=expert),
  "exercises": [
    {
      "name": "exercise name",
      "muscle_groups": ["MUST use exact values from: abs, arms, back, biceps, calves, chest, core, forearms, glutes, hamstrings, lats, legs, lower back, obliques, quads, shoulders, traps, triceps"],
      "equipment": "equipment needed - MUST be translated to the specified language if localization is provided (examples: Barbell, Dumbbells, Kettlebell, Machine, Cable, Bodyweight, Resistance Band, Medicine Ball, Pull-up Bar, Dip Station, None)",
      "sets": [
        {
          "set_type": "reps" or "duration" (indicates the primary measurement type for this set),
          "reps": integer or null,
          "weight_lbs": number or null,
          "duration_seconds": integer or null,
          "distance_miles": number or null,
          "rest_seconds": integer or null (defaults to 90 if not specified)
        }
      ],
      "instructions": "detailed instructions or null"
    }
  ],
  "tags": ["array of relevant tags"] or null,
  "creator": "creator name or null"
}

CRITICAL REQUIREMENTS:
- Each exercise MUST have at least 1 set
- Each set MUST include at least ONE measurement (reps, weight_lbs, duration_seconds, or distance_miles)
- Each set MUST include a set_type field that indicates the primary measurement:
  * "reps" when the primary measurement is repetitions (use with reps field)
  * "duration" when the primary measurement is time (use with duration_seconds field)
  * "distance" when the primary measurement is distance (use with distance_miles field)
- For exercises described with TIME (e.g., "30 seconds of jumping jacks", "hold plank for 45 seconds"): use duration_seconds and set_type: "duration"
- For exercises described with REPETITIONS (e.g., "10 jumping jacks", "15 push-ups"): use reps and set_type: "reps"
- For strength exercises with weights: use reps, weight_lbs, and set_type: "reps"
- For cardio exercises: use duration_seconds OR distance_miles with appropriate set_type ("duration" or "distance")
- The SAME exercise can use different measurement types in different sets (e.g., "10 jumping jacks" = reps + set_type: "reps", "jumping jacks for 30 seconds" = duration_seconds + set_type: "duration")
- muscle_groups must use EXACT values from the list above
- equipment should be descriptive (use common names like those in examples above)
- workout_type must use EXACT values from the list above
- Analyze ALL images together to understand the complete workout sequence

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, exercise names, instructions, equipment names) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""

        # Prepare content with multiple images
        contents = [prompt]

        # Add all slideshow images to the analysis (convert to JPEG if needed)
        from src.utils.image_converter import convert_image_to_jpeg

        valid_images = 0
        for i, image_content in enumerate(slideshow_images):
            if not image_content:
                continue
            jpeg_bytes = convert_image_to_jpeg(image_content)
            if not jpeg_bytes:
                logger.warning(f"Failed to convert slideshow image {i} to JPEG; skipping")
                continue
            try:
                contents.append(Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"))
                valid_images += 1
            except Exception as e:
                logger.warning(f"Failed to add image {i} to analysis: {e}")

        if valid_images == 0:
            logger.error("No valid images found in slideshow")
            return None

        # Generate content with retry logic
        def make_request():
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                ),
            )

        logger.info(f"Analyzing slideshow with {valid_images} images")
        response = await self._retry_with_backoff(make_request, max_retries=5, base_delay=2)

        # Parse response
        try:
            response_text = response.text.strip()
            logger.debug(f"Raw slideshow response: {response_text[:500]}...")

            # Clean up response if needed
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to parse slideshow response: {e}")
            return None
