from google import genai
from google.genai.types import HttpOptions, Part, GenerateContentConfig
from typing import Dict, Any, Optional, List
import json
import logging
import time
import random
import asyncio
import os
import io
try:
    from PIL import Image
    import pillow_heif
    # Register HEIF opener with PIL
    pillow_heif.register_heif_opener()
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

# Video format categories - how the video is produced/presented
VIDEO_FORMATS = [
    "voiceover",           # Voice narration over footage/B-roll
    "talking_head",        # Creator speaking directly to camera
    "talking_back_forth",  # Two perspectives/arguments presented
    "reaction",            # Reacting to other content
    "setting_changes",     # Multiple location/outfit changes
    "whiteboard",          # Text/drawing on screen explanations
    "shot_angle_change",   # Dynamic camera angle cuts
    "multitasking",        # Creator doing activity while talking
    "visual",              # Primarily visual content, minimal talking
    "green_screen",        # Green screen background content
    "clone",               # Same person appears multiple times
    "slideshow",           # Image carousel with text/voiceover
    "tutorial",            # Step-by-step how-to
    "duet",                # Side-by-side with another video (TikTok)
    "stitch",              # Response to another creator's clip
    "pov",                 # Point-of-view storytelling
    "before_after",        # Transformation/comparison
    "day_in_life",         # DITL vlog format
    "interview",           # Q&A or interview style
    "list",                # Listicle (5 tips, 10 things, etc.)
    "other"                # Doesn't fit above categories
]

# Content niche/category - what topic the video is about
CONTENT_NICHES = [
    "fitness",        # Gym, workout, bodybuilding, yoga
    "food",           # Cooking, recipes, meal prep, restaurants
    "business",       # Entrepreneurship, startups, marketing
    "finance",        # Investing, budgeting, crypto, real estate
    "tech",           # Software, AI, gadgets, coding
    "beauty",         # Skincare, makeup, haircare
    "fashion",        # Outfits, styling, shopping
    "lifestyle",      # Day in life, routines, organization
    "education",      # Study tips, learning, career advice
    "entertainment",  # Comedy, skits, memes, trends
    "motivation",     # Mindset, self-improvement, productivity
    "relationships",  # Dating, marriage, family dynamics
    "parenting",      # Kids, pregnancy, family life
    "health",         # Wellness, mental health, medical
    "travel",         # Destinations, tips, vlogs
    "gaming",         # Gameplay, reviews, esports
    "music",          # Covers, production, dance
    "art",            # Drawing, design, DIY, crafts
    "pets",           # Dogs, cats, animals
    "sports",         # Specific sports content
    "other"           # Catch-all for uncategorized
]


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
        description: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze video/post with Gemini 2.0 Flash for creator content extraction"""

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt for creator content extraction
        prompt = "You are an expert content analyst specializing in extracting transcripts and hooks from social media videos for content creators."

        if transcript:
            prompt += f"\n\nEXISTING TRANSCRIPT (if available):\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        if description:
            prompt += f"\n\nDESCRIPTION:\n{description}"

        prompt += """

TASK: Analyze this video and extract the full transcript, hook, format, and niche. Content creators save videos to study hooks, scripts, and content styles - your job is to provide accurate, complete analysis.

Return your response as a valid JSON object with NO additional text, explanations, or formatting.

Required JSON structure:
{
  "title": "short, descriptive title for the video content",
  "description": "brief 1-2 sentence summary of what the video is about",
  "transcript": "FULL transcript of EVERYTHING said in the video. This is PRIORITY #1. Include all spoken words, including filler words, pauses, and natural speech patterns. If no speech, describe what's happening.",
  "hook": "The attention-grabbing opening (first 10-30 seconds). This is the line or phrase that captures viewer attention immediately. Extract the exact opening words/hook used.",
  "format": "video production format (see FORMAT CLASSIFICATION below)",
  "niche": "primary content category (see NICHE CLASSIFICATION below)",
  "niche_detail": "specific subcategory or topic detail (e.g., 'meal prep for bodybuilders', 'startup marketing tips')",
  "secondary_niches": ["array of secondary topic categories if video spans multiple niches"] or null,
  "creator": "creator username from the post or null",
  "platform": "tiktok or instagram based on content style",
  "tags": ["array of relevant hashtags from the post"] or null
}

