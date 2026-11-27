"""Clinical threshold and ML anomaly alert evaluation service."""

from __future__ import annotations

from typing import Dict, List, Optional

from app.core.config import Settings, get_settings
from app.schemas.prediction import PredictionResponse


class AlertService:
    """Evaluates physiological thresholds, lead state, and ML anomalies into event items."""

    @staticmethod
    def evaluate(
        heart_rate: float,
        spo2: float,
        temperature: float,
        leads_connected: bool,
        prediction: Optional[PredictionResponse] = None,
        settings: Optional[Settings] = None,
    ) -> List[Dict[str, str]]:
        """Return structured alerts matching the dashboard EventLog / useTelemetry contract."""
        cfg = settings or get_settings()
        alerts: List[Dict[str, str]] = []

        if spo2 < cfg.spo2_critical_threshold:
            alerts.append(
                {
                    "severity": "critical",
                    "category": "Vitals",
                    "message": f"Critical low SpO2: {spo2:.1f}% (Threshold: {cfg.spo2_critical_threshold:.0f}%)",
                }
            )
        elif spo2 < cfg.spo2_warning_threshold:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "Vitals",
                    "message": f"Low SpO2: {spo2:.1f}% (Threshold: {cfg.spo2_warning_threshold:.0f}%)",
                }
            )

        if heart_rate > cfg.hr_high_threshold:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "Vitals",
                    "message": f"High heart rate: {heart_rate:.0f} BPM (Threshold: {cfg.hr_high_threshold:.0f} BPM)",
                }
            )
        elif heart_rate < cfg.hr_low_threshold:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "Vitals",
                    "message": f"Low heart rate: {heart_rate:.0f} BPM (Threshold: {cfg.hr_low_threshold:.0f} BPM)",
                }
            )

        if temperature > cfg.temp_high_threshold:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "Vitals",
                    "message": f"High temperature: {temperature:.1f} °C (Threshold: {cfg.temp_high_threshold:.1f} °C)",
                }
            )
        elif temperature < cfg.temp_low_threshold:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "Vitals",
                    "message": f"Low temperature: {temperature:.1f} °C (Threshold: {cfg.temp_low_threshold:.1f} °C)",
                }
            )

        if not leads_connected:
            alerts.append(
                {
                    "severity": "warning",
                    "category": "Hardware",
                    "message": "AD8232 ECG leads disconnected",
                }
            )

        if prediction is not None and prediction.isAnomaly:
            alerts.append(
                {
                    "severity": "critical",
                    "category": "ML Model",
                    "message": (
                        f"ML anomaly detected: Score {prediction.anomalyScore:.2f} "
                        f"(Threshold: {prediction.threshold:.2f})"
                    ),
                }
            )

        return alerts
