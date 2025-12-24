"""
API module for route organization
"""

from .health import router as health_router
from .process import router as process_router
from .admin import router as admin_router
from .script import router as script_router
from .templatize import router as templatize_router
from .script_from_scratch import router as script_from_scratch_router

__all__ = [
    "health_router",
    "process_router",
    "admin_router",
    "script_router",
    "templatize_router",
    "script_from_scratch_router",
]
