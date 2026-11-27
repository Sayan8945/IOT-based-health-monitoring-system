"""Async MongoDB Atlas connection manager using PyMongo AsyncMongoClient."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import get_settings
from app.database.collections import ensure_indexes

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages the async MongoDB client lifecycle with graceful in-memory fallback."""

    _instance: Optional["DatabaseManager"] = None

    def __init__(self) -> None:
        self._client: Any = None
        self._db: Any = None
        self._connected: bool = False

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """Return the process-wide DatabaseManager singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_connected(self) -> bool:
        """True when a live MongoDB database handle is active."""
        return self._connected and self._db is not None

    @property
    def database(self) -> Any:
        """Return the active MongoDB database handle or None when disconnected."""
        return self._db if self._connected else None

    def attach_database(self, db: Any) -> None:
        """Attach an external/mock database handle (primarily for unit tests)."""
        self._db = db
        self._connected = db is not None

    async def connect(self) -> bool:
        """Connect to MongoDB Atlas if MONGODB_URI is configured, else run in-memory."""
        settings = get_settings()
        if not settings.mongodb_uri:
            logger.info("MONGODB_URI not set; running telemetry in in-memory mode.")
            self._connected = False
            self._db = None
            return False

        try:
            from pymongo import AsyncMongoClient
        except ImportError as exc:
            logger.warning(
                "pymongo is not installed (%s); running in-memory without MongoDB persistence.",
                exc,
            )
            self._connected = False
            self._db = None
            return False

        try:
            client = AsyncMongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
                connectTimeoutMS=settings.mongodb_timeout_ms,
            )
            await client.admin.command("ping")
            db = client[settings.mongodb_db_name]
            await ensure_indexes(db, ttl_days=settings.mongodb_ttl_days)

            self._client = client
            self._db = db
            self._connected = True
            logger.info("Connected to MongoDB database '%s'", settings.mongodb_db_name)
            return True
        except Exception as exc:
            logger.warning(
                "MongoDB connection failed (%s); falling back to in-memory mode.", exc
            )
            await self.disconnect()
            return False

    async def ping(self) -> bool:
        """Verify active MongoDB connectivity."""
        if not self._connected or self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Close the MongoDB client cleanly on shutdown."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as exc:
                logger.debug("Ignoring MongoDB close error: %s", exc)
        self._client = None
        self._db = None
        self._connected = False


def get_db_manager() -> DatabaseManager:
    """Return the singleton DatabaseManager instance."""
    return DatabaseManager.get_instance()
