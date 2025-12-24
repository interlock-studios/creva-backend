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

    @staticmethod
    def estimate_seconds(word_count: int, reading_speed: str = "normal") -> int:
        """Calculate speaking time based on word count and reading speed."""
        wpm = 175 if reading_speed == "fast" else 150  # words per minute
        return max(1, round(word_count / wpm * 60))

    @staticmethod
    def count_words(text: str) -> int:
        """Count words in a text string."""
        return len(text.split())

    async def generate_scripts_from_scratch(
        self,
        topic: str,
        hook_style: str,
        cta_type: str,
        tone: str,
        video_format: str,
        length_seconds: int,
        reading_speed: str,
        audience: Optional[str] = None,
        proof: Optional[str] = None,
        cta_keyword: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate 3 meaningfully different scripts from scratch (no template required).

        Args:
            topic: Main topic/subject of the script
            hook_style: Style of opening hook (question, hot_take, storytime, etc.)
            cta_type: Type of call-to-action
            tone: Voice/tone of the script
            video_format: Video production format
            length_seconds: Target length in seconds (30, 45, or 60)
            reading_speed: Reading pace (normal or fast)
            audience: Target audience (optional)
            proof: Personal proof or credentials (optional)
            cta_keyword: Keyword for comment CTA (optional)

        Returns:
            Dict with 3 script options, each containing beats and metadata
        """
        # Calculate word targets based on length and speed
        wpm = 175 if reading_speed == "fast" else 150
        target_words = round(length_seconds * wpm / 60)
        word_tolerance = round(target_words * 0.1)  # ±10% tolerance

        # Build audience section
        audience_section = f"TARGET AUDIENCE: {audience}" if audience else "TARGET AUDIENCE: General viewers interested in this topic"

        # Build proof section - critical for avoiding fake claims
        if proof:
            proof_section = f"""CREATOR'S PROOF/CREDENTIALS: "{proof}"
Use this proof naturally in the scripts. Reference it authentically."""
        else:
            proof_section = """CREATOR'S PROOF/CREDENTIALS: None provided.
IMPORTANT: Do NOT invent fake statistics, personal results, or credentials.
Instead, use general credibility language like:
- "I've seen this work for..."
- "Creators who do this tend to..."
- "From what I've observed..."
- "The pattern I've noticed is..."
NEVER claim specific numbers or personal results that weren't provided."""

        # Build CTA section
        if cta_type == "comment_keyword" and cta_keyword:
            cta_instruction = f"CTA TYPE: Comment Keyword - Ask viewers to comment '{cta_keyword}' below"
        else:
            cta_map = {
                "follow_for_more": "Ask viewers to follow for more tips like this",
                "save_this": "Ask viewers to save this for later",
                "try_this_today": "Encourage viewers to try this on their next video",
                "download_app": "Mention link in bio to download",
                "dm_me": "Invite viewers to DM for more details",
            }
            cta_instruction = f"CTA TYPE: {cta_map.get(cta_type, 'Natural ending that encourages engagement')}"

        # Build hook style description
        hook_descriptions = {
            "question": "Open with an intriguing question that makes viewers curious",
            "hot_take": "Start with a bold, potentially controversial statement",
            "storytime": "Begin with a personal anecdote or story opener",
            "ranking": "Use a 'Top X...' or 'The #1 reason...' format",
            "tutorial": "Start with 'Here's how to...' instructional opener",
            "myth_bust": "Challenge a common belief with 'Everyone thinks X but actually...'",
        }
        hook_instruction = hook_descriptions.get(hook_style, "Create an attention-grabbing opening")

        # Build tone description
        tone_descriptions = {
            "casual": "Friendly, conversational, relatable - like talking to a friend",
            "confident": "Authoritative, assertive, bold - speak with conviction",
            "funny": "Humorous, lighthearted, playful - include wit",
            "calm": "Relaxed, soothing, measured - gentle delivery",
            "direct": "No fluff, straight to the point - efficient",
            "educational": "Informative, teacher-like - clear explanations",
        }
        tone_instruction = tone_descriptions.get(tone, "Natural, conversational tone")

        prompt = f"""You are a short-form video script writer for TikTok and Instagram Reels.

Generate 3 MEANINGFULLY DIFFERENT scripts based on these inputs:

TOPIC: "{topic}"
{audience_section}
HOOK STYLE: {hook_style} - {hook_instruction}
TONE: {tone} - {tone_instruction}
FORMAT: {video_format}
TARGET LENGTH: {length_seconds} seconds (~{target_words} words, tolerance ±{word_tolerance} words)
READING SPEED: {reading_speed} ({wpm} words per minute)

{proof_section}

{cta_instruction}

BEAT STRUCTURE (4 beats):
- HOOK (3-5 seconds): Pattern interrupt, grab attention immediately using the specified hook style
- CONTEXT (10-15 seconds): Set up the problem or situation
- VALUE (20-35 seconds): Deliver the main content, tips, or insight
- CTA (5-10 seconds): Clear call-to-action matching the specified CTA type

CRITICAL RULES:
1. Write scripts meant to be SPOKEN on camera, not read
2. Use short, punchy sentences (max 15 words per sentence)
3. NO fluff, filler words, or corporate language
4. Sound like a real person talking to a friend
5. NEVER invent fake statistics or personal results if no proof was provided
6. Each of the 3 scripts must feel DIFFERENT - vary the hook angle, structure, examples, and phrasing
7. Do NOT just swap synonyms between scripts - create genuinely different approaches

Respond with JSON only:

{{
  "options": [
    {{
      "option_id": "opt_1",
      "beats": {{
        "hook": "Opening hook (3-5 seconds)",
        "context": "Problem setup (10-15 seconds)",
        "value": "Main content (20-35 seconds)",
        "cta": "Call-to-action (5-10 seconds)"
      }},
      "tags": {{
        "hook_style": "{hook_style}",
        "tone": "{tone}",
        "format": "{video_format}"
      }}
    }},
    {{
      "option_id": "opt_2",
      "beats": {{ ... }},
      "tags": {{ ... }}
    }},
    {{
      "option_id": "opt_3",
      "beats": {{ ... }},
      "tags": {{ ... }}
    }}
  ]
}}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8,  # Higher temperature for variety
                    max_tokens=3000,
                    response_format={"type": "json_object"},
                ),
            )

            response_text = response.choices[0].message.content.strip()
            logger.debug(f"Raw from-scratch response: {response_text[:500]}...")

            parsed = json.loads(response_text)
            
            # Post-process to add full_text, word_count, estimated_seconds
            for option in parsed.get("options", []):
                beats = option.get("beats", {})
                full_text = "\n\n".join([
                    beats.get("hook", ""),
                    beats.get("context", ""),
                    beats.get("value", ""),
                    beats.get("cta", "")
                ])
                option["full_text"] = full_text
                option["word_count"] = self.count_words(full_text)
                option["estimated_seconds"] = self.estimate_seconds(
                    option["word_count"], reading_speed
                )

            logger.info("Successfully generated 3 scripts from scratch")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse from-scratch response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate scripts from scratch: {e}")
            return None

    async def refine_beat(
        self,
        beat_type: str,
        current_text: str,
        action: str,
        context: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Refine a single beat with a specific action.

        Args:
            beat_type: Which beat (hook, context, value, cta)
            current_text: Current text of the beat
            action: Refinement action to apply
            context: Optional context for consistency

        Returns:
            Dict with refined_text, estimated_seconds, word_count, action_applied
        """
        # Extract context if provided
        topic = context.get("topic", "the topic") if context else "the topic"
        audience = context.get("audience", "") if context else ""
        tone = context.get("tone", "conversational") if context else "conversational"

        # Action descriptions
        action_descriptions = {
            # Hook actions
            "punchier": "Make it more impactful, bold, and attention-grabbing. Increase urgency.",
            "more_curiosity": "Add mystery, create an open loop, make viewer desperate to keep watching.",
            "shorter": "Reduce word count while keeping the essence. Be more concise.",
            "new_hook": "Generate a completely different hook angle. New approach entirely.",
            # Context actions
            "clearer": "Simplify language, remove jargon, make easier to understand immediately.",
            "add_one_line": "Add one more sentence of context or setup to enhance understanding.",
            # Value actions
            "add_example": "Include a specific, relatable example or mini case study.",
            "make_simpler": "Break down complex ideas into simpler, bite-sized terms.",
            "cut_fluff": "Remove filler words, unnecessary phrases, and redundant content.",
            "add_pattern_interrupt": "Add something unexpected mid-way to re-engage wandering viewers.",
            # CTA actions
            "swap_cta": "Generate a different style of call-to-action entirely.",
            "add_keyword_prompt": "Add a 'Comment [keyword] below' style prompt.",
            "less_salesy": "Make the CTA feel more natural, casual, and less pushy.",
        }

        action_instruction = action_descriptions.get(action, "Improve this beat")

        prompt = f"""You are refining a single beat of a short-form video script.

BEAT TYPE: {beat_type}
CURRENT TEXT: "{current_text}"
ACTION TO APPLY: {action} - {action_instruction}

CONTEXT:
- Topic: {topic}
- Audience: {audience if audience else "General viewers"}
- Tone: {tone}

RULES:
1. Keep the same general meaning unless action is "new_hook" or "swap_cta"
2. Maintain the specified tone
3. Output should be spoken language, not written - short punchy sentences
4. No fluff or filler words

Return ONLY the refined text as a JSON object:

{{
  "refined_text": "The refined beat text here"
}}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                ),
            )

            response_text = response.choices[0].message.content.strip()
            parsed = json.loads(response_text)
            
            refined_text = parsed.get("refined_text", "")
            word_count = self.count_words(refined_text)
            
            result = {
                "refined_text": refined_text,
                "word_count": word_count,
                "estimated_seconds": self.estimate_seconds(word_count),
                "action_applied": action,
            }

            logger.info(f"Successfully refined {beat_type} beat with action: {action}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse refine beat response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to refine beat: {e}")
            return None
