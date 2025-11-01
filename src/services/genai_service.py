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

# Emoji mapping for common cooking ingredients (hybrid approach)
# AI will use this mapping first, fall back to generating emoji if ingredient not found
INGREDIENT_EMOJI_MAP = {
    # Proteins
    "chicken": "🍗", "chicken breast": "🍗", "chicken thighs": "🍗",
    "beef": "🥩", "steak": "🥩", "ground beef": "🥩",
    "pork": "🥓", "bacon": "🥓", "ham": "🍖",
    "fish": "🐟", "salmon": "🐟", "tuna": "🐟", "cod": "🐟",
    "shrimp": "🍤", "prawns": "🍤",
    "eggs": "🥚", "egg": "🥚",
    "tofu": "🥢",

    # Vegetables
    "broccoli": "🥦",
    "carrot": "🥕", "carrots": "🥕",
    "tomato": "🍅", "tomatoes": "🍅",
    "onion": "🧅", "onions": "🧅",
    "garlic": "🧄", "garlic cloves": "🧄",
    "pepper": "🫑", "bell pepper": "🫑", "peppers": "🫑",
    "chili": "🌶️", "chili pepper": "🌶️",
    "potato": "🥔", "potatoes": "🥔",
    "sweet potato": "🍠",
    "corn": "🌽",
    "eggplant": "🍆", "aubergine": "🍆",
    "mushroom": "🍄", "mushrooms": "🍄",
    "lettuce": "🥬", "salad": "🥗",
    "cucumber": "🥒",
    "avocado": "🥑",
    "spinach": "🥬",
    "kale": "🥬",

    # Fruits
    "lemon": "🍋", "lemons": "🍋",
    "lime": "🍋", "limes": "🍋",
    "apple": "🍎", "apples": "🍎",
    "banana": "🍌", "bananas": "🍌",
    "strawberry": "🍓", "strawberries": "🍓",
    "orange": "🍊", "oranges": "🍊",
    "grape": "🍇", "grapes": "🍇",
    "watermelon": "🍉",
    "pineapple": "🍍",
    "mango": "🥭",
    "peach": "🍑", "peaches": "🍑",
    "cherry": "🍒", "cherries": "🍒",

    # Grains & Pasta
    "pasta": "🍝", "spaghetti": "🍝", "noodles": "🍜",
    "rice": "🍚",
    "bread": "🍞", "baguette": "🥖",
    "flour": "🌾",
    "oats": "🌾", "oatmeal": "🌾",

    # Dairy
    "milk": "🥛",
    "cheese": "🧀", "cheddar": "🧀", "parmesan": "🧀",
    "butter": "🧈",
    "cream": "🥛", "heavy cream": "🥛",
    "yogurt": "🥛", "yoghurt": "🥛",

    # Condiments & Oils
    "olive oil": "🫒", "oil": "🫒",
    "salt": "🧂",
    "pepper": "🫑",
    "soy sauce": "🥫",
    "honey": "🍯",
    "sugar": "🧂",

    # Herbs & Spices
    "basil": "🌿",
    "parsley": "🌿",
    "cilantro": "🌿", "coriander": "🌿",
    "rosemary": "🌿",
    "thyme": "🌿",
    "oregano": "🌿",
    "mint": "🌿",

    # Nuts & Seeds
    "peanut": "🥜", "peanuts": "🥜",
    "almond": "🌰", "almonds": "🌰",
    "walnut": "🌰", "walnuts": "🌰",

    # Beverages
    "water": "💧",
    "wine": "🍷",
    "beer": "🍺",

    # Other
    "coconut": "🥥",
    "beans": "🫘",
    "chocolate": "🍫",
    "vanilla": "🌿",
}


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
        """Analyze video/post with Gemini 2.0 Flash for relationship content"""

        # Apply rate limiting
        await self._rate_limit()

        # Build prompt
        prompt = "You are an expert culinary AI specializing in extracting structured recipe data from cooking videos and social media posts."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        if description:
            prompt += f"\n\nDESCRIPTION:\n{description}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, ingredient names, instruction text, location) in {localization} language ONLY. Translate ALL human-readable text fields consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        prompt += "\n\nAnalyze this cooking video/post and extract structured recipe data. Use ALL available information (video content, transcript, caption, and description) to create a comprehensive recipe extraction. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction
        prompt += """

Required JSON structure:
{
  "title": "short, descriptive recipe name (e.g., 'Broccoli Pasta', 'Creamy Garlic Chicken')",
  "description": "brief 1-2 sentence summary of the dish and its appeal",
  "image": "main image URL from the post/video or null",
  "location": "cuisine origin or region mentioned (e.g., 'Italy', 'Thailand', 'Mediterranean') or null",
  "prepTimeMinutes": "estimated preparation time in minutes (integer) or null",
  "cookTimeMinutes": "estimated cooking time in minutes (integer) or null",
  "baseServings": "number of servings this recipe makes (integer) or null",
  "structuredIngredients": [
    {
      "name": "ingredient name (e.g., 'broccoli', 'chicken breast')",
      "amount": "numeric quantity as float (e.g., 2.0, 500, 0.5) or null for qualitative amounts",
      "unit": "measurement unit (e.g., 'cups', 'g', 'tbsp', 'heads', 'cloves') or null",
      "preparation": "how to prepare (e.g., 'chopped', 'sliced', 'minced', 'diced') or null",
      "emoji": "single emoji representing the ingredient (e.g., '🥦', '🍝', '🧄') or null",
      "notes": "substitution notes or alternatives (e.g., 'or canned tomatoes') or null"
    }
  ],
  "instructions": [
    {
      "stepNumber": "sequential step number starting from 1",
      "text": "clear, complete cooking instruction for this step",
      "durationMinutes": "time required for this step in minutes (integer) or null",
      "highlightedIngredients": ["array of ingredient names mentioned in this step"]
    }
  ],
  "tags": ["array of relevant hashtags or cooking tags from the post"] or null,
  "creator": "creator username or null"
}

EXTRACTION GUIDELINES:
- Focus on extracting recipe cooking instructions and ingredients
- Combine information from video visuals, spoken audio/transcript, caption, and description
- For Instagram: Use both the caption (primary text) and description (additional metadata)
- For TikTok: Use both the transcript (spoken content) and description (post text)

INGREDIENTS EXTRACTION:
- Extract ALL ingredients mentioned in video/audio/text
- Parse quantities (amounts + units) from spoken or written content
- Identify preparation methods (chopped, diced, minced, etc.)
- Add appropriate food emojis for common ingredients (or null if uncertain)
- Note substitutions or alternatives mentioned by creator
- For qualitative amounts (e.g., "a drizzle", "a pinch", "to taste"), set amount to null and describe in unit field
- Keep ingredient names simple and lowercase (e.g., "garlic" not "Garlic Cloves")

INSTRUCTIONS EXTRACTION:
- Break cooking process into numbered sequential steps
- Extract timing information for each step when mentioned (e.g., "cook for 10 minutes")
- Track which ingredients are used in each step for highlighting
- Keep step text clear and actionable
- Maintain chronological order from video/audio content
- If no timing mentioned for a step, set durationMinutes to null

METADATA EXTRACTION:
- Estimate prep and cook times based on video content and creator's statements
- Count servings mentioned by creator or estimate from ingredient quantities
- Identify cuisine type or geographic origin for location field
- Extract relevant hashtags and tags for discoverability

EXAMPLE OUTPUT:
{
  "title": "Broccoli Pasta",
  "description": "A quick and healthy 15-minute pasta dish with garlic and broccoli.",
  "image": "https://example.com/image.jpg",
  "location": "Italy",
  "prepTimeMinutes": 5,
  "cookTimeMinutes": 10,
  "baseServings": 4,
  "structuredIngredients": [
    {
      "name": "broccoli",
      "amount": 2.0,
      "unit": "heads",
      "preparation": null,
      "emoji": "🥦",
      "notes": null
    },
    {
      "name": "pasta",
      "amount": 500,
      "unit": "g",
      "preparation": null,
      "emoji": "🍝",
      "notes": "any shape works"
    },
    {
      "name": "garlic",
      "amount": 4,
      "unit": "cloves",
      "preparation": "sliced",
      "emoji": "🧄",
      "notes": null
    },
    {
      "name": "olive oil",
      "amount": null,
      "unit": "drizzle",
      "preparation": null,
      "emoji": "🫒",
      "notes": null
    }
  ],
  "instructions": [
    {
      "stepNumber": 1,
      "text": "Bring a large pot of salted water to boil. Add pasta and cook according to package directions.",
      "durationMinutes": 10,
      "highlightedIngredients": ["pasta", "water"]
    },
    {
      "stepNumber": 2,
      "text": "Meanwhile, heat olive oil in a large pan over medium heat. Add sliced garlic and sauté until fragrant.",
      "durationMinutes": 2,
      "highlightedIngredients": ["olive oil", "garlic"]
    },
    {
      "stepNumber": 3,
      "text": "Add broccoli florets to the pan and cook until tender. Season with salt and pepper.",
      "durationMinutes": 7,
      "highlightedIngredients": ["broccoli"]
    }
  ],
  "tags": ["#pasta", "#quickdinner", "#healthyrecipes"],
  "creator": "@cammienoodle"
}

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, ingredient names, instruction text, location) MUST be in the SAME target language consistently throughout the entire response.

IMPORTANT: Your response must be ONLY the JSON object, with no markdown formatting, no code blocks, no explanations before or after."""

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

        # Build prompt for slideshow analysis
        prompt = "You are an expert culinary AI specializing in extracting structured recipe data from cooking videos and social media posts."

        if transcript:
            prompt += f"\n\nTRANSCRIPT:\n{transcript}"

        if caption:
            prompt += f"\n\nCAPTION:\n{caption}"

        if description:
            prompt += f"\n\nDESCRIPTION:\n{description}"

        # Add localization instructions if specified
        localization_instruction = ""
        if localization:
            localization_instruction = f"\n\nIMPORTANT: Provide ALL text content (title, description, ingredient names, instruction text, location) in {localization} language ONLY. Translate ALL human-readable text fields consistently in the specified language. Maintain the exact JSON structure but translate all text to {localization}."

        image_count = len(slideshow_images)
        prompt += f"\n\nThis is a slideshow with {image_count} images. Analyze ALL the images together along with transcript, caption, and description to extract structured recipe data. Use ALL available information to create a comprehensive recipe extraction. Use 'slideshow_image_1' as placeholder for the main image URL. Return your response as a valid JSON object with NO additional text, explanations, or formatting."
        prompt += localization_instruction

        prompt += """

Required JSON structure:
{
  "title": "short, descriptive recipe name (e.g., 'Broccoli Pasta', 'Creamy Garlic Chicken')",
  "description": "brief 1-2 sentence summary of the dish and its appeal",
  "image": "use 'slideshow_image_1' as placeholder",
  "location": "cuisine origin or region mentioned (e.g., 'Italy', 'Thailand', 'Mediterranean') or null",
  "prepTimeMinutes": "estimated preparation time in minutes (integer) or null",
  "cookTimeMinutes": "estimated cooking time in minutes (integer) or null",
  "baseServings": "number of servings this recipe makes (integer) or null",
  "structuredIngredients": [
    {
      "name": "ingredient name (e.g., 'broccoli', 'chicken breast')",
      "amount": "numeric quantity as float (e.g., 2.0, 500, 0.5) or null for qualitative amounts",
      "unit": "measurement unit (e.g., 'cups', 'g', 'tbsp', 'heads', 'cloves') or null",
      "preparation": "how to prepare (e.g., 'chopped', 'sliced', 'minced', 'diced') or null",
      "emoji": "single emoji representing the ingredient (e.g., '🥦', '🍝', '🧄') or null",
      "notes": "substitution notes or alternatives (e.g., 'or canned tomatoes') or null"
    }
  ],
  "instructions": [
    {
      "stepNumber": "sequential step number starting from 1",
      "text": "clear, complete cooking instruction for this step",
      "durationMinutes": "time required for this step in minutes (integer) or null",
      "highlightedIngredients": ["array of ingredient names mentioned in this step"]
    }
  ],
  "tags": ["array of relevant hashtags or cooking tags from the post"] or null,
  "creator": "creator username or null"
}

EXTRACTION GUIDELINES:
- Focus on extracting recipe cooking instructions and ingredients
- Combine information from all slideshow images, spoken audio/transcript, caption, and description
- For Instagram: Use both the caption (primary text) and description (additional metadata)
- For TikTok: Use both the transcript (spoken content) and description (post text)

INGREDIENTS EXTRACTION:
- Extract ALL ingredients mentioned in images/audio/text
- Parse quantities (amounts + units) from visual or written content
- Identify preparation methods (chopped, diced, minced, etc.)
- Add appropriate food emojis for common ingredients (or null if uncertain)
- Note substitutions or alternatives mentioned by creator
- For qualitative amounts (e.g., "a drizzle", "a pinch", "to taste"), set amount to null and describe in unit field
- Keep ingredient names simple and lowercase (e.g., "garlic" not "Garlic Cloves")

INSTRUCTIONS EXTRACTION:
- Break cooking process into numbered sequential steps
- Extract timing information for each step when mentioned (e.g., "cook for 10 minutes")
- Track which ingredients are used in each step for highlighting
- Keep step text clear and actionable
- Maintain chronological order across all slideshow images
- If no timing mentioned for a step, set durationMinutes to null

METADATA EXTRACTION:
- Estimate prep and cook times based on slideshow content and creator's statements
- Count servings mentioned by creator or estimate from ingredient quantities
- Identify cuisine type or geographic origin for location field
- Extract relevant hashtags and tags for discoverability

EXAMPLE OUTPUT:
{
  "title": "Broccoli Pasta",
  "description": "A quick and healthy 15-minute pasta dish with garlic and broccoli.",
  "image": "slideshow_image_1",
  "location": "Italy",
  "prepTimeMinutes": 5,
  "cookTimeMinutes": 10,
  "baseServings": 4,
  "structuredIngredients": [
    {
      "name": "broccoli",
      "amount": 2.0,
      "unit": "heads",
      "preparation": null,
      "emoji": "🥦",
      "notes": null
    },
    {
      "name": "pasta",
      "amount": 500,
      "unit": "g",
      "preparation": null,
      "emoji": "🍝",
      "notes": "any shape works"
    },
    {
      "name": "garlic",
      "amount": 4,
      "unit": "cloves",
      "preparation": "sliced",
      "emoji": "🧄",
      "notes": null
    },
    {
      "name": "olive oil",
      "amount": null,
      "unit": "drizzle",
      "preparation": null,
      "emoji": "🫒",
      "notes": null
    }
  ],
  "instructions": [
    {
      "stepNumber": 1,
      "text": "Bring a large pot of salted water to boil. Add pasta and cook according to package directions.",
      "durationMinutes": 10,
      "highlightedIngredients": ["pasta", "water"]
    },
    {
      "stepNumber": 2,
      "text": "Meanwhile, heat olive oil in a large pan over medium heat. Add sliced garlic and sauté until fragrant.",
      "durationMinutes": 2,
      "highlightedIngredients": ["olive oil", "garlic"]
    },
    {
      "stepNumber": 3,
      "text": "Add broccoli florets to the pan and cook until tender. Season with salt and pepper.",
      "durationMinutes": 7,
      "highlightedIngredients": ["broccoli"]
    }
  ],
  "tags": ["#pasta", "#quickdinner", "#healthyrecipes"],
  "creator": "@cammienoodle"
}

CRITICAL CONSISTENCY RULE: If localization is specified, ALL text fields (title, description, ingredient names, instruction text, location) MUST be in the SAME target language consistently throughout the entire response.

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