TRANSCRIPT EXTRACTION (PRIORITY #1):
- Extract EVERY word spoken in the video
- Maintain natural speech flow including "um", "like", "you know" etc.
- Include emphasis and emotion indicators when clear [laughs], [pauses]
- For music-only videos, note "[No speech - background music]"
- For text-on-screen videos, transcribe the on-screen text
- Combine any existing transcript with what you hear in the video
- Be thorough - creators need complete transcripts to study scripts

HOOK EXTRACTION (PRIORITY #2):
- The hook is typically the first 10-30 seconds
- It's the attention-grabbing opening that makes viewers stop scrolling
- Examples: "You're doing this wrong...", "Stop everything and watch this...", "I can't believe I'm sharing this..."
- Extract the EXACT words used as the hook
- If the video jumps right into content, the hook IS the opening content

FORMAT CLASSIFICATION:
Classify the video's production style. Choose ONE primary format:
- "voiceover": Voice narration over footage/B-roll, creator not on screen
- "talking_head": Creator speaking directly to camera, single angle
- "talking_back_forth": Two perspectives or arguments presented (like angel/devil on shoulders)
- "reaction": Reacting to other content shown on screen
- "setting_changes": Multiple locations or outfit changes throughout
- "whiteboard": Text, drawings, or explanations written on screen
- "shot_angle_change": Dynamic camera angles, multiple cuts
- "multitasking": Creator doing an activity while talking (cooking, cleaning, etc.)
- "visual": Primarily visual content with minimal or no talking
- "green_screen": Green screen background with creator overlaid
- "clone": Same person appears multiple times in frame
- "slideshow": Image carousel with text or voiceover
- "tutorial": Step-by-step instructional content
- "duet": Side-by-side with another video (TikTok duet feature)
- "stitch": Response starting with another creator's clip
- "pov": Point-of-view storytelling format
- "before_after": Transformation or comparison content
- "day_in_life": Day in the life vlog format
- "interview": Q&A or interview style with questions
- "list": Listicle format (5 tips, 10 things, etc.)
- "other": Doesn't fit above categories

NICHE CLASSIFICATION:
Identify the primary topic/category. Choose ONE primary niche:
- "fitness": Gym, workout, bodybuilding, yoga, exercise
- "food": Cooking, recipes, meal prep, restaurants, eating
- "business": Entrepreneurship, startups, marketing, sales
- "finance": Investing, budgeting, crypto, real estate, money
- "tech": Software, AI, gadgets, coding, apps
- "beauty": Skincare, makeup, haircare, cosmetics
- "fashion": Outfits, styling, shopping, clothing
- "lifestyle": Daily routines, organization, productivity hacks
- "education": Study tips, learning, academic content
- "entertainment": Comedy, skits, memes, trends, pop culture
- "motivation": Mindset, self-improvement, inspirational
- "relationships": Dating, marriage, family dynamics, social
- "parenting": Kids, pregnancy, family life, motherhood
- "health": Wellness, mental health, medical, nutrition
- "travel": Destinations, travel tips, adventure, vlogs
- "gaming": Gameplay, game reviews, esports, streaming
- "music": Covers, production, dance, musical content
- "art": Drawing, design, DIY, crafts, creative
- "pets": Dogs, cats, animals, pet care
- "sports": Specific sports, athletics, training
- "other": Doesn't fit above categories

For niche_detail, provide a more specific description (e.g., if niche is "fitness", detail might be "home workout routines for beginners").

EXAMPLE OUTPUT:
{
  "title": "5 Ways to Grow Your TikTok",
  "description": "Creator shares proven strategies for growing a TikTok following, including posting frequency and engagement tips.",
  "transcript": "Hey everyone! Today I'm going to share 5 ways to grow your TikTok account. Number one - post consistently. I'm talking at least once a day, ideally twice. Number two - engage with your audience. Reply to every single comment in the first hour. Number three - use trending sounds. The algorithm loves trending audio. Number four - hook them in the first second. You have like one second to grab attention. And number five - be authentic. People can tell when you're being fake. Try these out and let me know how it goes!",
  "hook": "Hey everyone! Today I'm going to share 5 ways to grow your TikTok account.",
  "format": "talking_head",
  "niche": "business",
  "niche_detail": "social media growth strategies for content creators",
  "secondary_niches": ["education"],
  "creator": "@socialmediaguru",
  "platform": "tiktok",
  "tags": ["#tiktokgrowth", "#contentcreator", "#socialmediatips", "#fyp"]
}

IMPORTANT: 
- Your response must be ONLY the JSON object
- No markdown formatting, no code blocks, no explanations
- Transcript accuracy is the most important thing - creators rely on this
- Format and niche classification helps creators find similar content"""

        # Prepare content for Google Gen AI SDK
        contents = [prompt, Part.from_bytes(data=video_content, mime_type="video/mp4")]

        # Generate content using Google Gen AI SDK with retry logic
        def make_request():
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=GenerateContentConfig(
                    max_output_tokens=4096,  # Increased for complex recipes with many ingredients/steps
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

            # Apply emoji mapping to ingredients (hybrid approach)
            parsed_json = self._apply_emoji_mapping(parsed_json)

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
        description: Optional[str] = None,
        localization: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze slideshow images with Gemini 2.0 Flash"""

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt for slideshow analysis (creator content extraction)
        prompt = "You are an expert content analyst specializing in extracting transcripts, hooks, and content classification from social media slideshows for content creators."

        if transcript:
            prompt += f"\n\nTRANSCRIPT (audio from slideshow):\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        if description:
            prompt += f"\n\nDESCRIPTION:\n{description}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, transcript) in {localization} language ONLY. Translate ALL human-readable text fields consistently. Maintain the exact JSON structure but translate all text to {localization}."

        image_count = len(slideshow_images)
        prompt += f"\n\nThis is a slideshow with {image_count} images. Analyze ALL the images together along with any transcript, caption, and description to extract creator content data. Content creators save slideshows to study hooks, scripts, and content styles."
        prompt += localization_instruction

        prompt += """

Return your response as a valid JSON object with NO additional text, explanations, or formatting.

Required JSON structure:
{
  "title": "short, descriptive title for the slideshow content",
  "description": "brief 1-2 sentence summary of what the slideshow is about",
  "transcript": "FULL transcript of any spoken audio AND all text visible on the slideshow images. This is PRIORITY #1. Include all text from each slide in order. If no audio, transcribe the on-screen text from each image.",
  "hook": "The attention-grabbing opening text or line from the first slide/audio. This captures viewer attention immediately.",
  "format": "slideshow (this is always 'slideshow' for image carousels)",
  "niche": "primary content category (see NICHE CLASSIFICATION below)",
  "niche_detail": "specific subcategory or topic detail (e.g., 'meal prep for bodybuilders', 'startup marketing tips')",
  "secondary_niches": ["array of secondary topic categories if content spans multiple niches"] or null,
  "creator": "creator username from the post or null",
  "platform": "tiktok or instagram based on content style",
  "tags": ["array of relevant hashtags from the post"] or null
}

TRANSCRIPT EXTRACTION (PRIORITY #1):
- Transcribe ALL text visible on each slideshow image, in order
- Include any spoken audio/voiceover content
- Maintain the sequence of information as presented
- For text-heavy slides, capture all readable text
- Combine visual text with any audio transcript
- Be thorough - creators need complete transcripts to study content

HOOK EXTRACTION (PRIORITY #2):
- The hook is the opening text/line from the first slide
- It's what makes viewers stop scrolling and engage
- Extract the EXACT opening words or text used
- If audio starts with a hook, use that

NICHE CLASSIFICATION:
Identify the primary topic/category. Choose ONE primary niche:
- "fitness": Gym, workout, bodybuilding, yoga, exercise
- "food": Cooking, recipes, meal prep, restaurants, eating
- "business": Entrepreneurship, startups, marketing, sales
- "finance": Investing, budgeting, crypto, real estate, money
- "tech": Software, AI, gadgets, coding, apps
- "beauty": Skincare, makeup, haircare, cosmetics
- "fashion": Outfits, styling, shopping, clothing
- "lifestyle": Daily routines, organization, productivity hacks
- "education": Study tips, learning, academic content
- "entertainment": Comedy, skits, memes, trends, pop culture
- "motivation": Mindset, self-improvement, inspirational
- "relationships": Dating, marriage, family dynamics, social
- "parenting": Kids, pregnancy, family life, motherhood
- "health": Wellness, mental health, medical, nutrition
- "travel": Destinations, travel tips, adventure, vlogs
- "gaming": Gameplay, game reviews, esports, streaming
- "music": Covers, production, dance, musical content
- "art": Drawing, design, DIY, crafts, creative
- "pets": Dogs, cats, animals, pet care
- "sports": Specific sports, athletics, training
- "other": Doesn't fit above categories

For niche_detail, provide a more specific description of the content topic.

EXAMPLE OUTPUT:
{
  "title": "5 Morning Habits for Success",
  "description": "Slideshow sharing five morning routine habits that successful entrepreneurs follow daily.",
  "transcript": "Slide 1: 5 Morning Habits of Successful People. Slide 2: 1. Wake up at 5am - The most successful CEOs start their day early. Slide 3: 2. Exercise first thing - Gets your blood flowing and mind sharp. Slide 4: 3. No phone for the first hour - Protect your mental space. Slide 5: 4. Journal your goals - Write down what you want to achieve. Slide 6: 5. Eat a healthy breakfast - Fuel your body for peak performance. Slide 7: Follow for more tips! @productivityguru",
  "hook": "5 Morning Habits of Successful People",
  "format": "slideshow",
  "niche": "lifestyle",
  "niche_detail": "morning routines and productivity habits for entrepreneurs",
  "secondary_niches": ["business", "motivation"],
  "creator": "@productivityguru",
  "platform": "instagram",
  "tags": ["#morningroutine", "#productivity", "#successhabits", "#entrepreneur"]
}

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, transcript) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""

        # Prepare content with multiple images
        contents = [prompt]

        # Add all slideshow images to the analysis (convert to JPEG if needed)
        from src.utils.image_converter import convert_image_to_jpeg

        valid_images = 0
        for i, image_content in enumerate(slideshow_images):
            if image_content and len(image_content) > 0:  # Skip empty image content
                # Additional validation for image content
                if self._is_valid_image_content(image_content):
                    try:
                        # Determine mime type based on content
                        mime_type = self._get_image_mime_type(image_content)
                        
                        # Convert HEIC/HEIF to JPEG as Gemini doesn't support them
                        if mime_type == "image/heic":
                            if PILLOW_AVAILABLE:
                                try:
                                    image_content = self._convert_heic_to_jpeg(image_content)
                                    mime_type = "image/jpeg"
                                    logger.debug(f"Converted HEIC image {i} to JPEG for Gemini compatibility")
                                except Exception as conv_error:
                                    logger.warning(f"Failed to convert HEIC image {i} to JPEG: {conv_error}, skipping")
                                    continue
                            else:
                                logger.warning(f"Skipping image {i}: HEIC format not supported and conversion unavailable")
                                continue
                            
                        contents.append(Part.from_bytes(data=image_content, mime_type=mime_type))
                        valid_images += 1
                        logger.debug(f"Added image {i} to analysis (size: {len(image_content)} bytes, type: {mime_type})")
                    except Exception as e:
                        logger.warning(f"Failed to add image {i} to analysis: {e}")
                else:
                    logger.warning(f"Skipping image {i}: Invalid image content (size: {len(image_content)} bytes)")

        if valid_images == 0:
            logger.error("No valid images found in slideshow")
            return None

        # Generate content with retry logic
        def make_request():
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=GenerateContentConfig(
                    max_output_tokens=4096,  # Increased for complex recipes with many ingredients/steps
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

            # Apply emoji mapping to ingredients (hybrid approach)
            parsed_json = self._apply_emoji_mapping(parsed_json)

            return parsed_json
        except Exception as e:
            logger.error(f"Failed to parse slideshow response: {e}")
            return None

    async def analyze_hook(
        self,
        hook_text: str,
        transcript: Optional[str] = None,
        format: Optional[str] = None,
        niche: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze a hook and explain why it works"""

        if not hook_text or not hook_text.strip():
            return None

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt for hook analysis
        prompt = f"""You are an expert content strategist analyzing viral video hooks.

Analyze this hook and explain WHY it works:

HOOK: "{hook_text}"

FORMAT: {format or "unknown"}

NICHE: {niche or "general"}

TRANSCRIPT (for context): {transcript[:1000] if transcript else "Not available"}

Respond with JSON only:

{{
  "hook_formula": "one of: curiosity_gap, controversy, transformation, list, story, question, challenge, secret, comparison, myth_busting",
  "hook_formula_name": "Human readable name",
  "explanation": "2-3 sentences explaining the psychological triggers",
  "why_it_works": ["bullet 1", "bullet 2", "bullet 3", "bullet 4"],
  "replicable_pattern": "Template with [placeholders] that can be reused"
}}

Be specific and actionable. Focus on what psychological trigger makes viewers watch."""

        # Generate content using Gemini with retry logic
        def make_request():
            return self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.3,
                    top_p=0.8,
                    response_mime_type="application/json",
                ),
            )

        try:
            response = await self._retry_with_backoff(make_request, max_retries=5, base_delay=2)

            # Parse response
            response_text = response.text.strip()
            logger.debug(f"Raw hook analysis response: {response_text[:500]}...")

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
            return parsed_json

        except Exception as e:
            logger.error(f"Failed to analyze hook: {e}")
            return None

    def _apply_emoji_mapping(self, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply predefined emoji mapping to ingredients that don't have emojis.
        Hybrid approach: Use predefined map for common ingredients, keep AI-generated for rare ones.
        """
        if not recipe_data or "structuredIngredients" not in recipe_data:
            return recipe_data

        structured_ingredients = recipe_data.get("structuredIngredients", [])
        if not structured_ingredients:
            return recipe_data

        # Process each ingredient
        for ingredient in structured_ingredients:
            if not isinstance(ingredient, dict):
                continue

            ingredient_name = ingredient.get("name", "").lower().strip()
            current_emoji = ingredient.get("emoji")

            # If no emoji from AI or emoji is null/empty, try predefined mapping
            if not current_emoji:
                mapped_emoji = INGREDIENT_EMOJI_MAP.get(ingredient_name)
                if mapped_emoji:
                    ingredient["emoji"] = mapped_emoji
                    logger.debug(f"Applied predefined emoji '{mapped_emoji}' to '{ingredient_name}'")

        return recipe_data

    def _is_valid_image_content(self, content: bytes) -> bool:
        """Validate if the content is a valid image by checking headers"""
        if not content or len(content) < 10:
            return False
            
        # Check for common image format headers
        # JPEG
        if content.startswith(b'\xff\xd8\xff'):
            return True
        # PNG
        if content.startswith(b'\x89PNG\r\n\x1a\n'):
            return True
        # WebP
        if len(content) > 12 and content[8:12] == b'WEBP':
            return True
        # GIF
        if content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
            return True
        # BMP
        if content.startswith(b'BM'):
            return True
        # HEIC/HEIF (Apple's format used by TikTok)
        if len(content) > 12:
            # HEIC files have 'ftyp' at offset 4-8 and 'heic' or 'mif1' at offset 8-12
            if content[4:8] == b'ftyp' and (content[8:12] == b'heic' or content[8:12] == b'mif1'):
                return True
            # Alternative HEIC signature
            if content[4:8] == b'ftyp' and content[8:12] == b'heix':
                return True
            # Additional HEIC variants
            if content[4:8] == b'ftyp' and content[8:12] == b'msf1':
                return True
            # Check for any MP4-based image format (which HEIC is based on)
            if content[4:8] == b'ftyp':
                return True
        
        # AVIF format (another modern image format)
        if len(content) > 12 and content[4:8] == b'ftyp' and content[8:12] == b'avif':
            return True
            
        return False

    def _get_image_mime_type(self, content: bytes) -> str:
        """Determine the MIME type of an image based on its content"""
        if content.startswith(b'\xff\xd8\xff'):
            return "image/jpeg"
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):
            return "image/png"
        elif len(content) > 12 and content[8:12] == b'WEBP':
            return "image/webp"
        elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
            return "image/gif"
        elif content.startswith(b'BM'):
            return "image/bmp"
        elif len(content) > 12 and content[4:8] == b'ftyp':
            # Handle all MP4-based image formats (HEIC, AVIF, etc.)
            if content[8:12] == b'avif':
                return "image/avif"
            else:
                # Default to HEIC for other ftyp-based formats
                return "image/heic"
        else:
            # Default to JPEG if we can't determine the type
            return "image/jpeg"

    def _convert_heic_to_jpeg(self, heic_content: bytes) -> bytes:
        """Convert HEIC image content to JPEG format"""
        if not PILLOW_AVAILABLE:
            raise RuntimeError("Pillow and pillow-heif are required for HEIC conversion")
        
        try:
            # Open HEIC image from bytes
            heic_image = Image.open(io.BytesIO(heic_content))
            
            # Convert to RGB if necessary (HEIC can be in different color modes)
            if heic_image.mode != 'RGB':
                heic_image = heic_image.convert('RGB')
            
            # Save as JPEG to bytes buffer
            jpeg_buffer = io.BytesIO()
            heic_image.save(jpeg_buffer, format='JPEG', quality=85, optimize=True)
            jpeg_content = jpeg_buffer.getvalue()
            
            logger.debug(f"Converted HEIC image ({len(heic_content)} bytes) to JPEG ({len(jpeg_content)} bytes)")
            return jpeg_content
            
        except Exception as e:
            logger.error(f"Failed to convert HEIC to JPEG: {e}")
            raise
