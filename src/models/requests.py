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
