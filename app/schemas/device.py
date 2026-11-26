"""Pydantic schemas for ESP32 device registration and lookup."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class DeviceRegisterIn(BaseModel):
    """Payload to register or update an ESP32 hardware node."""

    device_id: str = Field(..., min_length=1, max_length=64, description="Unique device identifier")
    patient_name: Optional[str] = Field(default=None, max_length=120)
    patient_id: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=120)
    firmware_version: Optional[str] = Field(default=None, max_length=32)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeviceOut(BaseModel):
    """Registered device status and metadata returned by the API."""

    device_id: str
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    location: Optional[str] = None
    firmware_version: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str = "registered"
    registered_at: str
    last_seen: str
