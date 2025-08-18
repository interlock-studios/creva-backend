"""
Structured logging utilities for request correlation and observability
"""
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from fastapi import Request

# Context variables for request tracing
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
operation_var: ContextVar[str] = ContextVar('operation', default='')
service_var: ContextVar[str] = ContextVar('service', default='api')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')


class StructuredLogger:
    """Structured logger with request correlation"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.service_name = name.split('.')[-1]  # Extract service name from module
    
    def _build_log_data(self, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build structured log data with context"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": service_var.get(self.service_name),
            "request_id": request_id_var.get(),
            "operation": operation_var.get(),
            "user_id": user_id_var.get() or None,
            "message": message,
        }
        
        if extra:
            # Merge extra data, avoiding conflicts with reserved keys
            for key, value in extra.items():
                if key not in log_data:
                    log_data[key] = value
                else:
                    log_data[f"extra_{key}"] = value
            
        return log_data
    
    def _log_structured(self, level: str, message: str, **kwargs):
        """Log structured data to stdout for Cloud Logging"""
        log_data = self._build_log_data(message, kwargs)
        log_data["severity"] = level
        
        # Use print to stdout which Cloud Run captures as structured logs
        print(json.dumps(log_data))
    
    def info(self, message: str, **kwargs):
        """Log info level message with structured data"""
        self._log_structured("INFO", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error level message with structured data"""
        self._log_structured("ERROR", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message with structured data"""
        self._log_structured("WARNING", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug level message with structured data"""
        self._log_structured("DEBUG", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical level message with structured data"""
        self._log_structured("CRITICAL", message, **kwargs)


def set_request_context(
    request_id: str,
    operation: str = "",
    service: str = "api",
    user_id: str = ""
):
    """Set request context for logging correlation"""
    request_id_var.set(request_id)
    operation_var.set(operation)
    service_var.set(service)
    user_id_var.set(user_id)


def get_request_context() -> Dict[str, str]:
    """Get current request context"""
    return {
        "request_id": request_id_var.get(),
        "operation": operation_var.get(),
        "service": service_var.get(),
        "user_id": user_id_var.get()
    }


def log_performance_metric(
    operation: str,
    duration_ms: float,
    success: bool = True,
    **additional_metrics
):
    """Log performance metrics in structured format"""
    logger = StructuredLogger(__name__)
    
    metric_data = {
        "event_type": "performance_metric",
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "success": success,
        **additional_metrics
    }
    
    if success:
        logger.info("Performance metric recorded", **metric_data)
    else:
        logger.warning("Performance metric recorded (failed)", **metric_data)


def log_business_event(
    event_type: str,
    event_data: Dict[str, Any],
    user_id: str = None
):
    """Log business events for analytics"""
    logger = StructuredLogger(__name__)
    
    # Temporarily set user context if provided
    original_user_id = user_id_var.get()
    if user_id:
        user_id_var.set(user_id)
    
    try:
        logger.info(f"Business event: {event_type}", 
                   event_category="business_event",
                   business_event_type=event_type,
                   **event_data)
    finally:
        # Restore original user context
        user_id_var.set(original_user_id)


class RequestLoggingMiddleware:
    """Middleware for request logging and correlation"""
    
    def __init__(self, app, logger_name: str = "request"):
        self.app = app
        self.logger = StructuredLogger(logger_name)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request information
        request = Request(scope, receive)
        
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", f"{time.time()}-{id(request)}")
        operation = f"{request.method} {request.url.path}"
        
        # Extract user information if available (from headers, auth, etc.)
        user_id = request.headers.get("X-User-ID", "")
        
        # Set request context
        set_request_context(
            request_id=request_id,
            operation=operation,
            service="api",
            user_id=user_id
        )
        
        start_time = time.time()
        
        # Log request start
        self.logger.info("Request started",
                        method=request.method,
                        path=request.url.path,
                        query_params=str(request.query_params) if request.query_params else None,
                        user_agent=request.headers.get("User-Agent", ""),
                        client_ip=self._get_client_ip(request),
                        content_length=request.headers.get("Content-Length"))
        
        # Process request
        response_started = False
        status_code = 500  # Default to error if something goes wrong
        
        async def send_wrapper(message):
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                # Add request ID to response headers
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                headers.append((b"x-process-time", str(time.time() - start_time).encode()))
                message["headers"] = headers
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # Log unhandled exceptions
            self.logger.error("Unhandled exception in request",
                            error_type=type(e).__name__,
                            error_message=str(e),
                            exc_info=True)
            raise
        finally:
            # Log request completion
            process_time = time.time() - start_time
            
            self.logger.info("Request completed",
                           method=request.method,
                           path=request.url.path,
                           status_code=status_code,
                           process_time_ms=round(process_time * 1000, 2),
                           response_started=response_started)
            
            # Log performance metric
            log_performance_metric(
                operation=operation,
                duration_ms=process_time * 1000,
                success=200 <= status_code < 400,
                status_code=status_code,
                method=request.method,
                path=request.url.path
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers"""
        # Check for forwarded headers (common in load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        return request.client.host if request.client else "unknown"
