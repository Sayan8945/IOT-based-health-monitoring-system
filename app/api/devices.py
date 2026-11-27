"""FastAPI endpoints for ESP32 device registration and status lookup."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import verify_device_token
from app.database.collections import get_devices_collection
from app.database.connection import DatabaseManager, get_db_manager
from app.models.device import build_device_document
from app.models.health_reading import serialize_mongo_doc
from app.schemas.device import DeviceOut, DeviceRegisterIn

router = APIRouter(prefix="/api/devices", tags=["Devices"])

_memory_devices: Dict[str, Dict[str, Any]] = {}


def clear_memory_devices() -> None:
    """Clear in-memory device registry (primarily for isolated tests)."""
    _memory_devices.clear()


@router.post(
    "/register",
    response_model=DeviceOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_device_token)],
    summary="Register or update an ESP32 hardware node",
)
async def register_device(
    payload: DeviceRegisterIn,
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> DeviceOut:
    """Register a device in MongoDB (or in-memory fallback when DB is disconnected)."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    doc = build_device_document(
        device_id=payload.device_id,
        patient_name=payload.patient_name,
        patient_id=payload.patient_id,
        location=payload.location,
        firmware_version=payload.firmware_version,
        metadata=payload.metadata,
        now=now,
    )

    db = db_manager.database
    if db is not None:
        col = get_devices_collection(db)
        await col.update_one(
            {"device_id": payload.device_id},
            {
                "$set": {
                    "patient_name": payload.patient_name,
                    "patient_id": payload.patient_id,
                    "location": payload.location,
                    "firmware_version": payload.firmware_version,
                    "metadata": payload.metadata,
                    "status": "registered",
                    "last_seen": now_iso,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "device_id": payload.device_id,
                    "registered_at": now_iso,
                },
            },
            upsert=True,
        )
        stored = await col.find_one({"device_id": payload.device_id})
        if stored is not None:
            return DeviceOut(**serialize_mongo_doc(stored))

    existing = _memory_devices.get(payload.device_id)
    if existing is not None:
        doc["registered_at"] = existing["registered_at"]
    _memory_devices[payload.device_id] = doc
    return DeviceOut(**serialize_mongo_doc(doc))


@router.get(
    "",
    response_model=List[DeviceOut],
    summary="List registered ESP32 devices",
)
async def list_devices(
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> List[DeviceOut]:
    """List all registered devices from MongoDB or in-memory registry."""
    db = db_manager.database
    if db is not None:
        cursor = get_devices_collection(db).find({}).sort("last_seen", -1)
        docs = await cursor.to_list(length=200)
        return [DeviceOut(**serialize_mongo_doc(doc)) for doc in docs]

    return [DeviceOut(**serialize_mongo_doc(doc)) for doc in _memory_devices.values()]


@router.get(
    "/{device_id}",
    response_model=DeviceOut,
    summary="Get device details by ID",
)
async def get_device(
    device_id: str,
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> DeviceOut:
    """Fetch a single device record by device_id."""
    db = db_manager.database
    if db is not None:
        doc = await get_devices_collection(db).find_one({"device_id": device_id})
        if doc is not None:
            return DeviceOut(**serialize_mongo_doc(doc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )

    doc = _memory_devices.get(device_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )
    return DeviceOut(**serialize_mongo_doc(doc))
