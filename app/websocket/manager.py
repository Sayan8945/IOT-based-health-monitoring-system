"""Async WebSocket connection manager for live clinical dashboard streaming."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Thread- and task-safe registry of connected WebSocket dashboard clients."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        """Number of currently tracked WebSocket connections."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WebSocket client connected (active=%d)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket client if present."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WebSocket client disconnected (active=%d)", len(self._connections))

    async def send_personal_json(
        self, websocket: WebSocket, payload: Dict[str, Any]
    ) -> bool:
        """Send a JSON payload to a single client, disconnecting on failure."""
        try:
            await websocket.send_json(payload)
            return True
        except Exception as exc:
            logger.debug("Personal WebSocket send failed: %s", exc)
            await self.disconnect(websocket)
            return False

    async def broadcast_json(self, payload: Dict[str, Any]) -> int:
        """Broadcast a JSON payload to all active clients, pruning dead sockets."""
        async with self._lock:
            targets = list(self._connections)

        if not targets:
            return 0

        results = await asyncio.gather(
            *(ws.send_json(payload) for ws in targets),
            return_exceptions=True,
        )

        failed: list[WebSocket] = []
        sent_count = 0
        for ws, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.debug("Pruning disconnected WebSocket client: %s", result)
                failed.append(ws)
            else:
                sent_count += 1

        if failed:
            async with self._lock:
                for ws in failed:
                    self._connections.discard(ws)

        return sent_count


_ws_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    """Return the process-wide ConnectionManager singleton."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = ConnectionManager()
    return _ws_manager
