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


def get_config_with_defaults() -> Dict[str, Any]:
    """
    Get application configuration with sensible defaults

    Returns:
        Dictionary containing application configuration
    """
    return {
        "environment": os.getenv("ENVIRONMENT", "production"),
        "project_id": os.getenv("GOOGLE_CLOUD_PROJECT_ID"),
        "cache_ttl_hours": int(os.getenv("CACHE_TTL_HOURS", "168")),  # 1 week
        "worker_polling_interval": float(os.getenv("WORKER_POLLING_INTERVAL", "5")),
        "worker_batch_size": int(os.getenv("WORKER_BATCH_SIZE", "1")),
        "worker_shutdown_timeout": int(os.getenv("WORKER_SHUTDOWN_TIMEOUT", "30")),
        "rate_limit_requests": int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
        "rate_limit_window": int(os.getenv("RATE_LIMIT_WINDOW", "60")),
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
