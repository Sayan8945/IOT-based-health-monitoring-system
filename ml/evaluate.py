"""Model Evaluation and Benchmark Suite.

Evaluates the trained Isolation Forest on an independent test dataset with injected
anomalies, measures ROC-AUC, classification metrics, and benchmarks per-sample inference latency.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
import joblib
import numpy as np
from sklearn.metrics import classification_report, roc_auc_score

current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from ml.src.data_generator import generate_dataset
from ml.src.feature_extraction import FeatureExtractor


def evaluate_model(
    model_dir: Path | None = None,
    test_records: int = 3000,
    seed: int = 99,
) -> dict:
    """Benchmark model accuracy and inference latency."""
    if model_dir is None:
        model_dir = current_dir / "saved_models"

    model_path = model_dir / "isolation_forest.joblib"
    scaler_path = model_dir / "scaler.joblib"
    meta_path = model_dir / "model_metadata.json"

    if not model_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(f"Model artifacts not found in {model_dir}. Run ml/train.py first.")

    print(f"[*] Loading serialized artifacts from {model_dir}...")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    print(f"[*] Generating {test_records} independent test records with injected anomalies...")
    records = generate_dataset(total_records=test_records, anomaly_ratio=0.08, seed=seed)

    extractor = FeatureExtractor(window_size=30)
    features_list = []
    labels_list = []

    for i in range(30, len(records)):
        window = records[i - 30 : i]
        vec = extractor.extract_vector(window)
        is_anomaly = records[i - 1]["is_anomaly"]
        features_list.append(vec)
        labels_list.append(1 if is_anomaly else 0)

    X_test = np.array(features_list, dtype=np.float64)
    y_test = np.array(labels_list, dtype=np.int32)
    X_test_scaled = scaler.transform(X_test)

    print(f"[*] Evaluating on {len(y_test)} test windows ({np.sum(y_test)} anomaly windows)...")

    # Score samples
    raw_scores = model.score_samples(X_test_scaled)
    # Scikit-learn score_samples: more negative = more abnormal
    # Invert so higher = more abnormal
    inverted_scores = -raw_scores

    # Normalize to [0.0, 1.0] using metadata min/max bounds
    s_min = -metadata.get("score_max", 0.0)
    s_max = -metadata.get("score_min", -1.0)
    denom = max(1e-5, s_max - s_min)
    norm_scores = np.clip((inverted_scores - s_min) / denom, 0.0, 1.0)

    # Threshold evaluation
    threshold = metadata.get("threshold", 0.65)
    y_pred = (norm_scores >= threshold).astype(np.int32)

    # Metrics
    auc = float(roc_auc_score(y_test, norm_scores)) if len(np.unique(y_test)) > 1 else 0.0

    print("\n" + "=" * 55)
    print("           MODEL PERFORMANCE METRICS")
    print("=" * 55)
    print(f"ROC-AUC Score: {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["Nominal", "Anomaly"]))

    # Latency Benchmark
    print("\n[*] Benchmarking single-sample inference latency (1,000 runs)...")
    single_sample = X_test_scaled[0:1]
    warmup = model.score_samples(single_sample)

    t0 = time.perf_counter()
    iterations = 1000
    for _ in range(iterations):
        _ = model.score_samples(single_sample)
    total_time = time.perf_counter() - t0
    avg_latency_ms = (total_time / iterations) * 1000.0

    print(f"[+] Average Inference Latency: {avg_latency_ms:.3f} ms (Target: < 5.0 ms)")
    assert avg_latency_ms < 5.0, f"Inference latency exceeded 5 ms: {avg_latency_ms:.3f} ms"
    print("[+] Latency Requirement Met: YES")
    print("=" * 55)

    return {
        "roc_auc": round(auc, 4),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "total_test_samples": len(y_test),
        "anomalies_evaluated": int(np.sum(y_test)),
    }


if __name__ == "__main__":
    evaluate_model()
