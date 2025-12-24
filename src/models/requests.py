"""
Request models for API endpoints
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict
from enum import Enum
import re


# =============================================================================
# Enums for Script Generation From Scratch
# =============================================================================

class HookStyle(str, Enum):
    """Style of the opening hook"""
    QUESTION = "question"
    HOT_TAKE = "hot_take"
    STORYTIME = "storytime"
    RANKING = "ranking"
    TUTORIAL = "tutorial"
    MYTH_BUST = "myth_bust"


class CTAType(str, Enum):
    """Type of call-to-action"""
    FOLLOW_FOR_MORE = "follow_for_more"
    SAVE_THIS = "save_this"
    COMMENT_KEYWORD = "comment_keyword"
    TRY_THIS_TODAY = "try_this_today"
    DOWNLOAD_APP = "download_app"
    DM_ME = "dm_me"


class Tone(str, Enum):
    """Voice/tone of the script"""
    CASUAL = "casual"
    CONFIDENT = "confident"
    FUNNY = "funny"
    CALM = "calm"
    DIRECT = "direct"
    EDUCATIONAL = "educational"


class VideoFormat(str, Enum):
    """Video production format"""
    TALKING_TO_CAMERA = "talking_to_camera"
    VOICEOVER = "voiceover"
    FACELESS_TEXT = "faceless_text"


class ReadingSpeed(str, Enum):
    """Reading pace for time estimation"""
    NORMAL = "normal"  # 150 wpm
    FAST = "fast"      # 175 wpm


class BeatType(str, Enum):
    """Type of beat in a script"""
    HOOK = "hook"
    CONTEXT = "context"
    VALUE = "value"
    CTA = "cta"


class RefineAction(str, Enum):
    """Actions available for beat refinement"""
    # Hook actions
    PUNCHIER = "punchier"
    MORE_CURIOSITY = "more_curiosity"
    SHORTER = "shorter"
    NEW_HOOK = "new_hook"
    # Context actions
    CLEARER = "clearer"
    ADD_ONE_LINE = "add_one_line"
    # Value actions
    ADD_EXAMPLE = "add_example"
    MAKE_SIMPLER = "make_simpler"
    CUT_FLUFF = "cut_fluff"
    ADD_PATTERN_INTERRUPT = "add_pattern_interrupt"
    # CTA actions
    SWAP_CTA = "swap_cta"
    ADD_KEYWORD_PROMPT = "add_keyword_prompt"
    LESS_SALESY = "less_salesy"


class ProcessRequest(BaseModel):
    """Request model for video processing"""

    url: str = Field(..., description="TikTok or Instagram video URL")
    localization: Optional[str] = Field(
        None, description="Optional language code or name (e.g., 'es', 'Spanish', 'zh', 'Chinese', 'Tamil')"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validate URL format"""
        if not v or not isinstance(v, str):
            raise ValueError("URL must be a non-empty string")

        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        # Basic URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(v):
            raise ValueError("Invalid URL format")

        return v

    @field_validator("localization")
    @classmethod
    def validate_localization(cls, v):
        """Validate localization - accepts language codes or full language names"""
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        # Accept any reasonable language identifier (2-20 characters)
        # This allows both codes like "es", "zh" and full names like "Spanish", "Chinese"
        if len(v) < 2 or len(v) > 20:
            raise ValueError("Localization must be 2-20 characters")

        # Return original case for better AI understanding
        return v


