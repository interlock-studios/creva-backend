"""
Response models for Creva API endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class CreatorContent(BaseModel):
    """Complete creator content extracted from social media videos"""

    # Core fields
    title: str = Field(..., description="Video title")
    description: Optional[str] = Field(None, description="Video description/caption")
    image: Optional[str] = Field(None, description="Thumbnail image URL or base64-encoded JPEG")
    
    # Creator content - Priority #1 and #2
    transcript: Optional[str] = Field(
        None, 
        description="Full transcript of everything said in the video"
    )
    hook: Optional[str] = Field(
        None, 
        description="Attention-grabbing opening line (first 10-30 seconds)"
    )
    
    # Content classification - Format and Niche
    format: Optional[str] = Field(
        None,
        description="Video format/style (e.g., 'talking_head', 'voiceover', 'reaction', 'green_screen')"
    )
    niche: Optional[str] = Field(
        None,
        description="Primary content niche/category (e.g., 'fitness', 'business', 'food')"
    )
    niche_detail: Optional[str] = Field(
        None,
        description="Specific subcategory or topic detail (e.g., 'meal prep for bodybuilders')"
    )
    secondary_niches: Optional[List[str]] = Field(
        None,
        description="Secondary topic categories if video spans multiple niches"
    )
    
    # Metadata
    creator: Optional[str] = Field(None, description="Content creator username (e.g., '@creator')")
    platform: Optional[str] = Field(None, description="Source platform: 'tiktok' or 'instagram'")
    tags: Optional[List[str]] = Field(None, description="Hashtags from the post")
    
    # Cache indicator
    cached: Optional[bool] = Field(None, description="Whether result was served from cache")
    
    # Hook analysis
    analysis: Optional["HookAnalysis"] = Field(None, description="Hook analysis explaining why it works")


# Legacy alias for backward compatibility during transition
RecipeContent = CreatorContent
RelationshipContent = CreatorContent


class QueuedResponse(BaseModel):
    """Response for queued processing"""

    status: str = Field(..., description="Processing status")
    job_id: str = Field(..., description="Job identifier")
    message: str = Field(..., description="Status message")
    check_url: str = Field(..., description="URL to check job status")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    environment: str = Field(..., description="Environment name")
    project_id: str = Field(..., description="Google Cloud project ID")
    version: str = Field(..., description="Application version")
    services: Dict[str, str] = Field(..., description="Individual service health")


class StatusResponse(BaseModel):
    """System status response"""

    status: str = Field(..., description="System status")
    timestamp: datetime = Field(..., description="Status timestamp")
    hybrid_mode: Dict[str, Any] = Field(..., description="Hybrid processing info")
    rate_limiting: Dict[str, Any] = Field(..., description="Rate limiting info")
    processing_queue: Dict[str, Any] = Field(..., description="Queue status")
    cache: Dict[str, Any] = Field(..., description="Cache statistics")
    queue: Dict[str, Any] = Field(..., description="Queue statistics")
    app_check: Dict[str, Any] = Field(..., description="App Check status")
    cloud_run: Dict[str, Any] = Field(..., description="Cloud Run configuration")


class JobStatusResponse(BaseModel):
    """Job status response"""

    status: str = Field(..., description="Job status")
    created_at: Optional[datetime] = Field(None, description="Job creation time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    attempts: Optional[int] = Field(None, description="Number of attempts")
    last_error: Optional[str] = Field(None, description="Last error message")
    result: Optional[CreatorContent] = Field(
        None, description="Processing result if completed"
    )


class ErrorResponse(BaseModel):
    """Standard error response"""

    error: Dict[str, Any] = Field(..., description="Error details")
    request_id: str = Field(..., description="Request identifier")
    timestamp: datetime = Field(..., description="Error timestamp")
    path: str = Field(..., description="Request path")


class TestAPIResponse(BaseModel):
    """Test API response"""

    status: str = Field(..., description="Overall test status")
    message: str = Field(..., description="Test message")
    platforms: Dict[str, Dict[str, Any]] = Field(..., description="Platform test results")


class CacheInvalidationResponse(BaseModel):
    """Cache invalidation response"""

    url: str = Field(..., description="URL that was invalidated")
    invalidated: bool = Field(..., description="Whether invalidation was successful")
    cache_key: str = Field(..., description="Cache key that was invalidated")


class AppCheckStatusResponse(BaseModel):
    """App Check status response"""

    app_check_enabled: bool = Field(..., description="Whether App Check is enabled")
    app_check_required: bool = Field(..., description="Whether App Check is required")
    skip_paths: List[str] = Field(..., description="Paths that skip App Check")
    service_stats: Dict[str, Any] = Field(..., description="Service statistics")
    service_healthy: bool = Field(..., description="Service health status")


class HookAnalysis(BaseModel):
    """Analysis of why a hook works"""

    hook_formula: str = Field(..., description="Machine-readable formula type")
    hook_formula_name: str = Field(..., description="Human-readable formula name")
    explanation: str = Field(..., description="2-3 sentence explanation of psychological triggers")
    why_it_works: List[str] = Field(..., description="Bullet points of psychological triggers")
    replicable_pattern: str = Field(..., description="Template with [placeholders] for vault")


class ScriptParts(BaseModel):
    """Parts of a generated script"""

    hook: str = Field(..., description="Opening hook (first 3 seconds)")
    body: str = Field(..., description="Main content body")
    call_to_action: str = Field(..., description="Ending call to action")


class GeneratedScript(BaseModel):
    """Generated script response"""

    success: bool = Field(True, description="Whether generation was successful")
    script: ScriptParts = Field(..., description="Primary generated script")
    full_script: str = Field(..., description="Complete script as one readable string")
    variations: List[ScriptParts] = Field(..., description="Alternative script variations")
    estimated_duration: str = Field(..., description="Estimated video duration")


class TemplatizeTranscriptResponse(BaseModel):
    """Successful templatize transcript response"""

    success: bool = Field(True, description="Whether templatization was successful")
    template: str = Field(..., description="Templatized version with [placeholder] format")


class TemplatizeErrorResponse(BaseModel):
    """Error response for templatize transcript endpoint"""

    success: bool = Field(False, description="Whether templatization was successful")
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
