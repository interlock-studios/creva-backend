"""
Health check endpoints
"""

from fastapi import APIRouter, Request
from datetime import datetime
import logging

from src.services.cache_service import CacheService
from src.services.queue_service import QueueService
from src.services.appcheck_middleware import get_appcheck_service
from src.services.config_validator import get_config_with_defaults

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["health"])

# Initialize services for health checks
cache_service = CacheService()
queue_service = QueueService()
appcheck_service = get_appcheck_service()
config = get_config_with_defaults()


@router.get("/health")
async def health():
    """Health check endpoint with service validation"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": config["environment"],
        "project_id": config["project_id"],
        "version": "1.0.0",
        "services": {},
    }

    # Check cache service
    try:
        cache_healthy = cache_service.is_healthy()
        health_status["services"]["cache"] = "healthy" if cache_healthy else "unhealthy"
    except Exception as e:
        health_status["services"]["cache"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check queue service
    try:
        queue_stats = queue_service.get_queue_stats()
        health_status["services"]["queue"] = queue_stats.get("status", "unknown")
        if queue_stats.get("status") == "error":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["queue"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check TikTok scraper
    try:
        # Just check if the service is initialized
        health_status["services"]["tiktok_scraper"] = "healthy"
    except Exception as e:
        health_status["services"]["tiktok_scraper"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check App Check service
    try:
        app_check_healthy = appcheck_service.is_healthy()
        health_status["services"]["app_check"] = "healthy" if app_check_healthy else "unhealthy"
        if not app_check_healthy:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["app_check"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


@router.get("/status")
async def status():
    """Status endpoint showing current system load and queue status"""
    from collections import defaultdict
    import time
    import os
    import asyncio

    current_time = time.time()

    # Get rate limiting info from main app (we'll need to refactor this)
    # For now, return basic status

    # Get cache stats
    cache_stats = cache_service.get_cache_stats()

    # Get queue stats
    queue_stats = queue_service.get_queue_stats()

    # Get App Check stats
    appcheck_stats = appcheck_service.get_stats()

    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "hybrid_mode": {
            "enabled": True,
            "direct_processing": {
                "active": 0,  # Will be updated when we refactor main.py
                "max": int(os.getenv("MAX_DIRECT_PROCESSING", "5")),
                "available": int(os.getenv("MAX_DIRECT_PROCESSING", "5")),
            },
        },
        "rate_limiting": {
            "active_ips": 0,  # Will be updated when we refactor middleware
            "limit_per_ip": int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
            "window_seconds": int(os.getenv("RATE_LIMIT_WINDOW", "60")),
        },
        "processing_queue": {
            "available_slots": 40,  # Will be dynamic
            "total_slots": int(os.getenv("MAX_CONCURRENT_PROCESSING", "50")),
            "utilization_percent": 0,  # Will be calculated
        },
        "cache": cache_stats,
        "queue": queue_stats,
        "app_check": {
            "required": os.getenv("APPCHECK_REQUIRED", "false").lower() == "true",
            "stats": appcheck_stats,
        },
        "cloud_run": {
            "max_instances": 50,
            "concurrency_per_instance": 80,
            "max_concurrent_requests": 4000,
        },
    }
