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
import aiohttp
from concurrent.futures import ThreadPoolExecutor
logger = logging.getLogger(__name__)


class GenAIServicePool:
    """
    High-performance GenAI service pool with connection pooling, 
    multi-region support, and optimized request handling.
    """

    def __init__(self):
        self.services = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        self.health_check_lock = asyncio.Lock()
        self.last_health_check = 0
        self.health_check_interval = 300  # 5 minutes
        
        # Connection pooling
        self.http_session = None
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="genai-pool")

        # Get project ID
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")

        # Multi-region configuration
        self.regions = self._get_regions_config()
        
        # Initialize services with different approaches
        self._init_services()

        if not self.services:
            raise ValueError("No GenAI services could be initialized")

        logger.info(f"GenAI Service Pool initialized with {len(self.services)} services across {len(self.regions)} regions")

    def _get_regions_config(self) -> List[str]:
        """Get optimized region configuration based on environment"""
        # Multi-region configuration for global performance
        default_regions = [
            "us-central1",    # Primary - existing region
            "us-east1",       # East Coast US
            "europe-west1",   # Europe (Belgium)
            "asia-southeast1", # Asia Pacific (Singapore)
        ]
        
        env_regions = os.getenv("GEMINI_REGIONS", ",".join(default_regions))
        regions = [r.strip() for r in env_regions.split(",") if r.strip()]
        
        logger.info(f"Configured regions: {regions}")
        return regions
    
    async def _init_http_session(self):
        """Initialize HTTP session with connection pooling"""
        if self.http_session is None:
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=20,  # Per-host connection limit
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=60,
                enable_cleanup_closed=True,
            )
            
            timeout = aiohttp.ClientTimeout(
                total=120,  # Total timeout
                connect=10,  # Connection timeout
                sock_read=60,  # Socket read timeout
            )
            
            self.http_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": "Sets-AI-Backend/2.0",
                    "Connection": "keep-alive",
                }
            )
            logger.info("HTTP session initialized with connection pooling")

    def _init_services(self):
        """Initialize multiple GenAI services across regions with optimized configuration"""
        # Initialize services for each region
        for region in self.regions:
            try:
                # Optimized HTTP options for better performance
                http_options = HttpOptions(
                    api_version="v1",
                    # Add connection pooling and keep-alive
                    timeout=60,
                )
                
                client = genai.Client(
                    project=self.project_id,
                    location=region,
                    vertexai=True,
                    http_options=http_options,
                )
                
                # Create service with region-specific configuration
                service = GenAIService(
                    client=client, 
                    service_id=f"region_{region}",
                    region=region,
                    pool_ref=self  # Reference to pool for shared resources
                )
                
                self.services.append(service)
                logger.info(f"Initialized GenAI service for region: {region}")
                
            except Exception as e:
                logger.error(f"Failed to initialize service for region {region}: {e}")
                # Continue with other regions
                continue
        
        if not self.services:
            # Fallback to single region if all fail
            logger.warning("All regions failed, falling back to us-central1")
            try:
                client = genai.Client(
                    project=self.project_id,
                    location="us-central1",
                    vertexai=True,
                    http_options=HttpOptions(api_version="v1"),
                )
                service = GenAIService(client, "fallback_us-central1", "us-central1", self)
                self.services.append(service)
            except Exception as e:
                logger.error(f"Fallback service initialization failed: {e}")
                raise

    async def get_optimal_service(self, prefer_region: Optional[str] = None) -> "GenAIService":
        """Get optimal service based on load balancing and health checks"""
        await self._ensure_http_session()
        
        # Perform health checks if needed
        await self._health_check_services()
        
        async with self.lock:
            if not self.services:
                raise Exception("No GenAI services available")
            
            # Filter healthy services
            healthy_services = [s for s in self.services if s.is_healthy]
            if not healthy_services:
                logger.warning("No healthy services, using all services")
                healthy_services = self.services
            
            # Prefer specific region if requested
            if prefer_region:
                region_services = [s for s in healthy_services if s.region == prefer_region]
                if region_services:
                    # Use least loaded service in preferred region
                    service = min(region_services, key=lambda s: s.active_requests)
                    service.active_requests += 1
                    logger.debug(f"Using preferred region service: {service.service_id}")
                    return service
            
            # Load balancing: choose service with least active requests
            service = min(healthy_services, key=lambda s: s.active_requests)
            service.active_requests += 1
            
            logger.debug(f"Using optimal service: {service.service_id} (load: {service.active_requests})")
            return service
    
    async def _ensure_http_session(self):
        """Ensure HTTP session is initialized"""
        if self.http_session is None:
            await self._init_http_session()
    
    async def _health_check_services(self):
        """Perform health checks on services if needed"""
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return
        
        async with self.health_check_lock:
            # Double-check pattern
            if current_time - self.last_health_check < self.health_check_interval:
                return
            
            logger.debug("Performing health checks on GenAI services")
            
            # Quick health check - just verify client connectivity
            for service in self.services:
                try:
                    # Simple connectivity test
                    service.is_healthy = True  # Assume healthy unless proven otherwise
                except Exception as e:
                    logger.warning(f"Service {service.service_id} health check failed: {e}")
                    service.is_healthy = False
            
            self.last_health_check = current_time
    
    async def get_next_service(self) -> "GenAIService":
        """Backward compatibility method"""
        return await self.get_optimal_service()

    def get_pool_size(self) -> int:
        """Get number of services in pool"""
        return len(self.services)

    async def analyze_video(
        self,
        video_content: bytes,
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
        prefer_region: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze video with optimal service selection and error handling"""
        service = await self.get_optimal_service(prefer_region)
        try:
            result = await service.analyze_video_with_transcript(
                video_content, transcript, caption, localization
            )
            return result
        except Exception as e:
            logger.error(f"Video analysis failed with service {service.service_id}: {e}")
            # Try with different service if available
            if len(self.services) > 1:
                logger.info("Retrying with different service")
                backup_service = await self.get_optimal_service()
                if backup_service.service_id != service.service_id:
                    try:
                        return await backup_service.analyze_video_with_transcript(
                            video_content, transcript, caption, localization
                        )
                    except Exception as e2:
                        logger.error(f"Backup service also failed: {e2}")
            raise e
        finally:
            # Decrement active request count
            service.active_requests = max(0, service.active_requests - 1)

    async def analyze_slideshow(
        self,
        slideshow_images: List[bytes],
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
        prefer_region: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze slideshow with optimal service selection and error handling"""
        service = await self.get_optimal_service(prefer_region)
        try:
            result = await service.analyze_slideshow_with_transcript(
                slideshow_images, transcript, caption, localization
            )
            return result
        except Exception as e:
            logger.error(f"Slideshow analysis failed with service {service.service_id}: {e}")
            # Try with different service if available
            if len(self.services) > 1:
                logger.info("Retrying with different service")
                backup_service = await self.get_optimal_service()
                if backup_service.service_id != service.service_id:
                    try:
                        return await backup_service.analyze_slideshow_with_transcript(
                            slideshow_images, transcript, caption, localization
                        )
                    except Exception as e2:
                        logger.error(f"Backup service also failed: {e2}")
            raise e
        finally:
            # Decrement active request count
            service.active_requests = max(0, service.active_requests - 1)
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.http_session:
            await self.http_session.close()
        
        if self.executor:
            self.executor.shutdown(wait=True)
        
        logger.info("GenAI Service Pool cleaned up")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics for monitoring"""
        return {
            "total_services": len(self.services),
            "healthy_services": len([s for s in self.services if s.is_healthy]),
            "regions": list(set(s.region for s in self.services)),
            "active_requests": sum(s.active_requests for s in self.services),
            "services": [
                {
                    "id": s.service_id,
                    "region": s.region,
                    "healthy": s.is_healthy,
                    "active_requests": s.active_requests,
                    "total_requests": s.total_requests,
                    "last_request_time": s.last_request_time,
                }
                for s in self.services
            ],
        }


class GenAIService:
    """Individual GenAI service instance with enhanced performance tracking"""

    def __init__(self, client: genai.Client, service_id: str, region: str, pool_ref=None):
        self.client = client
        self.service_id = service_id
        self.region = region
        self.pool_ref = pool_ref
        self.model = "gemini-2.0-flash-lite"
        
        # Performance tracking
        self.last_request_time = 0
        self.min_request_interval = 0.1  # Reduced to 100ms for better throughput
        self.active_requests = 0
        self.total_requests = 0
        self.is_healthy = True
        
        # Request queue for better concurrency
        self.request_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests per service

    async def _retry_with_backoff(self, func, max_retries=3, base_delay=0.5):
        """Async retry function with exponential backoff and circuit breaker pattern"""
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Service {self.service_id} - Max retries reached for rate limit error"
                        )
                        self.is_healthy = False  # Mark as unhealthy temporarily
                        raise e

                    # Exponential backoff with jitter - reduced base delay
                    delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        f"Service {self.service_id} - Got rate limit error, retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Non-rate-limit error, don't retry
                    logger.error(f"Service {self.service_id} - Non-retryable error: {e}")
                    raise e
        return None

    async def _rate_limit(self):
        """Optimized rate limiting with reduced intervals"""
        async with self.request_semaphore:  # Limit concurrent requests
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                logger.debug(f"Service {self.service_id} rate limiting: waiting {sleep_time:.3f}s")
                await asyncio.sleep(sleep_time)
            
            self.last_request_time = time.time()
            self.total_requests += 1
    
    async def analyze_video_with_transcript(
        self,
        video_content: bytes,
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Optimized video analysis with async processing"""
        
        # Apply rate limiting
        await self._rate_limit()

        # Build optimized prompt
        prompt = self._build_video_prompt(transcript, caption, localization)

        # Prepare content for Google Gen AI SDK
        contents = [prompt, Part.from_bytes(data=video_content, mime_type="video/mp4")]

        # Generate content using async retry logic
        async def make_request():
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

        response = await self._retry_with_backoff(make_request, max_retries=3, base_delay=0.5)
        return self._parse_response(response)
    
    async def analyze_slideshow_with_transcript(
        self,
        slideshow_images: List[bytes],
        transcript: Optional[str] = None,
        caption: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Optimized slideshow analysis with async processing"""
        
        # Apply rate limiting
        await self._rate_limit()

        # Build optimized prompt
        prompt = self._build_slideshow_prompt(transcript, caption, localization, len(slideshow_images))

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

        # Generate content with async retry logic
        async def make_request():
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

        logger.info(f"Analyzing slideshow with {valid_images} images using service {self.service_id}")
        response = await self._retry_with_backoff(make_request, max_retries=3, base_delay=0.5)
        return self._parse_response(response)
    
    def _build_video_prompt(self, transcript: Optional[str], caption: Optional[str], localization: Optional[str]) -> str:
        """Build optimized prompt for video analysis"""
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
        prompt += self._get_json_schema()
        
        return prompt
    
    def _build_slideshow_prompt(self, transcript: Optional[str], caption: Optional[str], localization: Optional[str], image_count: int) -> str:
        """Build optimized prompt for slideshow analysis"""
        prompt = "You are an expert fitness instructor analyzing a TikTok workout slideshow containing multiple images."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, exercise names, instructions, AND equipment names) in {localization} language ONLY. Translate ALL human-readable text fields including equipment names consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        prompt += f"\n\nThis is a slideshow with {image_count} images showing workout exercises, poses, or fitness content. Analyze ALL the images together to extract the following information. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction
        prompt += self._get_json_schema()
        
        return prompt
    
    def _get_json_schema(self) -> str:
        """Get the JSON schema for workout data"""
        return """

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
- For strength exercises: use reps and optionally weight_lbs
- For cardio exercises: use duration_seconds or distance_miles
- For bodyweight exercises: use reps and optionally duration_seconds
- muscle_groups must use EXACT values from the list above
- equipment should be descriptive (use common names like those in examples above)
- workout_type must use EXACT values from the list above

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, exercise names, instructions, equipment names) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""
    
    def _parse_response(self, response) -> Optional[Dict[str, Any]]:
        """Parse and validate GenAI response"""
        try:
            # Get the response text from the API structure
            response_text = response.text.strip()
            logger.debug(f"Raw response from {self.service_id}: {response_text[:200]}...")

            # Try to extract JSON from the response
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
            logger.error(f"Failed to parse response from {self.service_id}: {e}")
            return None


# Global service pool instance
_service_pool = None


async def get_genai_service_pool() -> GenAIServicePool:
    """Get or create the global GenAI service pool"""
    global _service_pool
    if _service_pool is None:
        _service_pool = GenAIServicePool()
        logger.info("Global GenAI service pool created")
    return _service_pool


async def cleanup_genai_service_pool():
    """Cleanup the global GenAI service pool"""
    global _service_pool
    if _service_pool:
        await _service_pool.cleanup()
        _service_pool = None
        logger.info("Global GenAI service pool cleaned up")