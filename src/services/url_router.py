import re
from urllib.parse import urlparse
from typing import Optional
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
import logging

logger = logging.getLogger(__name__)


class URLRouter:
    """
    Route URLs to appropriate scrapers based on platform detection.
    
    This service determines whether a given URL is from TikTok or Instagram
    and provides validation for supported platforms.
    """
    
    # Platform type literals
    Platform = Literal["tiktok", "instagram"]
    
    @staticmethod
    def detect_platform(url: str) -> Optional[Platform]:
        """
        Detect which platform a URL belongs to.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Platform name ("tiktok" or "instagram") or None if not recognized
        """
        if not url or not isinstance(url, str):
            return None
            
        url = url.strip()
        if not url:
            return None
            
        # Parse URL
        try:
            parsed = urlparse(url)
            # Add scheme if missing
            if not parsed.scheme:
                url = f"https://{url}"
                parsed = urlparse(url)
                
            domain = parsed.netloc.lower()
            
            # TikTok domains
            tiktok_domains = [
                "tiktok.com",
                "www.tiktok.com",
                "vm.tiktok.com",
                "m.tiktok.com",
                "vt.tiktok.com"
            ]
            
            # Instagram domains
            instagram_domains = [
                "instagram.com",
                "www.instagram.com",
                "instagr.am",
                "www.instagr.am"
            ]
            
            if domain in tiktok_domains:
                logger.debug(f"URL detected as TikTok: {url}")
                return "tiktok"
            elif domain in instagram_domains:
                logger.debug(f"URL detected as Instagram: {url}")
                return "instagram"
            else:
                logger.warning(f"URL domain '{domain}' not recognized as TikTok or Instagram")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing URL '{url}': {e}")
            return None
    
    @staticmethod
    def is_tiktok_url(url: str) -> bool:
        """Check if URL is a TikTok URL"""
        return URLRouter.detect_platform(url) == "tiktok"
    
    @staticmethod
    def is_instagram_url(url: str) -> bool:
        """Check if URL is an Instagram URL"""
        return URLRouter.detect_platform(url) == "instagram"
    
    @staticmethod
    def validate_url(url: str) -> tuple:
        """
        Validate URL and detect platform.
        
        Args:
            url: The URL to validate
            
        Returns:
            Tuple of (is_valid, error_message, platform)
        """
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string", None
            
        url = url.strip()
        if not url:
            return False, "URL cannot be empty", None
            
        platform = URLRouter.detect_platform(url)
        
        if platform is None:
            return False, "URL must be from TikTok or Instagram", None
            
        # Additional validation based on platform
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
                parsed = urlparse(url)
                
            path = parsed.path
            
            if platform == "tiktok":
                # TikTok URL patterns
                # Examples:
                # https://www.tiktok.com/@username/video/1234567890
                # https://vm.tiktok.com/XXXXXXXXX/
                # https://m.tiktok.com/v/1234567890.html
                if not path or path == "/":
                    return False, "Invalid TikTok URL format", platform
                    
            elif platform == "instagram":
                # Instagram URL patterns
                valid_patterns = [
                    r'^/p/[A-Za-z0-9_-]+/?$',  # Post URL
                    r'^/reel/[A-Za-z0-9_-]+/?$',  # Reel URL
                    r'^/reels?/[A-Za-z0-9_-]+/?$',  # Alternative reel URL
                ]
                
                if not any(re.match(pattern, path) for pattern in valid_patterns):
                    return False, "URL must be an Instagram post or reel", platform
                    
            return True, None, platform
            
        except Exception as e:
            logger.error(f"Error validating URL '{url}': {e}")
            return False, f"Invalid URL format: {e}", None
    
    @staticmethod
    def get_platform_display_name(platform: Platform) -> str:
        """Get display name for platform"""
        return {
            "tiktok": "TikTok",
            "instagram": "Instagram"
        }.get(platform, platform.title())