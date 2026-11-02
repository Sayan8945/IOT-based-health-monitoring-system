"""Signal Processing and Feature Extraction Engine.

Extracts multivariate time-series features, computes linear trend slopes, and analyzes
Lead-I ECG waveform rhythm dynamics for anomaly detection and clinical presentation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import signal


class FeatureExtractor:
    """Extracts statistical feature vectors, vital trend directions, and ECG rhythm patterns."""

    FEATURE_NAMES: List[str] = [
        "mean_hr",
        "std_hr",
        "mean_spo2",
        "mean_temp",
        "delta_temp",
        "rms_ecg",
    ]

    def __init__(self, window_size: int = 30) -> None:
        self.window_size = window_size

    @staticmethod
    def calculate_rms(samples: List[float] | np.ndarray) -> float:
        """Calculate Root-Mean-Square (RMS) amplitude of an ECG sample array in microvolts."""
        arr = np.asarray(samples, dtype=np.float64)
        if len(arr) == 0:
            return 0.0
        # Remove DC baseline offset
        demeaned = arr - np.mean(arr)
        rms = np.sqrt(np.mean(np.square(demeaned)))
        # Scale to microvolts range matching clinical standard (e.g., ~100-250 uV)
        return float(round(rms * 1000.0, 1))

    def extract_vector(self, buffer: List[Dict[str, any]]) -> np.ndarray:
        """Extract a single 6-dimensional feature vector from a window of telemetry records.

        Returns array of [mean_hr, std_hr, mean_spo2, mean_temp, delta_temp, rms_ecg].
        """
        if not buffer:
            return np.zeros(len(self.FEATURE_NAMES), dtype=np.float64)

        hrs = [r["heart_rate"] for r in buffer]
        spo2s = [r["spo2"] for r in buffer]
        temps = [r["temperature"] for r in buffer]

        mean_hr = float(np.mean(hrs))
        std_hr = float(np.std(hrs)) if len(hrs) > 1 else 1.0
        mean_spo2 = float(np.mean(spo2s))
        mean_temp = float(np.mean(temps))
        delta_temp = float(temps[-1] - temps[0]) if len(temps) > 1 else 0.0

        # Latest ECG buffer
        latest_ecg = buffer[-1].get("ecg_samples", [])
        rms_ecg = self.calculate_rms(latest_ecg)

        return np.array(
            [mean_hr, std_hr, mean_spo2, mean_temp, delta_temp, rms_ecg],
            dtype=np.float64,
        )

    def extract_feature_dict(self, buffer: List[Dict[str, any]]) -> Dict[str, float]:
        """Extract named feature dictionary matching frontend MLAnalysisCard contract."""
        vec = self.extract_vector(buffer)
        return {
            "meanHr": round(float(vec[0]), 1),
            "stdHr": round(float(vec[1]), 2),
            "meanSpo2": round(float(vec[2]), 1),
            "meanTemp": round(float(vec[3]), 2),
            "deltaTemp": round(float(vec[4]), 3),
            "rmsEcg": round(float(vec[5]), 1),
        }

    @staticmethod
    def _compute_linear_slope(values: List[float], dt_minutes: float = 0.5) -> float:
        """Compute the ordinary least squares (OLS) linear slope per minute."""
        n = len(values)
        if n < 2:
            return 0.0

        x = np.arange(n) * (dt_minutes / max(1, n - 1))
        y = np.array(values, dtype=np.float64)

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        denominator = np.sum((x - x_mean) ** 2)
        if denominator == 0.0:
            return 0.0

        slope = np.sum((x - x_mean) * (y - y_mean)) / denominator
        return float(slope)

    def compute_trends(self, buffer: List[Dict[str, any]]) -> Dict[str, Dict[str, str]]:
        """Compute trend slope and clinical direction for each physiological metric."""
        if len(buffer) < 2:
            return {
                "heartRate": {"direction": "Stable", "slope": "+0.0 bpm/min"},
                "spo2": {"direction": "Steady", "slope": "0.0 %/min"},
                "temperature": {"direction": "Constant", "slope": "+0.0 °C/hr"},
            }

        hrs = [r["heart_rate"] for r in buffer]
        spo2s = [r["spo2"] for r in buffer]
        temps = [r["temperature"] for r in buffer]

        hr_slope = self._compute_linear_slope(hrs, dt_minutes=0.5)
        spo2_slope = self._compute_linear_slope(spo2s, dt_minutes=0.5)
        # Temperature slope expressed in °C per hour
        temp_slope = self._compute_linear_slope(temps, dt_minutes=0.5) * 60.0

        # HR direction
        if hr_slope > 0.8:
            hr_dir = "Increasing"
        elif hr_slope < -0.8:
            hr_dir = "Decreasing"
        else:
            hr_dir = "Stable"

        # SpO2 direction
        if spo2_slope > 0.3:
            spo2_dir = "Rising"
        elif spo2_slope < -0.3:
            spo2_dir = "Declining"
        else:
            spo2_dir = "Steady"

        # Temp direction
        if temp_slope > 0.15:
            temp_dir = "Rising"
        elif temp_slope < -0.15:
            temp_dir = "Falling"
        else:
            temp_dir = "Constant"

        hr_sign = "+" if hr_slope >= 0 else ""
        temp_sign = "+" if temp_slope >= 0 else ""
        spo2_sign = "+" if spo2_slope > 0 else ""

        return {
            "heartRate": {
                "direction": hr_dir,
                "slope": f"{hr_sign}{hr_slope:.1f} bpm/min",
            },
            "spo2": {
                "direction": spo2_dir,
                "slope": f"{spo2_sign}{spo2_slope:.1f} %/min",
            },
            "temperature": {
                "direction": temp_dir,
                "slope": f"{temp_sign}{temp_slope:.1f} °C/hr",
            },
        }

    @staticmethod
    def analyze_ecg_pattern(
        ecg_samples: List[float],
        heart_rate: float,
        leads_connected: bool = True,
    ) -> Dict[str, any]:
        """Analyze Lead-I ECG rhythm regularity and R-R interval parameters using peak detection."""
        if not leads_connected:
            return {
                "classification": "Leads Disconnected",
                "rrInterval": 0,
                "rrVariance": 0,
            }

        arr = np.asarray(ecg_samples, dtype=np.float64)
        if len(arr) < 20:
            # Fallback based on heart rate
            computed_rr = int(round(60000.0 / max(30.0, min(220.0, heart_rate))))
            rhythm = (
                "Sinus Tachycardia"
                if heart_rate > 100.0
                else ("Sinus Bradycardia" if heart_rate < 60.0 else "Normal Sinus Rhythm")
            )
            return {
                "classification": rhythm,
                "rrInterval": computed_rr,
                "rrVariance": 12,
            }

        # Find R-peaks with scipy peak finder
        peaks, _ = signal.find_peaks(arr, distance=30, height=0.35, prominence=0.3)

        if len(peaks) >= 2:
            # Peak differences in samples at 100 Hz (1 sample = 10 ms)
            intervals_ms = np.diff(peaks) * 10.0
            mean_rr = int(round(float(np.mean(intervals_ms))))
            variance_rr = int(round(float(np.var(intervals_ms))))
        else:
            mean_rr = int(round(60000.0 / max(30.0, min(220.0, heart_rate))))
            variance_rr = 12

        # Rhythm classification
        if heart_rate > 105.0:
            classification = "Sinus Tachycardia"
        elif heart_rate < 50.0:
            classification = "Sinus Bradycardia"
        elif variance_rr > 450:
            classification = "Irregular Rhythm"
        else:
            classification = "Normal Sinus Rhythm"

        return {
            "classification": classification,
            "rrInterval": mean_rr,
            "rrVariance": variance_rr,
        }
