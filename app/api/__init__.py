"""FastAPI API router exports."""

from app.api.devices import router as devices_router
from app.api.readings import router as readings_router

__all__ = ["devices_router", "readings_router"]
