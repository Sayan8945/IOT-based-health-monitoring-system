"""FastAPI REST ingestion and WebSocket streaming endpoints for ESP32 telemetry."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import verify_device_token, verify_ws_token
from app.schemas.health_reading import HealthReadingIn, ReadingIngestResponse
from app.services.reading_service import ReadingService
from app.websocket.manager import ConnectionManager, get_ws_manager

router = APIRouter(tags=["Telemetry & WebSockets"])


def get_reading_service() -> ReadingService:
    """Dependency provider for singleton ReadingService."""
    return ReadingService.get_instance()


@router.post(
    "/api/readings",
    response_model=ReadingIngestResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_device_token)],
    summary="Ingest live ESP32 sensor batch",
    description=(
        "Validates incoming ESP32 physiological telemetry, runs in-memory ML anomaly "
        "inference and alert checks, broadcasts over WebSockets, and persists to MongoDB."
    ),
)
async def ingest_reading(
    reading: HealthReadingIn,
    service: ReadingService = Depends(get_reading_service),
) -> ReadingIngestResponse:
    """Receive an ESP32 telemetry batch and broadcast to active WebSocket clients."""
    return await service.ingest_and_broadcast(reading)


@router.get(
    "/api/readings/latest",
    summary="Get latest ingested telemetry reading",
    description="Returns the most recent ESP32 telemetry snapshot from MongoDB or memory.",
)
async def get_latest_reading(
    device_id: Optional[str] = Query(default=None, description="Optional filter by device ID"),
    service: ReadingService = Depends(get_reading_service),
) -> Dict[str, Any]:
    """Retrieve the latest ingested telemetry payload."""
    latest = await service.fetch_latest(device_id=device_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No telemetry readings received yet",
        )
    return latest


@router.get(
    "/api/readings/history",
    summary="Get recent telemetry readings history",
    description="Returns recent telemetry snapshots in reverse-chronological order.",
)
async def get_reading_history(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of records to return"),
    device_id: Optional[str] = Query(default=None, description="Optional filter by device ID"),
    service: ReadingService = Depends(get_reading_service),
) -> Dict[str, Any]:
    """Retrieve recent telemetry snapshots from MongoDB or in-memory cache."""
    records = await service.fetch_history(limit=limit, device_id=device_id)
    return {
        "count": len(records),
        "readings": records,
    }


@router.get(
    "/api/alerts",
    summary="Get recent clinical and ML alerts",
    description="Returns recent alerts persisted in MongoDB or buffered in memory.",
)
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of alerts to return"),
    device_id: Optional[str] = Query(default=None, description="Optional filter by device ID"),
    service: ReadingService = Depends(get_reading_service),
) -> Dict[str, Any]:
    """Retrieve recent clinical threshold and ML anomaly alerts."""
    alerts = await service.fetch_alerts(limit=limit, device_id=device_id)
    return {
        "count": len(alerts),
        "alerts": alerts,
    }


async def _handle_telemetry_websocket(
    websocket: WebSocket,
    token: Optional[str],
    reading_service: ReadingService,
    ws_manager: ConnectionManager,
) -> None:
    """Shared handler for dashboard WebSocket streams (/ws/health and /ws/live)."""
    if not verify_ws_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(websocket)
    try:
        latest = reading_service.latest_payload
        if latest is not None:
            sent = await ws_manager.send_personal_json(websocket, latest)
            if not sent:
                return

        while True:
            raw_message = await websocket.receive_text()
            stripped = raw_message.strip()
            if stripped.lower() == "ping":
                await ws_manager.send_personal_json(websocket, {"type": "pong"})
                continue
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and parsed.get("type") == "ping":
                    await ws_manager.send_personal_json(websocket, {"type": "pong"})
            except ValueError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)


@router.websocket("/ws/health")
async def websocket_health_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
) -> None:
    """Primary real-time WebSocket stream consumed by the React dashboard (useTelemetry.js)."""
    await _handle_telemetry_websocket(
        websocket=websocket,
        token=token,
        reading_service=ReadingService.get_instance(),
        ws_manager=get_ws_manager(),
    )


@router.websocket("/ws/live")
async def websocket_live_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
) -> None:
    """Alias WebSocket stream endpoint for compatibility with AGENTS.md specification."""
    await _handle_telemetry_websocket(
        websocket=websocket,
        token=token,
        reading_service=ReadingService.get_instance(),
        ws_manager=get_ws_manager(),
    )
