"""
API module for route organization
"""

from .health import router as health_router
from .process import router as process_router
from .admin import router as admin_router

__all__ = ["health_router", "process_router", "admin_router"]
