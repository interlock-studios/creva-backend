"""
Firebase App Check Service for token verification
"""

import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import firebase_admin
from firebase_admin import credentials, app_check
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger(__name__)


class AppCheckError(Exception):
    """Custom exception for App Check errors"""
    pass


class AppCheckService:
    """Service for verifying Firebase App Check tokens"""
    
    def __init__(self):
        self._app = None
        self._initialized = False
        self._token_cache = {}  # Simple in-memory cache for verified tokens
        self._cache_ttl = timedelta(minutes=5)  # Cache tokens for 5 minutes
        self._init_firebase()
    
    def _init_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase app is already initialized
            if not firebase_admin._apps:
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
                if not project_id:
                    raise AppCheckError("GOOGLE_CLOUD_PROJECT_ID environment variable is required")
                
                # Prioritize Application Default Credentials (works on Cloud Run)
                # This avoids the need for service account keys
                service_account_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
                
                if service_account_key and service_account_key.lower() not in ['none', 'false', '']:
                    # Only use service account key if explicitly provided and not disabled
                    try:
                        # If it's a file path
                        if os.path.isfile(service_account_key):
                            cred = credentials.Certificate(service_account_key)
                            logger.info("Using Firebase service account key from file")
                        else:
                            # If it's JSON content as string
                            import json
                            key_dict = json.loads(service_account_key)
                            cred = credentials.Certificate(key_dict)
                            logger.info("Using Firebase service account key from environment")
                    except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
                        logger.warning(f"Failed to load service account key: {e}, falling back to Application Default Credentials")
                        cred = credentials.ApplicationDefault()
                else:
                    # Use Application Default Credentials (recommended for Cloud Run)
                    # This automatically uses the service account assigned to the Cloud Run service
                    cred = credentials.ApplicationDefault()
                    logger.info("Using Application Default Credentials for Firebase")
                
                self._app = firebase_admin.initialize_app(cred, {
                    'projectId': project_id
                })
            else:
                self._app = firebase_admin.get_app()
            
            self._initialized = True
            logger.info("Firebase Admin SDK initialized successfully for App Check")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
            self._initialized = False
            # Don't raise here - allow the service to start but log the error
    
    def _clean_token_cache(self):
        """Remove expired tokens from cache"""
        current_time = datetime.now()
        expired_keys = [
            token for token, (_, timestamp) in self._token_cache.items()
            if current_time - timestamp > self._cache_ttl
        ]
        for key in expired_keys:
            del self._token_cache[key]
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Firebase App Check token
        
        Args:
            token: App Check token to verify
            
        Returns:
            Dict containing verification result or None if invalid
            
        Raises:
            AppCheckError: If verification fails due to service issues
        """
        if not self._initialized:
            raise AppCheckError("Firebase Admin SDK not initialized")
        
        if not token:
            return None
        
        # Clean expired tokens from cache
        self._clean_token_cache()
        
        # Check cache first
        if token in self._token_cache:
            cached_result, timestamp = self._token_cache[token]
            if datetime.now() - timestamp < self._cache_ttl:
                logger.debug("App Check token found in cache")
                return cached_result
            else:
                # Remove expired token
                del self._token_cache[token]
        
        try:
            # Verify the App Check token
            app_check_claims = app_check.verify_token(token, app=self._app)
            
            # Extract relevant information
            result = {
                "valid": True,
                "app_id": app_check_claims.get("firebase", {}).get("app_id"),
                "iss": app_check_claims.get("iss"),
                "aud": app_check_claims.get("aud"),
                "exp": app_check_claims.get("exp"),
                "iat": app_check_claims.get("iat"),
                "sub": app_check_claims.get("sub"),
                "verified_at": datetime.now().isoformat()
            }
            
            # Cache the result
            self._token_cache[token] = (result, datetime.now())
            
            logger.info(f"App Check token verified successfully for app: {result['app_id']}")
            return result
            
        except FirebaseError as e:
            error_code = getattr(e, 'code', 'unknown')
            logger.warning(f"App Check token verification failed: {error_code} - {str(e)}")
            
            # Cache invalid result for a short time to prevent repeated verification attempts
            invalid_result = {
                "valid": False,
                "error": str(e),
                "error_code": error_code,
                "verified_at": datetime.now().isoformat()
            }
            self._token_cache[token] = (invalid_result, datetime.now())
            
            return invalid_result
            
        except Exception as e:
            logger.error(f"Unexpected error during App Check verification: {str(e)}")
            raise AppCheckError(f"App Check verification failed: {str(e)}")
    
    def is_healthy(self) -> bool:
        """Check if the App Check service is healthy"""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "initialized": self._initialized,
            "cached_tokens": len(self._token_cache),
            "cache_ttl_minutes": self._cache_ttl.total_seconds() / 60
        }
