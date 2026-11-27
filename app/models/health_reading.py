"""MongoDB document builders and JSON serializers for health telemetry & alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def serialize_mongo_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a MongoDB document into a JSON-safe dictionary."""
    clean: Dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            clean["id"] = str(value)
        elif key == "created_at":
            continue
        elif isinstance(value, datetime):
            clean[key] = value.isoformat()
        else:
            clean[key] = value
    return clean


def build_vitals_document(
    ws_payload: Dict[str, Any],
    created_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a vitals_records MongoDB document from a normalized telemetry payload."""
    ts = created_at or datetime.now(timezone.utc)
    doc = dict(ws_payload)
    doc["ecg_lead_off"] = not bool(ws_payload.get("leads_connected", True))
    doc["created_at"] = ts
    return doc


def build_alert_documents(
    device_id: str,
    timestamp_iso: str,
    alerts: List[Dict[str, str]],
    created_at: datetime | None = None,
) -> List[Dict[str, Any]]:
    """Build MongoDB documents for the alerts collection."""
    ts = created_at or datetime.now(timezone.utc)
    return [
        {
            "device_id": device_id,
            "timestamp": timestamp_iso,
            "severity": alert.get("severity", "warning"),
            "category": alert.get("category", "Vitals"),
            "message": alert.get("message", ""),
            "created_at": ts,
        }
        for alert in alerts
    ]
