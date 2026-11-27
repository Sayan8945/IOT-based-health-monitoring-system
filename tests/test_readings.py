"""Unit and Integration Tests for ESP32 Telemetry Ingestion and WebSocket Streaming."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.reading_service import ReadingService


@pytest.fixture(autouse=True)
def reset_reading_history():
    """Ensure each test starts with clean in-memory telemetry state."""
    service = ReadingService.get_instance()
    service.clear_history()
    yield
    service.clear_history()


@pytest.fixture
def client():
    """Create FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


def test_websocket_receives_live_reading_on_post(client):
    """POST /api/readings broadcasts exact useTelemetry.js contract over /ws/health."""
    payload = {
        "device_id": "ESP32_001",
        "heart_rate": 76.0,
        "spo2": 98.0,
        "temperature": 36.7,
        "leads_off": False,
        "ecg_samples": [0.02, 0.15, 0.72, -0.22, 0.18, 0.01] * 8,
    }

    with client.websocket_connect("/ws/health") as websocket:
        response = client.post("/api/readings", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["device_id"] == "ESP32_001"
        assert body["clients_notified"] == 1

        ws_msg = websocket.receive_json()
        assert ws_msg["device_id"] == "ESP32_001"
        assert ws_msg["heart_rate"] == 76.0
        assert ws_msg["spo2"] == 98.0
        assert ws_msg["temperature"] == 36.7
        assert ws_msg["leads_connected"] is True
        assert ws_msg["ecg_signal_quality"] == "Good"
        assert ws_msg["sensors"] == {
            "pulse_oximeter": True,
            "temp_probe": True,
            "ecg": True,
        }
        assert "anomaly_score" in ws_msg
        assert "anomaly" in ws_msg

        pred = ws_msg["prediction"]
        assert "anomaly_score" in pred
        assert "anomaly" in pred
        assert "trends" in pred
        assert "ecg_pattern" in pred
        assert "features" in pred
        assert "latency_ms" in pred
        assert pred["ecg_pattern"]["classification"] in [
            "Normal Sinus Rhythm",
            "Sinus Tachycardia",
            "Sinus Bradycardia",
            "Irregular Rhythm",
        ]


def test_websocket_live_alias_and_initial_snapshot(client):
    """Connecting to /ws/live immediately receives the latest cached snapshot if present."""
    client.post(
        "/api/readings",
        json={
            "device_id": "ESP32_LIVE",
            "heart_rate": 72.0,
            "spo2": 99.0,
            "temperature": 36.6,
            "ecg_samples": [0.05, 0.65, -0.15, 0.1] * 10,
        },
    )

    with client.websocket_connect("/ws/live") as websocket:
        initial = websocket.receive_json()
        assert initial["device_id"] == "ESP32_LIVE"
        assert initial["heart_rate"] == 72.0

        websocket.send_text("ping")
        assert websocket.receive_json() == {"type": "pong"}


def test_raw_adc_ecg_normalization(client):
    """Raw 10-bit/12-bit ESP32 ADC integer counts are centered and scaled to mV."""
    raw_adc_samples = [512, 518, 525, 540, 610, 720, 850, 650, 530, 515] * 5
    response = client.post(
        "/api/readings",
        json={
            "device_id": "ESP32_ADC",
            "heart_rate": 74.0,
            "spo2": 98.2,
            "temperature": 36.8,
            "ecg_samples": raw_adc_samples,
            "leads_off": False,
        },
    )
    assert response.status_code == 200

    latest = client.get("/api/readings/latest").json()
    normalized_ecg = latest["ecg_samples"]
    assert len(normalized_ecg) == len(raw_adc_samples)
    assert max(abs(val) for val in normalized_ecg) < 5.0
    assert latest["prediction"]["features"]["rmsEcg"] < 1000.0


def test_leads_off_and_alert_generation(client):
    """Hypoxia and disconnected ECG leads generate structured dashboard alerts."""
    response = client.post(
        "/api/readings",
        json={
            "device_id": "ESP32_ALERT",
            "heart_rate": 130.0,
            "spo2": 88.0,
            "temperature": 38.5,
            "leads_off": True,
            "ecg_samples": [512, 513, 511, 512] * 10,
        },
    )
    assert response.status_code == 200
    body = response.json()

    latest = client.get("/api/readings/latest").json()
    assert latest["leads_connected"] is False
    assert latest["ecg_signal_quality"] == "Leads Off"

    messages = [alert["message"] for alert in body["alerts"]]
    assert any("SpO2" in msg for msg in messages)
    assert any("heart rate" in msg.lower() for msg in messages)
    assert any("temperature" in msg.lower() for msg in messages)
    assert any("leads disconnected" in msg.lower() for msg in messages)


def test_readings_latest_404_and_history(client):
    """GET /api/readings/latest returns 404 when empty, and history orders newest first."""
    empty_res = client.get("/api/readings/latest")
    assert empty_res.status_code == 404

    for hr in (70.0, 74.0, 78.0):
        client.post(
            "/api/readings",
            json={
                "device_id": "ESP32_HIST",
                "heart_rate": hr,
                "spo2": 98.0,
                "temperature": 36.7,
                "ecg_samples": [0.0, 0.5, -0.2, 0.1] * 5,
            },
        )

    hist_res = client.get("/api/readings/history?limit=2")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["count"] == 2
    assert [r["heart_rate"] for r in hist_data["readings"]] == [78.0, 74.0]


def test_device_token_auth_when_configured(client, monkeypatch):
    """When DEVICE_AUTH_TOKEN is set, X-Device-Token header is enforced."""
    monkeypatch.setenv("DEVICE_AUTH_TOKEN", "secret-esp32-key")
    payload = {
        "device_id": "ESP32_AUTH",
        "heart_rate": 72.0,
        "spo2": 98.0,
        "temperature": 36.7,
        "ecg_samples": [0.0, 0.4, -0.1] * 5,
    }

    unauthorized = client.post("/api/readings", json=payload)
    assert unauthorized.status_code == 401

    wrong_token = client.post(
        "/api/readings", json=payload, headers={"X-Device-Token": "wrong"}
    )
    assert wrong_token.status_code == 401

    authorized = client.post(
        "/api/readings",
        json=payload,
        headers={"X-Device-Token": "secret-esp32-key"},
    )
    assert authorized.status_code == 200


def test_ws_token_auth_when_configured(client, monkeypatch):
    """When WS_AUTH_TOKEN is set, invalid WebSocket tokens are rejected."""
    monkeypatch.setenv("WS_AUTH_TOKEN", "ws-secret")

    with pytest.raises(Exception):
        with client.websocket_connect("/ws/health?token=wrong"):
            pass

    with client.websocket_connect("/ws/health?token=ws-secret") as websocket:
        websocket.send_text('{"type": "ping"}')
        assert websocket.receive_json() == {"type": "pong"}
