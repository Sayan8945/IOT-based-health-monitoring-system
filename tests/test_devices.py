"""Unit and Integration Tests for Devices API and MongoDB Persistence."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from app.api.devices import clear_memory_devices
from app.database.collections import (
    ALERTS_COLLECTION,
    DEVICES_COLLECTION,
    VITALS_COLLECTION,
    ensure_indexes,
)
from app.database.connection import get_db_manager
from app.main import app
from app.services.reading_service import ReadingService


class _FakeAsyncCursor:
    """Minimal async cursor supporting sort(), limit(), and to_list()."""

    def __init__(self, docs: List[Dict[str, Any]]) -> None:
        self._docs = list(docs)

    def sort(self, key: str, direction: int) -> "_FakeAsyncCursor":
        reverse = direction < 0
        self._docs.sort(key=lambda d: str(d.get(key, "")), reverse=reverse)
        return self

    def limit(self, count: int) -> "_FakeAsyncCursor":
        self._docs = self._docs[:count]
        return self

    async def to_list(self, length: int = 100) -> List[Dict[str, Any]]:
        return self._docs[:length]


class _FakeAsyncCollection:
    """In-memory async collection emulating PyMongo AsyncCollection operations."""

    def __init__(self) -> None:
        self.docs: List[Dict[str, Any]] = []
        self.indexes: List[Dict[str, Any]] = []

    async def create_index(self, keys: Any, **kwargs: Any) -> str:
        name = kwargs.get("name", "idx")
        self.indexes.append({"keys": keys, **kwargs})
        return name

    async def insert_one(self, doc: Dict[str, Any]) -> None:
        stored = dict(doc)
        stored.setdefault("_id", f"oid-{len(self.docs) + 1}")
        self.docs.append(stored)

    async def insert_many(self, docs: List[Dict[str, Any]]) -> None:
        for doc in docs:
            await self.insert_one(doc)

    @staticmethod
    def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(
        self, query: Dict[str, Any], sort: List[tuple] | None = None
    ) -> Dict[str, Any] | None:
        matches = [d for d in self.docs if self._matches(d, query)]
        if not matches:
            return None
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda d: str(d.get(key, "")), reverse=(direction < 0))
        return dict(matches[0])

    def find(self, query: Dict[str, Any]) -> _FakeAsyncCursor:
        matches = [dict(d) for d in self.docs if self._matches(d, query)]
        return _FakeAsyncCursor(matches)

    async def update_one(
        self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False
    ) -> None:
        target = next((d for d in self.docs if self._matches(d, query)), None)
        if target is None:
            if not upsert:
                return
            target = {"_id": f"oid-{len(self.docs) + 1}", **query}
            for k, v in update.get("$setOnInsert", {}).items():
                target.setdefault(k, v)
            self.docs.append(target)
        for k, v in update.get("$set", {}).items():
            target[k] = v


class _FakeAsyncDatabase:
    """In-memory async MongoDB database stub."""

    def __init__(self) -> None:
        self._collections: Dict[str, _FakeAsyncCollection] = {
            VITALS_COLLECTION: _FakeAsyncCollection(),
            DEVICES_COLLECTION: _FakeAsyncCollection(),
            ALERTS_COLLECTION: _FakeAsyncCollection(),
        }

    def __getitem__(self, name: str) -> _FakeAsyncCollection:
        if name not in self._collections:
            self._collections[name] = _FakeAsyncCollection()
        return self._collections[name]


@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory caches and detach mock database after each test."""
    clear_memory_devices()
    ReadingService.get_instance().clear_history()
    get_db_manager().attach_database(None)
    yield
    clear_memory_devices()
    ReadingService.get_instance().clear_history()
    get_db_manager().attach_database(None)


@pytest.fixture
def client():
    """Create FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


def test_device_register_list_and_lookup_in_memory(client):
    """Devices endpoints work cleanly in in-memory mode when MONGODB_URI is unset."""
    res = client.post(
        "/api/devices/register",
        json={
            "device_id": "ESP32_001",
            "patient_name": "Patient A",
            "location": "Ward 2",
            "firmware_version": "1.0.0",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["device_id"] == "ESP32_001"
    assert data["patient_name"] == "Patient A"
    assert data["status"] == "registered"

    listing = client.get("/api/devices").json()
    assert len(listing) == 1
    assert listing[0]["device_id"] == "ESP32_001"

    single = client.get("/api/devices/ESP32_001")
    assert single.status_code == 200
    assert single.json()["location"] == "Ward 2"

    missing = client.get("/api/devices/UNKNOWN")
    assert missing.status_code == 404


def test_mongodb_persistence_and_queries_with_fake_db(client):
    """When MongoDB is attached, readings, alerts, and devices persist and query cleanly."""
    fake_db = _FakeAsyncDatabase()
    get_db_manager().attach_database(fake_db)

    root_res = client.get("/").json()
    assert root_res["database"] == "connected"

    reg = client.post(
        "/api/devices/register",
        json={"device_id": "ESP32_DB_01", "patient_name": "Ward Test"},
    )
    assert reg.status_code == 200
    assert len(fake_db[DEVICES_COLLECTION].docs) == 1

    ingest = client.post(
        "/api/readings",
        json={
            "device_id": "ESP32_DB_01",
            "heart_rate": 122.0,
            "spo2": 89.0,
            "temperature": 38.2,
            "leads_off": False,
            "ecg_samples": [512, 530, 740, 520] * 5,
        },
    )
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["persisted"] is True
    assert len(fake_db[VITALS_COLLECTION].docs) == 1
    assert len(fake_db[ALERTS_COLLECTION].docs) >= 3

    latest = client.get("/api/readings/latest?device_id=ESP32_DB_01").json()
    assert latest["device_id"] == "ESP32_DB_01"
    assert latest["heart_rate"] == 122.0

    history = client.get("/api/readings/history?device_id=ESP32_DB_01&limit=5").json()
    assert history["count"] == 1

    alerts = client.get("/api/alerts?device_id=ESP32_DB_01").json()
    assert alerts["count"] >= 3


def test_ensure_indexes_creates_compound_and_ttl_indexes():
    """ensure_indexes configures compound device+time and 30-day TTL indexes."""
    fake_db = _FakeAsyncDatabase()
    asyncio.run(ensure_indexes(fake_db, ttl_days=30))

    vitals_idx = fake_db[VITALS_COLLECTION].indexes
    assert any(idx.get("expireAfterSeconds") == 30 * 86400 for idx in vitals_idx)
    assert any(idx["keys"] == [("device_id", 1), ("created_at", -1)] for idx in vitals_idx)

    devices_idx = fake_db[DEVICES_COLLECTION].indexes
    assert any(idx.get("unique") is True for idx in devices_idx)
