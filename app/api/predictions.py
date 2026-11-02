"""FastAPI API endpoints for Machine Learning predictions and telemetry evaluation."""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.prediction import PredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/predictions", tags=["Predictions"])


class TelemetryEvaluationRequest(BaseModel):
    """Payload to evaluate physiological signals against the ML model."""

    heart_rate: float = Field(..., ge=20.0, le=250.0, description="Heart rate in bpm")
    spo2: float = Field(..., ge=50.0, le=100.0, description="Arterial blood oxygen percentage")
    temperature: float = Field(..., ge=30.0, le=45.0, description="Body temperature in Celsius")
    ecg_samples: Optional[List[float]] = Field(
        default=None, description="50-point 100 Hz ECG buffer"
    )
    leads_connected: bool = Field(default=True, description="True if AD8232 leads are connected")


def get_prediction_service() -> PredictionService:
    """Dependency provider for in-memory singleton prediction service."""
    return PredictionService.get_instance()


@router.get(
    "/latest",
    response_model=PredictionResponse,
    summary="Get latest ML telemetry prediction",
    description="Returns the most recent model inference, anomaly score, trend slopes, and rhythm classification.",
)
async def get_latest_prediction(
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionResponse:
    """Retrieve the latest telemetry evaluation from the rolling buffer."""
    if not service.buffer:
        # Default nominal prediction when buffer is not yet populated
        return service.predict(
            heart_rate=72.0,
            spo2=98.5,
            temperature=36.7,
            ecg_samples=[0.0] * 50,
            leads_connected=True,
        )
    latest = service.buffer[-1]
    return service.predict(
        heart_rate=latest["heart_rate"],
        spo2=latest["spo2"],
        temperature=latest["temperature"],
        ecg_samples=latest.get("ecg_samples", []),
        leads_connected=latest.get("leads_connected", True),
    )


@router.post(
    "/evaluate",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate custom telemetry packet",
    description="Feeds a single reading into the ML model, updates the sliding window, and returns the evaluation.",
)
async def evaluate_telemetry(
    request: TelemetryEvaluationRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionResponse:
    """Evaluate an ad-hoc or live ESP32 telemetry packet."""
    try:
        return service.predict(
            heart_rate=request.heart_rate,
            spo2=request.spo2,
            temperature=request.temperature,
            ecg_samples=request.ecg_samples,
            leads_connected=request.leads_connected,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference pipeline execution error: {str(e)}",
        )
