"""
OpenAI service for transcript templatization
"""

from openai import OpenAI
import os
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for OpenAI API interactions"""

    def __init__(self):
        """Initialize OpenAI client with API key from environment"""
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API")
        if not api_key:
            raise ValueError("OPENAI_API_KEY or OPENAI_API environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"

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

