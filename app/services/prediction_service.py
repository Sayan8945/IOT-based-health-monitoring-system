"""In-Memory Machine Learning Prediction Service.

Loads the trained Isolation Forest model and RobustScaler into memory on startup
and computes sub-5ms anomaly scores, trend trajectories, and ECG pattern metrics.
"""

from __future__ import annotations

import collections
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
import joblib
import numpy as np

from app.schemas.prediction import (
    ECGPatternAnalysis,
    FeatureVector,
    PredictionResponse,
    TrendMetric,
    TrendsSummary,
)
from ml.src.feature_extraction import FeatureExtractor

logger = logging.getLogger(__name__)


class PredictionService:
    """Singleton service for real-time telemetry inference."""

    _instance: Optional["PredictionService"] = None

    def __init__(self, model_dir: Path | None = None) -> None:
        if model_dir is None:
            # server/ml/saved_models
            model_dir = Path(__file__).resolve().parent.parent.parent / "ml" / "saved_models"
        self.model_dir = model_dir
        self.extractor = FeatureExtractor(window_size=30)
        self.buffer = collections.deque(maxlen=30)

        self.model = None
        self.scaler = None
        self.metadata = {
            "threshold": 0.65,
            "score_min": -0.75,
            "score_max": -0.38,
        }
        self.load_artifacts()

    @classmethod
    def get_instance(cls, model_dir: Path | None = None) -> "PredictionService":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(model_dir=model_dir)
        return cls._instance

    def load_artifacts(self) -> None:
        """Load serialized Isolation Forest and Scaler from disk."""
        model_path = self.model_dir / "isolation_forest.joblib"
        scaler_path = self.model_dir / "scaler.joblib"
        meta_path = self.model_dir / "model_metadata.json"

        if model_path.exists() and scaler_path.exists():
            try:
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        self.metadata = json.load(f)
                logger.info("Successfully loaded ML model and scaler from %s", self.model_dir)
            except Exception as e:
                logger.error("Failed to load ML artifacts: %s", e)
                self._fallback_init()
        else:
            logger.warning(
                "ML model artifacts not found at %s. Initializing in fallback mode.",
                self.model_dir,
            )
            self._fallback_init()

    def _fallback_init(self) -> None:
        """Fallback initialization if model files have not yet been trained."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import RobustScaler

        # Fast synthetic fit for immediate development resilience
        from ml.src.data_generator import generate_dataset

        records = generate_dataset(total_records=400, anomaly_ratio=0.03, seed=42)
        feats = [self.extractor.extract_vector(records[max(0, i - 10) : i + 1]) for i in range(len(records))]
        X = np.array(feats)
        self.scaler = RobustScaler().fit(X)
        self.model = IsolationForest(n_estimators=30, contamination=0.03, random_state=42).fit(
            self.scaler.transform(X)
        )

    def predict(
        self,
        heart_rate: float,
        spo2: float,
        temperature: float,
        ecg_samples: Optional[List[float]] = None,
        leads_connected: bool = True,
    ) -> PredictionResponse:
        """Process incoming telemetry packet, update rolling window, and compute inference."""
        t_start = time.perf_counter()

        if ecg_samples is None:
            ecg_samples = []

        reading_dict = {
            "heart_rate": float(heart_rate),
            "spo2": float(spo2),
            "temperature": float(temperature),
            "ecg_samples": ecg_samples,
            "leads_connected": bool(leads_connected),
        }
        self.buffer.append(reading_dict)

        # 1. Feature Extraction
        feature_dict = self.extractor.extract_feature_dict(list(self.buffer))
        features_vec = self.extractor.extract_vector(list(self.buffer)).reshape(1, -1)

        # 2. Model Inference & Normalized Anomaly Score
        if self.scaler is not None and self.model is not None:
            scaled_vec = self.scaler.transform(features_vec)
            raw_score = float(self.model.score_samples(scaled_vec)[0])
        else:
            raw_score = -0.5

        # Normalization to [0.00, 1.00]
        # Invert score so higher = more anomalous
        inverted = -raw_score
        s_min = -float(self.metadata.get("score_max", -0.38))
        s_max = -float(self.metadata.get("score_min", -0.75))
        denom = max(1e-5, s_max - s_min)
        anomaly_score = float(np.clip((inverted - s_min) / denom, 0.0, 1.0))
        anomaly_score = round(anomaly_score, 2)

        # Clinical thresholding
        threshold = float(self.metadata.get("threshold", 0.65))
        is_anomaly = anomaly_score >= threshold

        if is_anomaly:
            status = "Elevated"
            risk_level = "Elevated"
        elif anomaly_score > 0.45:
            status = "Borderline"
            risk_level = "Borderline"
        else:
            status = "Normal"
            risk_level = "Nominal"

        # 3. Vital Trends
        trend_dict = self.extractor.compute_trends(list(self.buffer))
        trends = TrendsSummary(
            heartRate=TrendMetric(**trend_dict["heartRate"]),
            spo2=TrendMetric(**trend_dict["spo2"]),
            temperature=TrendMetric(**trend_dict["temperature"]),
        )

        # 4. ECG Pattern Analysis
        ecg_dict = self.extractor.analyze_ecg_pattern(
            ecg_samples=ecg_samples,
            heart_rate=heart_rate,
            leads_connected=leads_connected,
        )
        ecg_pattern = ECGPatternAnalysis(**ecg_dict)

        # 5. Measure latency
        latency_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

        return PredictionResponse(
            status=status,
            isAnomaly=is_anomaly,
            anomalyScore=anomaly_score,
            threshold=threshold,
            riskLevel=risk_level,
            trends=trends,
            ecgPattern=ecg_pattern,
            features=FeatureVector(**feature_dict),
            inferenceLatencyMs=latency_ms,
        )
