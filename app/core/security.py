"""Authentication helpers for ESP32 device ingestion and WebSocket clients."""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_device_token(
    x_device_token: Optional[str] = Header(default=None, alias="X-Device-Token"),
) -> None:
    """Validate optional shared device token for ESP32 ingestion requests.

    When ``DEVICE_AUTH_TOKEN`` is unset/empty, local development requests pass without a header.
    """
    expected = get_settings().device_auth_token
    if not expected:
        return

    if not x_device_token or not secrets.compare_digest(x_device_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Device-Token header",
        )


def verify_ws_token(token: Optional[str]) -> bool:
    """Validate optional WebSocket query token when ``WS_AUTH_TOKEN`` is configured."""
    expected = get_settings().ws_auth_token
    if not expected:
        return True
    return bool(token and secrets.compare_digest(token, expected))
