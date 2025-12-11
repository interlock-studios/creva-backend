"""
Request models for API endpoints
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


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

    template: str = Field(..., description="Madlib template with [placeholders]")
    topic: str = Field(..., description="User's topic/subject")
    niche: Optional[str] = Field("general", description="Content niche")
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
