import os
from typing import Dict, Any, Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Optional Firebase imports - only used if ENABLE_AUTH=true
try:
    import firebase_admin
    from firebase_admin import auth, credentials
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

security = HTTPBearer(auto_error=False)


def initialize_firebase():
    if FIREBASE_AVAILABLE and not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)


async def verify_firebase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    # Check if auth is enabled
    enable_auth = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    
    if not enable_auth:
        # Return mock user for development
        return {
            "uid": "dev-user-123",
            "email": "dev@example.com",
            "email_verified": True
        }
    
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Firebase not available. Install firebase-admin or set ENABLE_AUTH=false"
        )
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required when ENABLE_AUTH=true"
        )
    
    try:
        initialize_firebase()
        
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False)
        }
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication token: {str(e)}"
        )


async def get_current_user(user_data: Dict[str, Any] = Depends(verify_firebase_token)) -> Dict[str, Any]:
    return user_data