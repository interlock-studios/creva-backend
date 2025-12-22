"""
Configuration validation utilities
Centralizes environment variable validation and configuration checks
"""

import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def validate_required_env_vars(required_vars: List[str], project_name: str = "application") -> None:
    """
    Validate that all required environment variables are set and not placeholder values

    Args:
        required_vars: List of environment variable names to validate
        project_name: Name of the project for logging purposes

    Raises:
        ValueError: If any required environment variables are missing or invalid
    """
    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if not value or value == "your_actual_api_key_here":
            missing_vars.append(var)

    if missing_vars:
        error_msg = f"Missing or invalid required environment variables for {project_name}: {', '.join(missing_vars)}"

        # Add specific guidance for common issues
        if "SCRAPECREATORS_API_KEY" in missing_vars:
            error_msg += "\nPlease update your .env file with your actual ScrapeCreators API key."
        elif "GOOGLE_CLOUD_PROJECT_ID" in missing_vars:
            error_msg += "\nPlease set GOOGLE_CLOUD_PROJECT_ID to your Google Cloud project ID."

        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"All required environment variables validated successfully for {project_name}")


from dataclasses import dataclass


@dataclass
class ProcessingConfig:
    """Video processing configuration"""

    max_direct_processing: int = 5
    direct_processing_timeout: float = 30.0
    video_processing_timeout: float = 300.0
    max_video_size_mb: int = 100
    max_concurrent_processing: int = 50


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""

    requests_per_window: int = 10
    window_seconds: int = 60
    genai_min_interval: float = 1.0
    genai_max_retries: int = 3


@dataclass
class CacheConfig:
    """Caching configuration"""

    ttl_hours: int = 168  # 1 week
    max_cache_size_mb: int = 1000
    cleanup_interval_hours: int = 24


@dataclass
class WorkerConfig:
    """Worker service configuration"""

    polling_interval: float = 1.0  # Reduced from 5.0 for faster job pickup
    batch_size: int = 5  # Increased from 1 for better throughput
    shutdown_timeout: int = 30


@dataclass
class AppCheckConfig:
    """App Check configuration"""

    required: bool = False
    skip_paths: List[str] = None

    def __post_init__(self):
        if self.skip_paths is None:
            self.skip_paths = ["/health", "/docs", "/redoc", "/openapi.json", "/test-api"]


@dataclass
class AppConfig:
    """Main application configuration"""

    environment: str
    project_id: str
    processing: ProcessingConfig
    rate_limiting: RateLimitConfig
    caching: CacheConfig
    worker: WorkerConfig
    app_check: AppCheckConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables"""
        return cls(
            environment=os.getenv("ENVIRONMENT", "production"),
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT_ID"),
            processing=ProcessingConfig(
                max_direct_processing=int(os.getenv("MAX_DIRECT_PROCESSING", "5")),
                direct_processing_timeout=float(os.getenv("DIRECT_PROCESSING_TIMEOUT", "30.0")),
                video_processing_timeout=float(os.getenv("VIDEO_PROCESSING_TIMEOUT", "300.0")),
                max_video_size_mb=int(os.getenv("MAX_VIDEO_SIZE_MB", "100")),
                max_concurrent_processing=int(os.getenv("MAX_CONCURRENT_PROCESSING", "50")),
            ),
            rate_limiting=RateLimitConfig(
                requests_per_window=int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
                window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
                genai_min_interval=float(os.getenv("GENAI_MIN_INTERVAL", "1.0")),
                genai_max_retries=int(os.getenv("GENAI_MAX_RETRIES", "3")),
            ),
            caching=CacheConfig(
                ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "168")),
                max_cache_size_mb=int(os.getenv("MAX_CACHE_SIZE_MB", "1000")),
                cleanup_interval_hours=int(os.getenv("CACHE_CLEANUP_INTERVAL", "24")),
            ),
            worker=WorkerConfig(
                polling_interval=float(os.getenv("WORKER_POLLING_INTERVAL", "5.0")),
                batch_size=int(os.getenv("WORKER_BATCH_SIZE", "1")),
                shutdown_timeout=int(os.getenv("WORKER_SHUTDOWN_TIMEOUT", "30")),
            ),
            app_check=AppCheckConfig(
                required=os.getenv("APPCHECK_REQUIRED", "false").lower() == "true",
                skip_paths=(
                    os.getenv("APPCHECK_SKIP_PATHS", "").split(",")
                    if os.getenv("APPCHECK_SKIP_PATHS")
                    else None
                ),
            ),
        )


def get_config_with_defaults() -> Dict[str, Any]:
    """
    Get application configuration with sensible defaults (legacy compatibility)

    Returns:
        Dictionary containing application configuration
    """
    config = AppConfig.from_env()
    return {
        "environment": config.environment,
        "project_id": config.project_id,
        "cache_ttl_hours": config.caching.ttl_hours,
        "worker_polling_interval": config.worker.polling_interval,
        "worker_batch_size": config.worker.batch_size,
        "worker_shutdown_timeout": config.worker.shutdown_timeout,
        "rate_limit_requests": config.rate_limiting.requests_per_window,
        "rate_limit_window": config.rate_limiting.window_seconds,
    }


def validate_firestore_connection(project_id: str) -> bool:
    """
    Validate Firestore connection

    Args:
        project_id: Google Cloud project ID

    Returns:
        True if connection is valid, False otherwise
    """
    try:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)
        # Test connection by attempting to get a collection reference
        db.collection("test").limit(1).stream()
        logger.info(f"Firestore connection validated for project: {project_id}")
        return True
    except Exception as e:
        logger.error(f"Firestore connection validation failed: {e}")
        return False
