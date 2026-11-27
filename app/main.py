"""FastAPI Application Entrypoint for IoT Health Monitoring Telemetry Server."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.devices import router as devices_router
from app.api.readings import router as readings_router
from app.database.connection import get_db_manager
from app.services.reading_service import ReadingService
from app.websocket.manager import get_ws_manager

logger = logging.getLogger(__name__)

try:
    from app.api.predictions import router as predictions_router
    from app.services.prediction_service import PredictionService
except ImportError as exc:
    predictions_router = None
    PredictionService = None
    logger.warning("ML predictions router disabled (missing dependencies): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MongoDB, ML artifacts, reading state, and WebSocket manager."""
    db_manager = get_db_manager()
    await db_manager.connect()
    if PredictionService is not None:
        PredictionService.get_instance()
    ReadingService.get_instance()
    get_ws_manager()
    try:
        yield
    finally:
        await db_manager.disconnect()


app = FastAPI(
    title="SmartHealth IoT Telemetry Server",
    description="Real-time IoT telemetry ingestion, clinical threshold evaluation, and ML anomaly inference.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for React dashboard communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
if predictions_router is not None:
    app.include_router(predictions_router)
app.include_router(readings_router)
app.include_router(devices_router)


@app.get("/", tags=["Health Check"])
async def root():
    """Server status health check."""
    db_connected = get_db_manager().is_connected
    return {
        "status": "healthy",
        "service": "SmartHealth IoT Telemetry & ML Ingestion Server",
        "version": "1.0.0",
        "database": "connected" if db_connected else "in-memory",
    }
