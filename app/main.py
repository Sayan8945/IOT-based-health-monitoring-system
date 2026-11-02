"""FastAPI Application Entrypoint for IoT Health Monitoring Telemetry Server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.predictions import router as predictions_router
from app.services.prediction_service import PredictionService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload machine learning model and scaler artifacts into RAM on startup."""
    PredictionService.get_instance()
    yield


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
app.include_router(predictions_router)


@app.get("/", tags=["Health Check"])
async def root():
    """Server status health check."""
    return {
        "status": "healthy",
        "service": "SmartHealth IoT Telemetry & ML Ingestion Server",
        "version": "1.0.0",
    }
