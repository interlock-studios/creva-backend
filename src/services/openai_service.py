"""
OpenAI service for transcript templatization and script generation
"""

from openai import OpenAI
import os
import logging
import asyncio
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for OpenAI API interactions"""

    def __init__(self):
        """Initialize OpenAI client with API key from environment"""
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API")
        if not api_key:
            raise ValueError("OPENAI_API_KEY or OPENAI_API environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"

    async def templatize_transcript(self, transcript: str) -> Optional[str]:
        """
        Convert a full transcript into a fill-in-the-blank template.

        Args:
            transcript: Full transcript text from the video

        Returns:
            Templatized version with [placeholder] format, or None if generation failed
        """
        prompt = f"""This is a transcript from a viral video, please make it into a script template that could be used for any niche. Keep the overall format and structure of the video and make it a fill in the blank version.

Use [placeholder] format for fill-in-the-blank sections.

Common placeholders: [topic], [product], [action], [result], [number], [timeframe], [location], [name], [time]

Guidelines:
1. Preserve the original structure and flow
2. Replace specific nouns/verbs/adjectives with appropriate placeholders
3. Keep the hook structure intact
4. Make it reusable across different niches
5. Use clear, descriptive placeholder names

TRANSCRIPT:

{transcript}

Respond with ONLY the templatized script, no additional text or explanation."""

        try:
            # Run synchronous OpenAI call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,  # Lower temperature for more consistent templatization
                    max_tokens=2000,
                ),
            )

            template = response.choices[0].message.content.strip()
            logger.info(f"Successfully templatized transcript (output length: {len(template)})")
            return template

        except Exception as e:
            logger.error(f"Failed to templatize transcript with OpenAI: {e}")
            return None

    async def generate_script(
        self,
        template: str,
        topic: str,
        creator_role: str,
        main_message: str,
        niche: Optional[str] = None,
        style: str = "conversational",
        length: str = "short",
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a script from a template using creator role and main message.

        Args:
            template: Madlib template with [placeholders]
            topic: User's topic/subject
            creator_role: Creator's role/identity (e.g., 'food chef', 'school teacher')
            main_message: Single text describing the creator's main message/goal
            niche: Content niche (optional, AI will infer from creator_role + topic)
            style: Script style: conversational, professional, humorous
            length: Target length: short (30s), medium (60s), long (90s+)

        Returns:
            Dict with script parts, full_script, variations, and estimated_duration
        """
        # Length guide mapping
        length_guide = {
            "short": "30 seconds, ~75 words",
            "medium": "60 seconds, ~150 words",
            "long": "90+ seconds, ~225 words",
        }
        target_length = length_guide.get(length, length_guide["short"])

        # Niche inference section
        if niche:
            niche_section = f"NICHE: {niche}"
        else:
            niche_section = f"NICHE: Infer from creator_role ('{creator_role}') and topic ('{topic}'). Stay strictly within this inferred niche."

        # Build prompt for script generation
        prompt = f"""You are a viral content writer creating short-form video scripts.

Create a script using this template and the creator's context:

TEMPLATE: "{template}"

TOPIC: "{topic}"

CREATOR ROLE: {creator_role}

MAIN MESSAGE: "{main_message}"

{niche_section}

STYLE: {style}

TARGET LENGTH: {target_length}

YOUR TASK:
1. INFER THE NICHE from the creator_role and topic. For example:
   - "school teacher" + "classroom management" = education niche
   - "food chef" + "meal prep" = food/cooking niche
   - "fitness coach" + "workout routines" = fitness niche
   - Stay STRICTLY within this inferred niche. Do NOT discuss unrelated topics.

2. MAP THE MAIN MESSAGE to template placeholders:
   - Parse the template for [PLACEHOLDER] patterns (e.g., [MISTAKE], [GOAL], [SECRET], [SOLUTION])
   - Use the main_message to intelligently fill these user-intent placeholders
   - For generic placeholders like [number], [timeframe], [location], infer appropriate values from context
   
   Example:
   - Template: "Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION]"
   - Main message: "Stop trying to control every student behavior. Focus on building relationships."
   - Map: [MISTAKE] → "trying to control every student behavior"
          [GOAL] → "effective classroom management" (inferred from topic)
          [SOLUTION] → "building relationships and setting clear expectations"

3. ADAPT VOICE AND TERMINOLOGY to the creator_role:
   - Use terminology, examples, and language appropriate to their profession/identity
   - "school teacher" → classroom terms, student examples, education context
   - "food chef" → cooking terminology, kitchen examples, culinary context
   - "fitness coach" → workout terms, training examples, health context
   - Make it sound like THIS specific person is speaking from their expertise

4. MAINTAIN NICHE CONSISTENCY:
   - All examples, terminology, and content must align with the inferred niche
   - If creator_role is "school teacher", do NOT mention marketing, business, or unrelated topics
   - Keep everything contextually relevant to who the creator is

5. GENERATE THE SCRIPT:
   - Use the template structure EXACTLY, filling all placeholders
   - Hook MUST grab attention in first 3 seconds and reflect creator expertise
   - Body must match target length and include actionable, specific information
   - Call to action must be relevant to the creator's role and audience

Respond with JSON only:

{{
  "script": {{
    "hook": "Opening hook filled from template (first 3 seconds, grabs attention)",
    "body": "Main content filled from template (match target length, creator-specific terminology)",
    "call_to_action": "Ending CTA (relevant to creator role)"
  }},
  "full_script": "Complete script as one readable string with all placeholders filled",
  "variations": [
    {{"hook": "...", "body": "...", "call_to_action": "..."}}
  ],
  "estimated_duration": "X seconds",
  "inferred_niche": "The niche you inferred from creator_role + topic"
}}

CRITICAL RULES:
1. Fill ALL [placeholders] using main_message and context - no placeholders left unfilled
2. Keep sentences short - this is for SPEAKING not reading
3. Match the style (conversational = casual, first person; professional = authoritative)
4. Sound authentic to the creator's role - use their terminology and perspective
5. Stay within the inferred niche - no topic drift
6. Provide 1-2 variations with different angles on same topic"""

        try:
            # Run synchronous OpenAI call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,  # Higher temperature for creative script generation
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                ),
            )

            response_text = response.choices[0].message.content.strip()
            logger.debug(f"Raw script generation response: {response_text[:500]}...")

            parsed_json = json.loads(response_text)
            logger.info(f"Successfully generated script with OpenAI")
            return parsed_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI script response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate script with OpenAI: {e}")
            return None

