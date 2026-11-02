"""Model Training Pipeline for IoT Health Monitoring Telemetry.

Extracts multivariate physiological features from synthetic baseline telemetry,
fits a Scikit-Learn Isolation Forest with RobustScaler, and serializes artifacts.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

# Add parent directory to sys.path to allow imports when run standalone
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from ml.src.data_generator import generate_dataset
from ml.src.feature_extraction import FeatureExtractor


def train_anomaly_model(
    output_dir: Path | None = None,
    total_records: int = 8000,
    contamination: float = 0.03,
    n_estimators: int = 50,
    seed: int = 42,
) -> dict:
    """Train and serialize the Isolation Forest model and RobustScaler."""
    if output_dir is None:
        output_dir = current_dir / "saved_models"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Generating {total_records} synthetic telemetry records...")
    records = generate_dataset(total_records=total_records, anomaly_ratio=contamination, seed=seed)

    print("[*] Extracting multivariate sliding window feature vectors...")
    extractor = FeatureExtractor(window_size=30)
    features_list = []
    labels_list = []

    # Slide 30-sample window over sequential records
    for i in range(30, len(records)):
        window = records[i - 30 : i]
        vec = extractor.extract_vector(window)
        is_anomaly = records[i - 1]["is_anomaly"]
        features_list.append(vec)
        labels_list.append(1 if is_anomaly else 0)

    X = np.array(features_list, dtype=np.float64)
    y = np.array(labels_list, dtype=np.int32)
    print(f"[*] Feature matrix shape: {X.shape} (Anomalies in stream: {np.sum(y)})")

    # Fit RobustScaler to handle physiological outliers gracefully
    print("[*] Fitting RobustScaler on feature vectors...")
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    # Train Isolation Forest (n_jobs=1 avoids threadpool dispatch overhead during single-sample real-time inference)
    print(f"[*] Training IsolationForest (n_estimators={n_estimators}, contamination={contamination})...")
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=seed,
        n_jobs=1,
    )
    model.fit(X_scaled)

    # Compute raw decision function scores on training set to calibrate threshold
    raw_scores = model.score_samples(X_scaled)
    min_score = float(np.min(raw_scores))
    max_score = float(np.max(raw_scores))
    p10_score = float(np.percentile(raw_scores, 10))

    # Calibrate normalization parameters so nominal readings lie in [0.0, 0.45],
    # borderline in [0.45, 0.65], and anomalies >= 0.65.
    model_path = output_dir / "isolation_forest.joblib"
    scaler_path = output_dir / "scaler.joblib"
    meta_path = output_dir / "model_metadata.json"

    print(f"[*] Serializing model to {model_path}...")
    joblib.dump(model, model_path, compress=3)

    print(f"[*] Serializing scaler to {scaler_path}...")
    joblib.dump(scaler, scaler_path, compress=3)

    metadata = {
        "model_type": "IsolationForest",
        "n_estimators": n_estimators,
        "contamination": contamination,
        "features": FeatureExtractor.FEATURE_NAMES,
        "trained_samples": int(X.shape[0]),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "score_min": min_score,
        "score_max": max_score,
        "threshold": 0.65,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[+] Model training complete! Artifacts saved in {output_dir}")
    return metadata


if __name__ == "__main__":
    train_anomaly_model()
