"""Unit and Integration Tests for Machine Learning Service and Prediction API Endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.prediction_service import PredictionService
from ml.src.data_generator import generate_synthetic_ecg_buffer
from ml.src.feature_extraction import FeatureExtractor


@pytest.fixture
def client():
    """Create FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def prediction_service():
    """Retrieve in-memory prediction service singleton."""
    return PredictionService.get_instance()


def test_feature_extractor_vector():
    """Verify feature extractor extracts 6-dimensional vectors accurately."""
    extractor = FeatureExtractor(window_size=10)
    mock_buffer = [
        {
            "heart_rate": 72.0 + i,
            "spo2": 98.0,
            "temperature": 36.6 + (i * 0.02),
            "ecg_samples": [0.1, 0.2, 0.7, -0.2, 0.1],
        }
        for i in range(10)
    ]

    vec = extractor.extract_vector(mock_buffer)
    assert len(vec) == 6
    assert 72.0 <= vec[0] <= 82.0  # mean_hr
    assert vec[2] == 98.0  # mean_spo2
    assert round(vec[4], 2) == 0.18  # delta_temp


def test_ecg_rhythm_classification():
    """Verify heuristic classification for various heart rate regimes."""
    extractor = FeatureExtractor()

    # Bradycardia
    brady = extractor.analyze_ecg_pattern(ecg_samples=[], heart_rate=45.0, leads_connected=True)
    assert brady["classification"] == "Sinus Bradycardia"

    # Tachycardia
    tachy = extractor.analyze_ecg_pattern(ecg_samples=[], heart_rate=125.0, leads_connected=True)
    assert tachy["classification"] == "Sinus Tachycardia"

    # Normal
    normal = extractor.analyze_ecg_pattern(ecg_samples=[], heart_rate=75.0, leads_connected=True)
    assert normal["classification"] == "Normal Sinus Rhythm"

    # Leads off
    leads_off = extractor.analyze_ecg_pattern(ecg_samples=[], heart_rate=75.0, leads_connected=False)
    assert leads_off["classification"] == "Leads Disconnected"


def test_prediction_service_inference(prediction_service):
    """Verify PredictionService generates valid PredictionResponse on normal telemetry."""
    ecg = generate_synthetic_ecg_buffer(72.0, num_samples=50)

    # Warm buffer with 5 normal readings
    for _ in range(5):
        res = prediction_service.predict(
            heart_rate=72.0,
            spo2=98.5,
            temperature=36.7,
            ecg_samples=ecg,
            leads_connected=True,
        )

    assert res.status in ["Normal", "Borderline", "Elevated"]
    assert 0.0 <= res.anomalyScore <= 1.0
    assert res.trends.heartRate.direction in ["Stable", "Increasing", "Decreasing"]
    assert res.features.meanHr > 0.0


def test_prediction_api_get_latest(client):
    """Test GET /api/predictions/latest returns HTTP 200 with complete schema."""
    response = client.get("/api/predictions/latest")
    assert response.status_code == 200
    data = response.json()

    assert "anomalyScore" in data
    assert "threshold" in data
    assert "trends" in data
    assert "ecgPattern" in data
    assert "features" in data
    assert "inferenceLatencyMs" in data
    assert data["threshold"] == 0.65


def test_prediction_api_evaluate_endpoint(client):
    """Test POST /api/predictions/evaluate computes anomaly inference for incoming packet."""
    ecg = generate_synthetic_ecg_buffer(130.0, num_samples=50)
    payload = {
        "heart_rate": 130.0,
        "spo2": 88.0,
        "temperature": 38.5,
        "ecg_samples": ecg,
        "leads_connected": True,
    }

    response = client.post("/api/predictions/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["isAnomaly"] is True
    assert data["anomalyScore"] >= 0.65
    assert data["status"] == "Elevated"
    assert data["ecgPattern"]["classification"] == "Sinus Tachycardia"
