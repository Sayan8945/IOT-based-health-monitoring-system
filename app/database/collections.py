"""MongoDB collection definitions and index initialization."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

VITALS_COLLECTION = "vitals_records"
DEVICES_COLLECTION = "devices"
ALERTS_COLLECTION = "alerts"


def get_vitals_collection(db: Any) -> Any:
    """Return the time-series vitals_records collection."""
    return db[VITALS_COLLECTION]


def get_devices_collection(db: Any) -> Any:
    """Return the registered ESP32 devices collection."""
    return db[DEVICES_COLLECTION]


def get_alerts_collection(db: Any) -> Any:
    """Return the clinical/ML alerts collection."""
    return db[ALERTS_COLLECTION]


async def ensure_indexes(db: Any, ttl_days: int = 30) -> None:
    """Create compound query indexes and 30-day TTL indexes idempotently."""
    ttl_seconds = max(1, ttl_days) * 86400

    vitals = get_vitals_collection(db)
    await vitals.create_index([("device_id", 1), ("created_at", -1)], name="idx_device_created")
    await vitals.create_index(
        [("created_at", 1)],
        expireAfterSeconds=ttl_seconds,
        name="idx_vitals_ttl",
    )

    devices = get_devices_collection(db)
    await devices.create_index([("device_id", 1)], unique=True, name="idx_device_id_unique")

    alerts = get_alerts_collection(db)
    await alerts.create_index([("device_id", 1), ("created_at", -1)], name="idx_alerts_device_created")
    await alerts.create_index(
        [("created_at", 1)],
        expireAfterSeconds=ttl_seconds,
        name="idx_alerts_ttl",
    )
    logger.info("MongoDB indexes ensured (TTL=%d days)", ttl_days)
