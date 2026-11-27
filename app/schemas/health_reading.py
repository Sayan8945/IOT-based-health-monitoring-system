"""Pydantic schemas for ESP32 telemetry ingestion and WebSocket payloads."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SensorStatusIn(BaseModel):
    """Per-sensor connectivity flags reported by ESP32 hardware."""

    pulse_oximeter: bool = True
    temp_probe: bool = True
    ecg: bool = True


class HealthReadingIn(BaseModel):
    """Incoming telemetry batch sent by ESP32 over HTTP POST."""

    device_id: str = Field(
        default="ESP32_001",
        min_length=1,
        max_length=64,
        description="Unique hardware node identifier",
    )
    heart_rate: float = Field(..., ge=20.0, le=250.0, description="Heart rate in BPM")
    spo2: float = Field(..., ge=50.0, le=100.0, description="Oxygen saturation percentage")
    temperature: float = Field(..., ge=30.0, le=45.0, description="Body temperature in Celsius")
    ecg_samples: List[float] = Field(
        default_factory=list,
        description="Batched 100 Hz Lead-I ECG samples (raw ADC counts or mV floats)",
    )
    leads_off: Optional[bool] = Field(
        default=None,
        description="Hardware AD8232 LO+/LO- flag (true when electrodes are disconnected)",
    )
    leads_connected: Optional[bool] = Field(
        default=None,
        description="Explicit electrode connectivity flag (takes precedence over leads_off)",
    )
    sensors: Optional[SensorStatusIn] = Field(
        default=None,
        description="Optional per-module hardware connectivity states",
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="Optional ISO-8601 timestamp from device",
    )

    @property
    def resolved_leads_connected(self) -> bool:
        """Resolve electrode connection state from either leads_connected or leads_off."""
        if self.leads_connected is not None:
            return self.leads_connected
        if self.leads_off is not None:
            return not self.leads_off
        return True

    @property
    def resolved_sensors(self) -> SensorStatusIn:
        """Return explicit sensor flags or default all modules to connected."""
        if self.sensors is not None:
            return self.sensors
        return SensorStatusIn()


class ReadingIngestResponse(BaseModel):
    """HTTP response returned to the ESP32 after telemetry ingestion and broadcast."""

    status: str = "success"
    device_id: str
    timestamp: str
    clients_notified: int
    persisted: bool = False
    anomaly_score: float
    is_anomaly: bool
    alerts: List[Dict[str, str]] = Field(default_factory=list)
