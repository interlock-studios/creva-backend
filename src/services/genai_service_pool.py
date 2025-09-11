from google import genai
from google.genai.types import HttpOptions, Part, GenerateContentConfig

from google.auth import default
from google.oauth2 import service_account
from typing import Dict, Any, Optional, List
import json
import os
import time
import random
import asyncio
import logging

logger = logging.getLogger(__name__)


class GenAIServicePool:
    """Pool of GenAI services for distributed rate limiting"""

    def __init__(self):
        self.services = []
        self.current_index = 0
        self.lock = asyncio.Lock()

        # Get project ID
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")

        # Initialize services with different approaches
        self._init_services()

        if not self.services:
            raise ValueError("No GenAI services could be initialized")

        logger.info(f"Initialized GenAI service pool with {len(self.services)} services")

    def _init_services(self):
        """Initialize multiple GenAI services"""

        # Method 1: Multiple service account files
        sa_files = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILES", "").split(",")
        for sa_file in sa_files:
            sa_file = sa_file.strip()
            if sa_file and os.path.exists(sa_file):
                try:
                    credentials = service_account.Credentials.from_service_account_file(sa_file)
                    # Use local region for GenAI calls
                    local_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
                    client = genai.Client(
                        project=self.project_id,
                        location=local_region,
                        vertexai=True,
                        credentials=credentials,
                        http_options=HttpOptions(api_version="v1"),
                    )
                    service = GenAIService(client, f"sa_file_{len(self.services)}")
                    self.services.append(service)
                    logger.info(f"Loaded service account from file: {sa_file}")
                except Exception as e:
                    logger.error(f"Failed to load service account from {sa_file}: {e}")

        # Method 2: Multiple service account JSON strings (for Cloud Run)
        sa_jsons = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSONS", "").split(
            "|||"
        )  # Use ||| as delimiter
        for i, sa_json in enumerate(sa_jsons):
            sa_json = sa_json.strip()
            if sa_json:
                try:
                    sa_info = json.loads(sa_json)
                    credentials = service_account.Credentials.from_service_account_info(sa_info)
                    # Use local region for GenAI calls
                    local_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
                    client = genai.Client(
                        project=self.project_id,
                        location=local_region,
                        vertexai=True,
                        credentials=credentials,
                        http_options=HttpOptions(api_version="v1"),
                    )
                    service = GenAIService(client, f"sa_json_{i}")
                    self.services.append(service)
                    logger.info(f"Loaded service account from JSON string {i}")
                except Exception as e:
                    logger.error(f"Failed to load service account from JSON {i}: {e}")

        # Method 3: Default credentials (if no explicit accounts provided)
        if not self.services:
            try:
                # This will use the default service account in Cloud Run
                credentials, _ = default()
                # Use local region for GenAI calls
                local_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
                client = genai.Client(
                    project=self.project_id,
                    location=local_region,
                    vertexai=True,
                    credentials=credentials,
                    http_options=HttpOptions(api_version="v1"),
                )
                service = GenAIService(client, "default")
                self.services.append(service)
                logger.info("Using default credentials")
            except Exception as e:
                logger.error(f"Failed to use default credentials: {e}")

        # Method 4: Multiple locations for same project (distributes load)
        locations = os.getenv("GEMINI_LOCATIONS", "us-central1").split(",")
        if len(locations) > 1 and self.services:
            # Use the first service's credentials for other locations
            base_credentials = self.services[0].client._credentials
            for location in locations[1:]:
                location = location.strip()
                try:
                    client = genai.Client(
                        project=self.project_id,
                        location=location,
                        vertexai=True,
                        credentials=base_credentials,
                        http_options=HttpOptions(api_version="v1"),
                    )
                    service = GenAIService(client, f"location_{location}")
                    self.services.append(service)
                    logger.info(f"Added service for location: {location}")
                except Exception as e:
                    logger.error(f"Failed to add service for location {location}: {e}")

    async def get_next_service(self) -> "GenAIService":
        """Get next available service in round-robin fashion"""
        async with self.lock:
            if not self.services:
                raise Exception("No GenAI services available")

            # Simple round-robin
            service = self.services[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.services)

            logger.debug(f"Using GenAI service: {service.service_id}")
            return service

    def get_pool_size(self) -> int:
        """Get number of services in pool"""
        return len(self.services)

    async def analyze_video(
        self,
        video_content: bytes,
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze video using round-robin GenAI service selection"""
        service = await self.get_next_service()
        return await service.analyze_video_with_transcript(
            video_content, transcript, caption, localization
        )

    async def analyze_slideshow(
        self,
        slideshow_images: List[bytes],
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze slideshow using round-robin GenAI service selection"""
        service = await self.get_next_service()
        return await service.analyze_slideshow_with_transcript(
            slideshow_images, transcript, caption, localization
        )


class GenAIService:
    """Individual GenAI service instance"""

    def __init__(self, client: genai.Client, service_id: str):
        self.client = client
        self.service_id = service_id
        self.model = "gemini-2.0-flash-lite"
        self.last_request_time = 0
        self.min_request_interval = 0.2  # 200ms between requests per service

    def _retry_with_backoff(self, func, max_retries=3, base_delay=1):
        """Retry function with exponential backoff for 429 errors"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Service {self.service_id} - Max retries reached for 429 error"
                        )
                        raise e

                    # Exponential backoff with jitter
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Service {self.service_id} - Got 429 error, retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                else:
                    # Non-429 error, don't retry
                    raise e
        return None

    async def _rate_limit(self):
        """Ensure minimum time between requests for this service"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.debug(f"Service {self.service_id} - Rate limiting: waiting {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)
        self.last_request_time = time.time()

    async def analyze_video_with_transcript(
        self,
        video_content: bytes,
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze video with Gemini 2.0 Flash"""

        # Apply rate limiting for this specific service
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
  "duration_minutes": estimatedtotal workout duration in minutes (including rest periods) as integer or null,
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

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, exercise names, instructions, equipment names) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""

        # Prepare content
        contents = [prompt, Part.from_bytes(data=video_content, mime_type="video/mp4")]

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

        logger.info(f"Service {self.service_id} - Analyzing video")
        response = self._retry_with_backoff(make_request, max_retries=5, base_delay=2)

        # Parse response
        try:
            response_text = response.text.strip()
            logger.debug(f"Service {self.service_id} - Raw response: {response_text[:500]}...")

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
            logger.error(f"Service {self.service_id} - Failed to parse response: {e}")
            return None

    async def analyze_slideshow_with_transcript(
        self,
        slideshow_images: List[bytes],
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze slideshow images with Gemini 2.0 Flash"""

        # Apply rate limiting for this specific service
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
          "set_type": "reps" or "duration" or "distance" (indicates the primary measurement type for this set),
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
                logger.warning(
                    f"Service {self.service_id} - Failed to convert slideshow image {i} to JPEG; skipping"
                )
                continue
            try:
                contents.append(Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"))
                valid_images += 1
            except Exception as e:
                logger.warning(
                    f"Service {self.service_id} - Failed to add image {i} to analysis: {e}"
                )

        if valid_images == 0:
            logger.error(f"Service {self.service_id} - No valid images found in slideshow")
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

        logger.info(f"Service {self.service_id} - Analyzing slideshow with {valid_images} images")
        response = self._retry_with_backoff(make_request, max_retries=5, base_delay=2)

        # Parse response
        try:
            response_text = response.text.strip()
            logger.debug(
                f"Service {self.service_id} - Raw slideshow response: {response_text[:500]}..."
            )

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
            logger.error(f"Service {self.service_id} - Failed to parse slideshow response: {e}")
            return None
