"""MongoDB database package exports."""

from app.database.collections import (
    ALERTS_COLLECTION,
    DEVICES_COLLECTION,
    VITALS_COLLECTION,
    ensure_indexes,
    get_alerts_collection,
    get_devices_collection,
    get_vitals_collection,
)
from app.database.connection import DatabaseManager, get_db_manager

__all__ = [
    "ALERTS_COLLECTION",
    "DEVICES_COLLECTION",
    "DatabaseManager",
    "VITALS_COLLECTION",
    "ensure_indexes",
    "get_alerts_collection",
    "get_db_manager",
    "get_devices_collection",
    "get_vitals_collection",
]
