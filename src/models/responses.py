"""
Response models for API endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class ExerciseSet(BaseModel):
    """Individual exercise set"""
    reps: Optional[int] = Field(None, description="Number of repetitions")
    weight_lbs: Optional[float] = Field(None, description="Weight in pounds")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    distance_miles: Optional[float] = Field(None, description="Distance in miles")
    rest_seconds: Optional[int] = Field(90, description="Rest time in seconds")


class Exercise(BaseModel):
    """Individual exercise in workout"""
    name: str = Field(..., description="Exercise name")
    muscle_groups: List[str] = Field(..., description="Target muscle groups")
    equipment: str = Field(..., description="Required equipment")
    sets: List[ExerciseSet] = Field(..., description="Exercise sets")
    instructions: Optional[str] = Field(None, description="Exercise instructions")


class WorkoutData(BaseModel):
    """Complete workout information"""
    title: str = Field(..., description="Workout title")
    description: Optional[str] = Field(None, description="Workout description")
    workout_type: str = Field(..., description="Type of workout")
    duration_minutes: Optional[int] = Field(None, description="Total workout duration")
    difficulty_level: int = Field(..., ge=1, le=10, description="Difficulty from 1-10")
    exercises: List[Exercise] = Field(..., description="List of exercises")
    tags: Optional[List[str]] = Field(None, description="Workout tags")
    creator: Optional[str] = Field(None, description="Content creator")


class QueuedResponse(BaseModel):
    """Response for queued processing"""
    status: str = Field(..., description="Processing status")
    job_id: str = Field(..., description="Job identifier")
    message: str = Field(..., description="Status message")
    check_url: str = Field(..., description="URL to check job status")


# ProcessResponse is handled as Union type directly in route handlers
# No need for a separate model class since FastAPI handles Union types well


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
    result: Optional[WorkoutData] = Field(None, description="Processing result if completed")


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