class CacheInvalidationRequest(BaseModel):
    """Request model for cache invalidation"""

    url: str = Field(..., description="URL to invalidate from cache")
    localization: Optional[str] = Field(None, description="Optional localization to invalidate")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validate URL format"""
        if not v or not isinstance(v, str):
            raise ValueError("URL must be a non-empty string")
        return v.strip()


class GenerateScriptRequest(BaseModel):
    """Request model for script generation"""

    # Required fields
    template: str = Field(..., description="Madlib template with [placeholders]")
    topic: str = Field(..., description="User's topic/subject")
    creator_role: str = Field(..., description="Creator's role/identity (e.g., 'food chef', 'school teacher', 'fitness coach')")
    main_message: str = Field(..., description="Single text describing the creator's main message/goal for this script")
    
    # Optional fields
    niche: Optional[str] = Field(None, description="Content niche (optional, AI will infer from creator_role + topic)")
    style: Optional[str] = Field("conversational", description="Script style: conversational, professional, humorous")
    length: Optional[str] = Field("short", description="Target length: short (30s), medium (60s), long (90s+)")

    @field_validator("template")
    @classmethod
    def validate_template(cls, v):
        """Validate template is not empty"""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("template must be a non-empty string")
        return v.strip()

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v):
        """Validate topic is not empty"""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("topic must be a non-empty string")
        return v.strip()

    @field_validator("creator_role")
    @classmethod
    def validate_creator_role(cls, v):
        """Validate creator_role is not empty"""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("creator_role must be a non-empty string")
        return v.strip()

    @field_validator("main_message")
    @classmethod
    def validate_main_message(cls, v):
        """Validate main_message is not empty"""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("main_message must be a non-empty string")
        return v.strip()

    @field_validator("style")
    @classmethod
    def validate_style(cls, v):
        """Validate style is one of allowed values"""
        if v and v not in ["conversational", "professional", "humorous"]:
            raise ValueError("style must be one of: conversational, professional, humorous")
        return v

    @field_validator("length")
    @classmethod
    def validate_length(cls, v):
        """Validate length is one of allowed values"""
        if v and v not in ["short", "medium", "long"]:
            raise ValueError("length must be one of: short, medium, long")
        return v


class TemplatizeTranscriptRequest(BaseModel):
    """Request model for transcript templatization"""

    transcript: str = Field(..., description="Full transcript text from the video")

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, v):
        """Validate transcript is not empty and within length limit"""
        if not v or not isinstance(v, str):
            raise ValueError("transcript must be a non-empty string")

        v = v.strip()
        if not v:
            raise ValueError("transcript cannot be empty")

        if len(v) > 10000:
            raise ValueError("transcript exceeds maximum length of 10,000 characters")

        return v


# =============================================================================
# Script Generation From Scratch Request Models
# =============================================================================

class GenerateScriptsFromScratchRequest(BaseModel):
    """Request for generating scripts from scratch (no template required)"""

    topic: str = Field(..., max_length=120, description="Main topic/subject of the script")
    audience: Optional[str] = Field(None, max_length=80, description="Target audience")
    hook_style: HookStyle = Field(..., description="Style of the opening hook")
    proof: Optional[str] = Field(None, max_length=500, description="Personal proof or credentials")
    cta_type: CTAType = Field(..., description="Type of call-to-action")
    cta_keyword: Optional[str] = Field(None, max_length=20, description="Keyword for comment CTA")
    tone: Tone = Field(..., description="Voice/tone of the script")
    format: VideoFormat = Field(..., description="Video production format")
    length_seconds: int = Field(..., description="Target length: 30, 45, or 60 seconds")
    reading_speed: ReadingSpeed = Field(..., description="Reading pace for time estimation")

    @field_validator("topic")
    @classmethod
    def validate_topic_not_empty(cls, v):
        """Validate topic is not empty"""
        if not v or not v.strip():
            raise ValueError("topic must be non-empty")
        return v.strip()

    @field_validator("length_seconds")
    @classmethod
    def validate_length_seconds(cls, v):
        """Validate length_seconds is one of allowed values"""
        if v not in [30, 45, 60]:
            raise ValueError("length_seconds must be 30, 45, or 60")
        return v

    @model_validator(mode='after')
    def validate_cta_keyword_required(self):
        """Validate cta_keyword is provided when cta_type is comment_keyword"""
        if self.cta_type == CTAType.COMMENT_KEYWORD and not self.cta_keyword:
            raise ValueError("cta_keyword is required when cta_type is comment_keyword")
        return self


class RefineBeatRequest(BaseModel):
    """Request for refining a single beat of a script"""

    beat_type: BeatType = Field(..., description="Which beat to refine")
    current_text: str = Field(..., description="Current text of the beat to refine")
    action: RefineAction = Field(..., description="Refinement action to apply")
    context: Optional[Dict[str, str]] = Field(
        None, description="Optional context for consistency (topic, audience, tone)"
    )

    @field_validator("current_text")
    @classmethod
    def validate_current_text(cls, v):
        """Validate current_text is not empty"""
        if not v or not v.strip():
            raise ValueError("current_text must be non-empty")
        return v.strip()
