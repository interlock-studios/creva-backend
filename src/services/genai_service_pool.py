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
        """Analyze video/post with Gemini 2.0 Flash for relationship content"""

        # Apply rate limiting for this specific service
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

            parsed_json = json.loads(response_text)
            logger.debug(f"Service {self.service_id} - Gemini returned image field: {parsed_json.get('image', 'NOT_SET')}")
            return parsed_json
        except Exception as e:
            logger.error(f"Service {self.service_id} - Failed to parse response: {e}")
            try:
                logger.error(f"Service {self.service_id} - Full response object: {response}")
            except Exception:
                logger.error(f"Service {self.service_id} - Could not access response object")
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

            parsed_json = json.loads(response_text)
            logger.debug(
                f"Service {self.service_id} - Gemini slideshow returned image field: {parsed_json.get('image', 'NOT_SET')}"
            )
            return parsed_json
        except Exception as e:
            logger.error(f"Service {self.service_id} - Failed to parse slideshow response: {e}")
            return None
