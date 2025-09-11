"""
Enhanced security middleware for API protection
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ThreatDetector:
    """Advanced threat detection and monitoring"""
    
    def __init__(self):
        self.ip_failures = defaultdict(list)
        self.suspicious_patterns = defaultdict(int)
        self.blocked_ips = set()
        self.attack_patterns = {
            "rapid_failures": {"threshold": 200, "window": 300},  # 200 failures in 5 min (very lax)
            "path_traversal": {"threshold": 50, "window": 3600},   # 50 attempts in 1 hour (very lax)
            "bot_behavior": {"threshold": 500, "window": 3600},    # 500 bot-like requests in 1 hour (very lax)
        }
    
    def analyze_request(self, ip: str, path: str, user_agent: str, status: int, app_id: str = None):
        """Analyze request for suspicious patterns"""
        now = datetime.now()
        
        # Track failed authentication attempts
        if status in [401, 403, 429]:
            self.ip_failures[ip].append(now)
            # Clean old failures
            self.ip_failures[ip] = [
                t for t in self.ip_failures[ip] 
                if now - t < timedelta(seconds=self.attack_patterns["rapid_failures"]["window"])
            ]
            
            # Check for rapid failure pattern
            if len(self.ip_failures[ip]) >= self.attack_patterns["rapid_failures"]["threshold"]:
                self._log_security_event("rapid_failures", ip, {
                    "failure_count": len(self.ip_failures[ip]),
                    "app_id": app_id,
                    "user_agent": user_agent
                })
                self.blocked_ips.add(ip)
        
        # Detect bot-like behavior
        if not user_agent or any(bot in user_agent.lower() for bot in ["bot", "crawler", "spider", "scraper"]):
            self.suspicious_patterns[f"bot_{ip}"] += 1
            if self.suspicious_patterns[f"bot_{ip}"] >= self.attack_patterns["bot_behavior"]["threshold"]:
                self._log_security_event("bot_behavior", ip, {
                    "bot_requests": self.suspicious_patterns[f"bot_{ip}"],
                    "user_agent": user_agent
                })
        
        # Detect path traversal attempts and common attack patterns
        suspicious_paths = ["../", "..\\", "/etc/", "/proc/", "/sys/", "passwd", "shadow", "/.git", "/.env", "/admin", "/wp-admin", "/phpmyadmin", "/config", "/.well-known"]
        if any(pattern in path.lower() for pattern in suspicious_paths):
            self.suspicious_patterns[f"traversal_{ip}"] += 1
            self._log_security_event("path_traversal", ip, {
                "attempted_path": path,
                "attempt_count": self.suspicious_patterns[f"traversal_{ip}"]
            })
            
            # Log obvious attack patterns but don't immediately block IP (allow legitimate access)
            if any(obvious_attack in path.lower() for obvious_attack in ["/.git", "/.env", "/wp-admin", "/phpmyadmin"]):
                self._log_security_event("attack_pattern_detected", ip, {
                    "reason": "obvious_attack_pattern",
                    "attempted_path": path,
                    "note": "logged_but_not_blocked"
                })
                # Only block IP after many obvious attacks (25+ in 10 minutes)
                self.suspicious_patterns[f"obvious_attacks_{ip}"] += 1
                if self.suspicious_patterns[f"obvious_attacks_{ip}"] >= 25:
                    self.blocked_ips.add(ip)
                    self._log_security_event("ip_blocked_multiple_attacks", ip, {
                        "attack_count": self.suspicious_patterns[f"obvious_attacks_{ip}"],
                        "reason": "multiple_obvious_attacks"
                    })
            elif self.suspicious_patterns[f"traversal_{ip}"] >= self.attack_patterns["path_traversal"]["threshold"]:
                self.blocked_ips.add(ip)
        
        # Detect unusual endpoints (only block on very obvious probing)
        if status == 404 and not any(allowed in path for allowed in ["/health", "/docs", "/redoc", "/process", "/status", "/admin", "/metrics"]):
            self.suspicious_patterns[f"404_{ip}"] += 1
            if self.suspicious_patterns[f"404_{ip}"] > 100:  # Much higher threshold
                self._log_security_event("endpoint_probing", ip, {
                    "probed_path": path,
                    "probe_count": self.suspicious_patterns[f"404_{ip}"]
                })
                # Only block after excessive probing
                if self.suspicious_patterns[f"404_{ip}"] > 200:
                    self.blocked_ips.add(ip)
    
    def is_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.blocked_ips
    
    def _log_security_event(self, event_type: str, ip: str, details: Dict[str, Any]):
        """Log security events with structured data"""
        logger.warning(
            f"🚨 Security event detected: {event_type}",
            extra={
                "security_event": event_type,
                "ip_address": ip,
                "severity": "high" if event_type in ["rapid_failures", "path_traversal"] else "medium",
                "timestamp": datetime.utcnow().isoformat(),
                "details": details
            }
        )


class EnhancedRateLimiter:
    """Smart rate limiting with per-user and per-IP limits"""
    
    def __init__(self):
        self.ip_limits = defaultdict(list)
        self.user_limits = defaultdict(list)
        self.endpoint_limits = defaultdict(lambda: defaultdict(list))
    
    def check_limits(self, request: Request, endpoint_config: Dict[str, Any]) -> Optional[JSONResponse]:
        """Check rate limits and return error response if exceeded"""
        current_time = time.time()
        ip = self._get_client_ip(request)
        
        # Get user identifier from App Check
        app_claims = getattr(request.state, 'appcheck_claims', {})
        user_id = app_claims.get('app_id') if app_claims else None
        
        # Determine limits based on authentication status
        if user_id:
            # Authenticated user - very generous limits
            ip_max = endpoint_config.get("ip_limit_auth", 100)
            user_max = endpoint_config.get("user_limit", 50)
            window = endpoint_config.get("window", 300)
            rate_key = f"user_{user_id}"
        else:
            # Unauthenticated - still generous for testing
            ip_max = endpoint_config.get("ip_limit_unauth", 50)
            user_max = ip_max  # Same as IP for unauth
            window = endpoint_config.get("window", 300)
            rate_key = f"ip_{ip}"
        
        # Check IP limit (prevents single IP from overwhelming)
        self.ip_limits[ip] = [
            t for t in self.ip_limits[ip] 
            if current_time - t < window
        ]
        if len(self.ip_limits[ip]) >= ip_max:
            return self._rate_limit_response("IP rate limit exceeded", window)
        
        # Check user/session limit
        self.user_limits[rate_key] = [
            t for t in self.user_limits[rate_key] 
            if current_time - t < window
        ]
        if len(self.user_limits[rate_key]) >= user_max:
            return self._rate_limit_response("User rate limit exceeded", window)
        
        # Record both limits
        self.ip_limits[ip].append(current_time)
        self.user_limits[rate_key].append(current_time)
        
        return None  # No limit exceeded
    
    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP handling proxy headers"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host
    
    def _rate_limit_response(self, message: str, retry_after: int) -> JSONResponse:
        """Create rate limit error response"""
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": message,
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # HSTS only for HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy for API responses
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request size to prevent memory exhaustion attacks"""
    
    def __init__(self, app, max_size: int = 1024 * 1024):  # 1MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next):
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Request too large",
                            "detail": f"Request size {size} bytes exceeds limit of {self.max_size} bytes"
                        }
                    )
            except ValueError:
                pass  # Invalid content-length header, let it through
        
        return await call_next(request)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Main security middleware combining all security features"""
    
    def __init__(self, app, config: Dict[str, Any]):
        super().__init__(app)
        self.threat_detector = ThreatDetector()
        self.rate_limiter = EnhancedRateLimiter()
        self.config = config
        self.skip_paths = config.get("skip_paths", ["/health", "/docs", "/redoc", "/openapi.json"])
    
    async def dispatch(self, request: Request, call_next):
        # Skip security checks for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        ip = self.rate_limiter._get_client_ip(request)
        
        # Allow legitimate paths without blocking (but still log attacks)
        legitimate_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json", "/process", "/status", "/admin", "/metrics"]
        is_legitimate_path = any(request.url.path.startswith(path) for path in legitimate_paths)
        
        # Check if IP is blocked (but allow legitimate paths even from blocked IPs for now)
        if self.threat_detector.is_blocked(ip) and not is_legitimate_path:
            logger.warning(f"Blocked request from {ip} to {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "Access denied", "detail": "IP address blocked due to suspicious activity"}
            )
        
        # Check rate limits
        endpoint_config = self._get_endpoint_config(request.url.path)
        rate_limit_response = self.rate_limiter.check_limits(request, endpoint_config)
        if rate_limit_response:
            # Log rate limit violation for threat detection
            self.threat_detector.analyze_request(
                ip=ip,
                path=request.url.path,
                user_agent=request.headers.get("user-agent", ""),
                status=429
            )
            return rate_limit_response
        
        # Process request
        response = await call_next(request)
        
        # Analyze request for threats (after processing to get status code)
        app_claims = getattr(request.state, 'appcheck_claims', {})
        app_id = app_claims.get('app_id') if app_claims else None
        
        self.threat_detector.analyze_request(
            ip=ip,
            path=request.url.path,
            user_agent=request.headers.get("user-agent", ""),
            status=response.status_code,
            app_id=app_id
        )
        
        return response
    
    def _get_endpoint_config(self, path: str) -> Dict[str, Any]:
        """Get rate limiting config for specific endpoint"""
        from src.config.security import security_config
        
        rate_limits = security_config.rate_limits
        
        # Find matching endpoint config
        for endpoint_path, config in rate_limits.items():
            if endpoint_path != "default" and endpoint_path in path:
                return config
        
        # Return default config
        return rate_limits["default"]
