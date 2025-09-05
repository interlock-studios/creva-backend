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
        """Analyze video/post with Gemini 2.0 Flash for relationship content"""

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt
        prompt = "You are an expert relationship coach and lifestyle content analyst analyzing social media content."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, tips, location) in {localization} language ONLY. Translate ALL human-readable text fields consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        prompt += "\n\nAnalyze this social media post/video and extract relationship, dating, or lifestyle content. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction
        prompt += """

Required JSON structure:
{
  "title": "descriptive title for the content",
  "description": "brief description of the content or null",
  "image": "main image URL from the post/video or null",
  "location": "location mentioned or tagged in the content or null",
  "content_type": "type of content (examples: date_idea, relationship_advice, couples_activity, lifestyle_tip, romantic_gesture, communication_tip, self_care) or null",
  "mood": "mood or vibe (examples: romantic, fun, adventurous, cozy, intimate, playful, serious, inspiring) or null",
  "occasion": "relevant occasion (examples: date_night, anniversary, valentine, weekend, vacation, everyday, special_occasion) or null",
  "tips": ["array of extracted tips or advice points"] or null,
  "tags": ["array of relevant hashtags or tags"] or null,
  "creator": "creator username or null"
}

EXTRACTION GUIDELINES:
- Focus on relationship, dating, and lifestyle content
- Extract the main image URL if visible in the video/post
- Identify any location mentioned in captions, tags, or content
- Categorize the content type based on the main theme
- Extract actionable tips or advice if present
- Identify the mood and occasion if relevant
- Include relevant hashtags or tags

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, tips, location) MUST be in the SAME target language consistently throughout the entire response.

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

            parsed_json = json.loads(response_text)
            logger.debug(f"Gemini returned image field: {parsed_json.get('image', 'NOT_SET')}")
            return parsed_json
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
        prompt = "You are an expert relationship coach and lifestyle content analyst analyzing a social media slideshow."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, tips, location) in {localization} language ONLY. Translate ALL human-readable text fields consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        image_count = len(slideshow_images)
        prompt += f"\n\nThis is a slideshow with {image_count} images. Analyze ALL the images together to extract relationship, dating, or lifestyle content. Use 'slideshow_image_1' as placeholder for the main image URL. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction

        prompt += """

Required JSON structure:
{
  "title": "descriptive title for the content",
  "description": "brief description of the content or null",
  "image": "use 'slideshow_image_1' as placeholder",
  "location": "location mentioned or visible in the content or null",
  "content_type": "type of content (examples: date_idea, relationship_advice, couples_activity, lifestyle_tip, romantic_gesture, communication_tip, self_care) or null",
  "mood": "mood or vibe (examples: romantic, fun, adventurous, cozy, intimate, playful, serious, inspiring) or null",
  "occasion": "relevant occasion (examples: date_night, anniversary, valentine, weekend, vacation, everyday, special_occasion) or null",
  "tips": ["array of extracted tips or advice points from all images"] or null,
  "tags": ["array of relevant hashtags or tags"] or null,
  "creator": "creator username or null"
}

EXTRACTION GUIDELINES:
- Focus on relationship, dating, and lifestyle content
- Use 'slideshow_image_1' as placeholder for the main image field
- Look for location information in images or captions
- Analyze ALL images together to understand the complete story or advice
- Extract actionable tips or advice if present across the images
- Identify the overall mood and occasion
- Include relevant hashtags or tags

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, tips, location) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""

        # Prepare content with multiple images
        contents = [prompt]

        # Add all slideshow images to the analysis
        valid_images = 0
        for i, image_content in enumerate(slideshow_images):
            if image_content:  # Skip empty image content
                try:
                    contents.append(Part.from_bytes(data=image_content, mime_type="image/jpeg"))
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

            parsed_json = json.loads(response_text)
            logger.debug(
                f"Gemini slideshow returned image field: {parsed_json.get('image', 'NOT_SET')}"
            )
            return parsed_json
        except Exception as e:
            logger.error(f"Failed to parse slideshow response: {e}")
            return None
