"""MongoDB document builder for ESP32 device registration records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def build_device_document(
    device_id: str,
    patient_name: str | None = None,
    patient_id: str | None = None,
    location: str | None = None,
    firmware_version: str | None = None,
    metadata: Dict[str, Any] | None = None,
    status: str = "registered",
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Construct a device document suitable for MongoDB upsert."""
    ts = now or datetime.now(timezone.utc)
    return {
        "device_id": device_id,
        "patient_name": patient_name,
        "patient_id": patient_id,
        "location": location,
        "firmware_version": firmware_version,
        "metadata": metadata or {},
        "status": status,
        "registered_at": ts.isoformat(),
        "last_seen": ts.isoformat(),
        "updated_at": ts,
    }
