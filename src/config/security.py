"""
Security configuration settings
"""

import os
from typing import Dict, List, Any


class SecurityConfig:
    """Centralized security configuration"""
    
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins based on environment"""
        if self.environment == "production":
            # Allow all origins for frontend access
            # TODO: Restrict to specific domains once frontend domains are known
            return ["*"]
        else:
            # Development: Allow localhost for testing + all origins
            return [
                "http://localhost:3000",
                "http://localhost:8080", 
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8080",
                "*"  # Allow all origins for development
            ]
    
    @property
    def trusted_hosts(self) -> List[str]:
        """Get trusted hosts based on environment"""
        if self.environment == "production":
            # Cloud Run domains for production
            return [
                "*.run.app",
                "*.a.run.app",
                "workout-parser-v2-341666880405.us-central1.run.app"
            ]
        else:
            # Development: Allow all for testing
            return ["*"]
    
    @property
    def rate_limits(self) -> Dict[str, Dict[str, Any]]:
        """Rate limiting configuration per endpoint"""
        # Much more generous rate limits for normal usage
        base_limits = {
            "/process": {
                "user_limit": 100,      # 100 requests per authenticated user per minute
                "ip_limit_auth": 200,   # 200 requests per IP for authenticated users
                "ip_limit_unauth": 50,  # 50 requests per IP for unauthenticated
                "window": 60            # 1 minute window
            },
            "/admin": {
                "user_limit": 200,     # 200 requests per user for admin endpoints
                "ip_limit_auth": 300,
                "ip_limit_unauth": 100,
                "window": 60
            },
            "default": {
                "user_limit": 150,     # 150 requests per user for other endpoints
                "ip_limit_auth": 250,
                "ip_limit_unauth": 75,
                "window": 60
            }
        }
        
        if self.environment == "development":
            # Slightly more lenient for development
            for endpoint in base_limits:
                base_limits[endpoint]["user_limit"] += 5
                base_limits[endpoint]["ip_limit_auth"] += 10
                base_limits[endpoint]["ip_limit_unauth"] += 5
        
        return base_limits
    
    @property
    def threat_detection(self) -> Dict[str, Dict[str, int]]:
        """Threat detection thresholds - much more lax, only block real attacks"""
        return {
            "rapid_failures": {"threshold": 100, "window": 300},  # 100 failures in 5 min
            "path_traversal": {"threshold": 20, "window": 3600},   # 20 attempts in 1 hour
            "bot_behavior": {"threshold": 500, "window": 3600},    # 500 bot requests in 1 hour
            "endpoint_probing": {"threshold": 50, "window": 300},  # 50 404s in 5 min
        }
    
    @property
    def request_limits(self) -> Dict[str, Any]:
        """Request size and other limits"""
        return {
            "max_request_size": 1024 * 1024,  # 1MB
            "max_url_length": 2048,
            "max_header_size": 8192
        }
    
    @property
    def security_headers(self) -> Dict[str, str]:
        """Security headers to add to responses"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none';",
        }
    
    @property
    def monitoring_config(self) -> Dict[str, Any]:
        """Security monitoring configuration"""
        return {
            "log_security_events": True,
            "alert_thresholds": {
                "invalid_tokens_per_hour": 50,
                "blocked_ips_per_hour": 10,
                "failed_requests_per_minute": 20
            },
            "retention_days": 30
        }


# Global security config instance
security_config = SecurityConfig()
