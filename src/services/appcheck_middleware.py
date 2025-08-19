"""
Firebase App Check Middleware and Decorators
"""

import logging
from functools import wraps
from typing import Optional, Callable, Any

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .firebase_appcheck import AppCheckService, AppCheckError

logger = logging.getLogger(__name__)

# Global App Check service instance
_appcheck_service: Optional[AppCheckService] = None


def get_appcheck_service() -> AppCheckService:
    """Get or create the global App Check service instance"""
    global _appcheck_service
    if _appcheck_service is None:
        _appcheck_service = AppCheckService()
    return _appcheck_service


class AppCheckMiddleware:
    """FastAPI middleware for App Check verification"""

    def __init__(self, app, skip_paths: Optional[list] = None, required: bool = True):
        """
        Initialize App Check middleware

        Args:
            app: FastAPI app instance
            skip_paths: List of paths to skip App Check verification
            required: If True, requests without valid App Check tokens are rejected
        """
        self.skip_paths = skip_paths or ["/health", "/docs", "/redoc", "/openapi.json"]
        self.required = required
        self.appcheck_service = get_appcheck_service()

    async def __call__(self, request: Request, call_next):
        """Process the request with App Check verification"""

        # Skip verification for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # Get App Check token from header
        appcheck_token = request.headers.get("X-Firebase-AppCheck")

        if not appcheck_token:
            if self.required:
                logger.warning(f"Missing App Check token for {request.url.path}")
                raise HTTPException(
                    status_code=401,
                    detail="App Check token required",
                    headers={"WWW-Authenticate": "X-Firebase-AppCheck"},
                )
            else:
                logger.info(f"App Check token missing but not required for {request.url.path}")
                request.state.appcheck_verified = False
                return await call_next(request)

        # Verify the token
        try:
            verification_result = self.appcheck_service.verify_token(appcheck_token)

            if verification_result and verification_result.get("valid"):
                # Token is valid
                request.state.appcheck_verified = True
                request.state.appcheck_claims = verification_result
                logger.debug(f"App Check verified for app: {verification_result.get('app_id')}")
                return await call_next(request)
            else:
                # Token is invalid
                request.state.appcheck_verified = False
                error_msg = (
                    verification_result.get("error", "Invalid App Check token")
                    if verification_result
                    else "Invalid App Check token"
                )

                if self.required:
                    logger.warning(f"Invalid App Check token for {request.url.path}: {error_msg}")
                    raise HTTPException(
                        status_code=401,
                        detail=f"Invalid App Check token: {error_msg}",
                        headers={"WWW-Authenticate": "X-Firebase-AppCheck"},
                    )
                else:
                    logger.info(f"Invalid App Check token but not required for {request.url.path}")
                    return await call_next(request)

        except AppCheckError as e:
            logger.error(f"App Check service error: {str(e)}")
            if self.required:
                raise HTTPException(
                    status_code=503, detail="App Check verification service unavailable"
                )
            else:
                request.state.appcheck_verified = False
                return await call_next(request)
        except Exception as e:
            logger.error(f"Unexpected error in App Check middleware: {str(e)}")
            if self.required:
                raise HTTPException(
                    status_code=500, detail="Internal server error during App Check verification"
                )
            else:
                request.state.appcheck_verified = False
                return await call_next(request)


# Security scheme for OpenAPI documentation
appcheck_scheme = HTTPBearer(
    scheme_name="X-Firebase-AppCheck", description="Firebase App Check token"
)


async def verify_appcheck_token(request: Request) -> dict:
    """
    FastAPI dependency to verify App Check token

    Args:
        request: FastAPI request object

    Returns:
        App Check claims if verification successful

    Raises:
        HTTPException: If token is missing or invalid
    """
    appcheck_token = request.headers.get("X-Firebase-AppCheck")

    if not appcheck_token:
        raise HTTPException(
            status_code=401,
            detail="App Check token required",
            headers={"WWW-Authenticate": "X-Firebase-AppCheck"},
        )

    try:
        appcheck_service = get_appcheck_service()
        verification_result = appcheck_service.verify_token(appcheck_token)

        if verification_result and verification_result.get("valid"):
            return verification_result
        else:
            error_msg = (
                verification_result.get("error", "Invalid App Check token")
                if verification_result
                else "Invalid App Check token"
            )
            raise HTTPException(
                status_code=401,
                detail=f"Invalid App Check token: {error_msg}",
                headers={"WWW-Authenticate": "X-Firebase-AppCheck"},
            )

    except AppCheckError as e:
        logger.error(f"App Check service error: {str(e)}")
        raise HTTPException(status_code=503, detail="App Check verification service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during App Check verification: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during App Check verification"
        )


async def optional_appcheck_token(request: Request) -> Optional[dict]:
    """
    Optional FastAPI dependency to verify App Check token
    Returns None if token is missing or invalid, doesn't raise exceptions

    Args:
        request: FastAPI request object

    Returns:
        App Check claims if verification successful, None otherwise
    """
    appcheck_token = request.headers.get("X-Firebase-AppCheck")

    if not appcheck_token:
        return None

    try:
        appcheck_service = get_appcheck_service()
        verification_result = appcheck_service.verify_token(appcheck_token)

        if verification_result and verification_result.get("valid"):
            return verification_result
        else:
            return None

    except Exception as e:
        logger.warning(f"App Check verification failed: {str(e)}")
        return None


def require_appcheck(func: Callable) -> Callable:
    """
    Decorator to require App Check verification for a function

    Args:
        func: Function to decorate

    Returns:
        Decorated function that requires App Check verification
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Find the request object in the arguments
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if not request:
            raise RuntimeError("Request object not found in function arguments")

        # Verify App Check token
        await verify_appcheck_token(request)

        # Call the original function
        return await func(*args, **kwargs)

    return wrapper


def get_appcheck_claims(request: Request) -> Optional[dict]:
    """
    Get App Check claims from request state (if available)

    Args:
        request: FastAPI request object

    Returns:
        App Check claims if available, None otherwise
    """
    return getattr(request.state, "appcheck_claims", None)


def is_appcheck_verified(request: Request) -> bool:
    """
    Check if request has been verified with App Check

    Args:
        request: FastAPI request object

    Returns:
        True if App Check verification passed, False otherwise
    """
    return getattr(request.state, "appcheck_verified", False)
