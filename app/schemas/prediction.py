"""Pydantic schemas for Machine Learning predictions and telemetry evaluation.

Adheres strictly to the frontend React contract required by MLAnalysisCard.jsx.
"""

from __future__ import annotations

from typing import Dict, Literal
from pydantic import BaseModel, Field


class TrendMetric(BaseModel):
    """Trend direction and slope description for a physiological variable."""

    direction: str = Field(..., description="e.g. 'Stable', 'Increasing', 'Declining'")
    slope: str = Field(..., description="e.g. '+0.1 bpm/min', '-0.2 %/min'")


class TrendsSummary(BaseModel):
    """Composite trend projections across the three core physiological vital signs."""

    heartRate: TrendMetric
    spo2: TrendMetric
    temperature: TrendMetric


class ECGPatternAnalysis(BaseModel):
    """Rhythm classification and interval metrics derived from 100 Hz Lead-I ECG."""

    classification: str = Field(..., description="e.g. 'Normal Sinus Rhythm', 'Sinus Tachycardia'")
    rrInterval: int = Field(..., description="Mean R-R interval in milliseconds")
    rrVariance: int = Field(..., description="Variance of R-R intervals across window")


class FeatureVector(BaseModel):
    """Aggregated numerical feature values extracted across the sliding window."""

    meanHr: float = Field(..., description="Mean heart rate (bpm)")
    stdHr: float = Field(..., description="Standard deviation of heart rate")
    meanSpo2: float = Field(..., description="Mean SpO2 percentage")
    meanTemp: float = Field(..., description="Mean body temperature (°C)")
    deltaTemp: float = Field(..., description="Temperature change over window (°C)")
    rmsEcg: float = Field(..., description="Root-Mean-Square ECG amplitude (uV)")


class PredictionResponse(BaseModel):
    """Full telemetry analysis payload returned by the FastAPI ML inference service."""

    status: Literal["Normal", "Borderline", "Elevated"] = Field(
        default="Normal", description="Clinical risk category"
    )
    isAnomaly: bool = Field(default=False, description="True if anomalyScore >= threshold")
    anomalyScore: float = Field(
        default=0.08, ge=0.0, le=1.0, description="Normalized Isolation Forest anomaly score [0.00 - 1.00]"
    )
    threshold: float = Field(default=0.65, description="Anomaly decision threshold")
    riskLevel: Literal["Nominal", "Borderline", "Elevated"] = Field(
        default="Nominal", description="Risk level descriptor"
    )
    trends: TrendsSummary
    ecgPattern: ECGPatternAnalysis
    features: FeatureVector
    inferenceLatencyMs: float = Field(
        default=3.5, description="Model inference latency in milliseconds"
    )
