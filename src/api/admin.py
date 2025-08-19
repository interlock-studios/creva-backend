"""
Admin and testing endpoints
"""

from fastapi import APIRouter, Request, Depends, HTTPException
import os
import logging

from src.models.requests import CacheInvalidationRequest
from src.models.responses import TestAPIResponse, CacheInvalidationResponse, AppCheckStatusResponse
from src.services.cache_service import CacheService
from src.services.tiktok_scraper import (
    TikTokScraper,
    ScrapingOptions as TikTokScrapingOptions,
    APIError as TikTokAPIError,
    NetworkError as TikTokNetworkError,
    ValidationError as TikTokValidationError,
)
from src.services.instagram_scraper import (
    InstagramScraper,
    ScrapingOptions as InstagramScrapingOptions,
    APIError as InstagramAPIError,
    NetworkError as InstagramNetworkError,
    ValidationError as InstagramValidationError,
)
from src.services.appcheck_middleware import verify_appcheck_token, get_appcheck_service
from src.services.config_validator import get_config_with_defaults

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["admin"])

# Initialize services
cache_service = CacheService()
tiktok_scraper = TikTokScraper()
instagram_scraper = InstagramScraper()
appcheck_service = get_appcheck_service()
config = get_config_with_defaults()


@router.get("/test-api", response_model=TestAPIResponse)
async def test_api(req: Request):
    """Test the ScrapeCreators API connection for both TikTok and Instagram"""
    results = {}

    # Test TikTok
    try:
        test_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"
        options = TikTokScrapingOptions(
            get_transcript=False,
            trim_response=True,
            max_retries=1,
            timeout=10,
        )
        info = await tiktok_scraper.get_video_info(test_url, options)
        results["tiktok"] = {
            "status": "success",
            "message": "TikTok API working correctly",
            "test_video": {
                "title": info["metadata"]["title"][:100],
                "author": info["metadata"]["author"],
                "duration": info["metadata"]["duration_seconds"],
            },
        }
    except (TikTokValidationError, TikTokAPIError, TikTokNetworkError) as e:
        results["tiktok"] = {"status": "error", "message": str(e), "type": type(e).__name__}
    except Exception as e:
        results["tiktok"] = {"status": "error", "type": "unexpected", "message": str(e)}

    # Test Instagram
    try:
        test_url = "https://www.instagram.com/reel/DDXT72CSnUJ/"
        options = InstagramScrapingOptions(
            trim_response=True,
            max_retries=1,
            timeout=10,
        )
        info = await instagram_scraper.get_video_info(test_url, options)
        results["instagram"] = {
            "status": "success",
            "message": "Instagram API working correctly",
            "test_video": {
                "title": info["metadata"]["title"][:100],
                "author": info["metadata"]["author"],
                "duration": info["metadata"]["duration_seconds"],
            },
        }
    except (InstagramValidationError, InstagramAPIError, InstagramNetworkError) as e:
        results["instagram"] = {"status": "error", "message": str(e), "type": type(e).__name__}
    except Exception as e:
        results["instagram"] = {"status": "error", "type": "unexpected", "message": str(e)}

    # Overall status
    overall_status = (
        "success" if all(r["status"] == "success" for r in results.values()) else "partial"
    )

    return TestAPIResponse(
        status=overall_status, message="API connection test results", platforms=results
    )


@router.delete("/cache/{url_hash}", response_model=CacheInvalidationResponse)
async def invalidate_cache_by_hash(url_hash: str):
    """Invalidate cache entry by URL hash (for debugging)"""
    # This is a debug endpoint - in production you might want to restrict access
    if config["environment"] == "production":
        raise HTTPException(status_code=404, detail="Not found")

    try:
        if cache_service.db:
            doc_ref = cache_service.cache_collection.document(url_hash)
            exists = doc_ref.get().exists
            if exists:
                doc_ref.delete()
                return CacheInvalidationResponse(
                    url="unknown",  # We don't have the original URL
                    invalidated=True,
                    cache_key=url_hash,
                )
            else:
                return CacheInvalidationResponse(
                    url="unknown", invalidated=False, cache_key=url_hash
                )
        else:
            raise HTTPException(status_code=503, detail="Cache service not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/invalidate", response_model=CacheInvalidationResponse)
async def invalidate_cache_by_url(request: CacheInvalidationRequest):
    """Invalidate cache for a specific TikTok URL"""
    if config["environment"] == "production":
        raise HTTPException(status_code=404, detail="Not found")

    success = cache_service.invalidate_cache(request.url, request.localization)
    return CacheInvalidationResponse(
        url=request.url,
        invalidated=success,
        cache_key=cache_service._generate_cache_key(request.url, request.localization),
    )


@router.post("/test-appcheck")
async def test_appcheck(req: Request, appcheck_claims: dict = Depends(verify_appcheck_token)):
    """Test endpoint that requires valid App Check token"""
    request_id = getattr(req.state, "request_id", "unknown")

    return {
        "status": "success",
        "message": "App Check token verified successfully",
        "request_id": request_id,
        "app_check_claims": {
            "app_id": appcheck_claims.get("app_id"),
            "iss": appcheck_claims.get("iss"),
            "aud": appcheck_claims.get("aud"),
            "verified_at": appcheck_claims.get("verified_at"),
        },
    }


@router.get("/appcheck-status", response_model=AppCheckStatusResponse)
async def appcheck_status():
    """Get App Check service status and configuration"""
    if config["environment"] == "production":
        raise HTTPException(status_code=404, detail="Not found")

    appcheck_required = os.getenv("APPCHECK_REQUIRED", "false").lower() == "true"
    appcheck_skip_paths = ["/health", "/docs", "/redoc", "/openapi.json", "/test-api"]

    return AppCheckStatusResponse(
        app_check_enabled=True,
        app_check_required=appcheck_required,
        skip_paths=appcheck_skip_paths,
        service_stats=appcheck_service.get_stats(),
        service_healthy=appcheck_service.is_healthy(),
    )
