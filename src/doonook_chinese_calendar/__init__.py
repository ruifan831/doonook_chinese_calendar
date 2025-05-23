from fastapi import APIRouter
from .api.endpoints import router as calendar_router
from .api.astro_endpoints import router as astro_router
from .core.config import CalendarSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def create_calendar_router(
    settings: Optional[CalendarSettings] = None,
    prefix: str = "/api/v1/calendar",
) -> APIRouter:
    """
    Creates and configures the main calendar router
    
    Args:
        settings: Calendar settings configuration
        prefix: API route prefix
    """
    if settings is None:
        settings = CalendarSettings()
    
    router = APIRouter(prefix=prefix)
    router.include_router(calendar_router)
    router.include_router(astro_router)
    
    return router
