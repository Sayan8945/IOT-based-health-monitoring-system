"""Real-time hardware telemetry ingestion, normalization, persistence, and WebSocket broadcast."""

from __future__ import annotations

import collections
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Deque, Dict, List, Optional

from app.core.config import get_settings
from app.database.collections import (
    get_alerts_collection,
    get_devices_collection,
    get_vitals_collection,
)
from app.database.connection import DatabaseManager, get_db_manager
from app.models.health_reading import (
    build_alert_documents,
    build_vitals_document,
    serialize_mongo_doc,
)
from app.schemas.health_reading import HealthReadingIn, ReadingIngestResponse
from app.services.alert_service import AlertService
from app.websocket.manager import ConnectionManager, get_ws_manager

if TYPE_CHECKING:
    from app.schemas.prediction import PredictionResponse
    from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


class ReadingService:
    """Coordinates ESP32 telemetry validation, ML inference, MongoDB storage, and WS broadcast."""

    _instance: Optional["ReadingService"] = None

    def __init__(
        self,
        ws_manager: Optional[ConnectionManager] = None,
        prediction_service: Optional["PredictionService"] = None,
        db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        settings = get_settings()
        self._ws_manager = ws_manager or get_ws_manager()
        self._prediction_service = prediction_service
        self._db_manager = db_manager or get_db_manager()
        self._ml_unavailable = False
        self._history: Deque[Dict[str, Any]] = collections.deque(
            maxlen=settings.telemetry_history_maxlen
        )
        self._alerts_history: Deque[Dict[str, Any]] = collections.deque(
            maxlen=settings.telemetry_history_maxlen
        )
        self._latest_payload: Optional[Dict[str, Any]] = None

    @classmethod
    def get_instance(cls) -> "ReadingService":
        """Get or create the singleton ReadingService instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def clear_history(self) -> None:
        """Clear in-memory telemetry and alert caches (primarily for isolated tests)."""
        self._history.clear()
        self._alerts_history.clear()
        self._latest_payload = None

    @property
    def latest_payload(self) -> Optional[Dict[str, Any]]:
        """Return the most recent in-memory telemetry snapshot, if any."""
        return self._latest_payload

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return up to ``limit`` recent in-memory telemetry payloads newest-first."""
        items = list(self._history)
        items.reverse()
        return items[:limit]

    async def fetch_latest(
        self, device_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the latest reading from MongoDB if connected, else from memory."""
        db = self._db_manager.database
        if db is not None:
            try:
                query: Dict[str, Any] = {"device_id": device_id} if device_id else {}
                doc = await get_vitals_collection(db).find_one(
                    query, sort=[("created_at", -1)]
                )
                if doc is not None:
                    return serialize_mongo_doc(doc)
            except Exception as exc:
                logger.warning("MongoDB latest query failed (%s); falling back to memory.", exc)

        if device_id is None:
            return self._latest_payload
        for item in reversed(self._history):
            if item.get("device_id") == device_id:
                return item
        return None

    async def fetch_history(
        self, limit: int = 50, device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recent readings from MongoDB if connected, else from memory."""
        db = self._db_manager.database
        if db is not None:
            try:
                query: Dict[str, Any] = {"device_id": device_id} if device_id else {}
                cursor = (
                    get_vitals_collection(db)
                    .find(query)
                    .sort("created_at", -1)
                    .limit(limit)
                )
                docs = await cursor.to_list(length=limit)
                if docs:
                    return [serialize_mongo_doc(doc) for doc in docs]
            except Exception as exc:
                logger.warning("MongoDB history query failed (%s); falling back to memory.", exc)

        if device_id is None:
            return self.get_history(limit=limit)
        filtered = [item for item in reversed(self._history) if item.get("device_id") == device_id]
        return filtered[:limit]

    async def fetch_alerts(
        self, limit: int = 50, device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recent alerts from MongoDB if connected, else from memory."""
        db = self._db_manager.database
        if db is not None:
            try:
                query: Dict[str, Any] = {"device_id": device_id} if device_id else {}
                cursor = (
                    get_alerts_collection(db)
                    .find(query)
                    .sort("created_at", -1)
                    .limit(limit)
                )
                docs = await cursor.to_list(length=limit)
                if docs:
                    return [serialize_mongo_doc(doc) for doc in docs]
            except Exception as exc:
                logger.warning("MongoDB alerts query failed (%s); falling back to memory.", exc)

        items = list(reversed(self._alerts_history))
        if device_id is not None:
            items = [item for item in items if item.get("device_id") == device_id]
        return items[:limit]

    @staticmethod
    def normalize_ecg_samples(
        samples: List[float],
        adc_max: Optional[int] = None,
        mv_range: Optional[float] = None,
    ) -> List[float]:
        """Convert raw ESP32 ADC integer counts to zero-centered mV floats if needed.

        Buffers whose values already sit within [-5.0, 5.0] mV are passed through unchanged.
        """
        if not samples:
            return []

        max_abs = max(abs(float(val)) for val in samples)
        if max_abs <= 5.0:
            return [round(float(val), 4) for val in samples]

        cfg = get_settings()
        effective_adc_max = adc_max if adc_max is not None else cfg.ecg_adc_max
        effective_mv_range = mv_range if mv_range is not None else cfg.ecg_mv_range

        mean_adc = sum(float(val) for val in samples) / len(samples)
        counts_per_mv = max(1.0, effective_adc_max / effective_mv_range)
        return [round((float(val) - mean_adc) / counts_per_mv, 4) for val in samples]

    @staticmethod
    def compute_signal_quality(leads_connected: bool, ecg_mv: List[float]) -> str:
        """Derive human-readable Lead-I signal quality label for ECGMonitor.jsx."""
        if not leads_connected:
            return "Leads Off"
        if not ecg_mv or (max(ecg_mv) - min(ecg_mv)) < 0.01:
            return "Fair"
        return "Good"

    def _get_prediction_service(self) -> Optional["PredictionService"]:
        """Lazily resolve PredictionService so core ingestion works even if ML deps are absent."""
        if self._prediction_service is not None:
            return self._prediction_service
        if self._ml_unavailable:
            return None
        try:
            from app.services.prediction_service import PredictionService

            self._prediction_service = PredictionService.get_instance()
            return self._prediction_service
        except Exception as exc:
            self._ml_unavailable = True
            logger.warning("ML PredictionService unavailable; using fallback metrics: %s", exc)
            return None

    def _run_ml_inference(
        self,
        reading: HealthReadingIn,
        ecg_mv: List[float],
        leads_connected: bool,
    ) -> Optional["PredictionResponse"]:
        """Run in-memory ML inference defensively so telemetry streaming never breaks."""
        service = self._get_prediction_service()
        if service is None:
            return None
        try:
            return service.predict(
                heart_rate=reading.heart_rate,
                spo2=reading.spo2,
                temperature=reading.temperature,
                ecg_samples=ecg_mv,
                leads_connected=leads_connected,
            )
        except Exception as exc:
            logger.exception("ML inference failed during reading ingestion: %s", exc)
            return None

    @staticmethod
    def _fallback_prediction_dict(
        reading: HealthReadingIn, leads_connected: bool
    ) -> Dict[str, Any]:
        """Build a neutral ML summary when ML inference is unavailable."""
        rr_interval = int(round(60000.0 / max(30.0, min(220.0, reading.heart_rate))))
        rhythm = (
            "Leads Disconnected"
            if not leads_connected
            else (
                "Sinus Tachycardia"
                if reading.heart_rate > 105.0
                else ("Sinus Bradycardia" if reading.heart_rate < 50.0 else "Normal Sinus Rhythm")
            )
        )
        return {
            "status": "Normal",
            "risk_level": "Nominal",
            "anomaly_score": 0.0,
            "anomaly": False,
            "threshold": 0.65,
            "trends": {
                "heartRate": {"direction": "Stable", "slope": "+0.0 bpm/min"},
                "spo2": {"direction": "Steady", "slope": "0.0 %/min"},
                "temperature": {"direction": "Constant", "slope": "+0.0 °C/hr"},
            },
            "ecg_pattern": {
                "classification": rhythm,
                "rrInterval": rr_interval,
                "rrVariance": 0,
            },
            "features": {
                "meanHr": round(reading.heart_rate, 1),
                "stdHr": 0.0,
                "meanSpo2": round(reading.spo2, 1),
                "meanTemp": round(reading.temperature, 2),
                "deltaTemp": 0.0,
                "rmsEcg": 0.0,
            },
            "latency_ms": 0.0,
        }

    def build_ws_payload(
        self,
        reading: HealthReadingIn,
        ecg_mv: List[float],
        leads_connected: bool,
        signal_quality: str,
        timestamp_iso: str,
        prediction: Optional["PredictionResponse"],
        alerts: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Format telemetry + ML inference to match the React useTelemetry.js contract."""
        sensors = reading.resolved_sensors

        if prediction is not None:
            pred_payload: Dict[str, Any] = {
                "status": prediction.status,
                "risk_level": prediction.riskLevel,
                "anomaly_score": prediction.anomalyScore,
                "anomaly": prediction.isAnomaly,
                "threshold": prediction.threshold,
                "trends": prediction.trends.model_dump(),
                "ecg_pattern": prediction.ecgPattern.model_dump(),
                "features": prediction.features.model_dump(),
                "latency_ms": prediction.inferenceLatencyMs,
            }
        else:
            pred_payload = self._fallback_prediction_dict(reading, leads_connected)

        return {
            "device_id": reading.device_id,
            "timestamp": timestamp_iso,
            "heart_rate": round(reading.heart_rate, 1),
            "spo2": round(reading.spo2, 1),
            "temperature": round(reading.temperature, 2),
            "leads_connected": leads_connected,
            "ecg_signal_quality": signal_quality,
            "ecg_samples": ecg_mv,
            "sensors": {
                "pulse_oximeter": sensors.pulse_oximeter,
                "temp_probe": sensors.temp_probe,
                "ecg": sensors.ecg,
            },
            "anomaly_score": pred_payload["anomaly_score"],
            "anomaly": pred_payload["anomaly"],
            "prediction": pred_payload,
            "alerts": alerts,
        }

    async def _persist_to_mongodb(
        self,
        ws_payload: Dict[str, Any],
        device_id: str,
        timestamp_iso: str,
        alerts: List[Dict[str, str]],
    ) -> bool:
        """Persist vitals record, alerts, and device heartbeat to MongoDB if connected."""
        db = self._db_manager.database
        if db is None:
            return False

        now = datetime.now(timezone.utc)
        try:
            vitals_doc = build_vitals_document(ws_payload, created_at=now)
            await get_vitals_collection(db).insert_one(vitals_doc)

            if alerts:
                alert_docs = build_alert_documents(
                    device_id=device_id,
                    timestamp_iso=timestamp_iso,
                    alerts=alerts,
                    created_at=now,
                )
                await get_alerts_collection(db).insert_many(alert_docs)

            await get_devices_collection(db).update_one(
                {"device_id": device_id},
                {
                    "$set": {
                        "last_seen": timestamp_iso,
                        "status": "online",
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "device_id": device_id,
                        "registered_at": timestamp_iso,
                        "metadata": {},
                    },
                },
                upsert=True,
            )
            return True
        except Exception as exc:
            logger.warning("MongoDB persistence error (stream unaffected): %s", exc)
            return False

    async def ingest_and_broadcast(
        self, reading: HealthReadingIn
    ) -> ReadingIngestResponse:
        """Process an incoming ESP32 reading, broadcast to WebSockets, and persist to MongoDB."""
        leads_connected = reading.resolved_leads_connected
        ecg_mv = self.normalize_ecg_samples(reading.ecg_samples)
        signal_quality = self.compute_signal_quality(leads_connected, ecg_mv)
        timestamp_iso = reading.timestamp or datetime.now(timezone.utc).isoformat()

        prediction = self._run_ml_inference(reading, ecg_mv, leads_connected)
        alerts = AlertService.evaluate(
            heart_rate=reading.heart_rate,
            spo2=reading.spo2,
            temperature=reading.temperature,
            leads_connected=leads_connected,
            prediction=prediction,
        )

        ws_payload = self.build_ws_payload(
            reading=reading,
            ecg_mv=ecg_mv,
            leads_connected=leads_connected,
            signal_quality=signal_quality,
            timestamp_iso=timestamp_iso,
            prediction=prediction,
            alerts=alerts,
        )

        self._history.append(ws_payload)
        self._latest_payload = ws_payload
        for alert in alerts:
            self._alerts_history.append(
                {
                    "device_id": reading.device_id,
                    "timestamp": timestamp_iso,
                    **alert,
                }
            )

        clients_notified = await self._ws_manager.broadcast_json(ws_payload)
        persisted = await self._persist_to_mongodb(
            ws_payload=ws_payload,
            device_id=reading.device_id,
            timestamp_iso=timestamp_iso,
            alerts=alerts,
        )

        return ReadingIngestResponse(
            status="success",
            device_id=reading.device_id,
            timestamp=timestamp_iso,
            clients_notified=clients_notified,
            persisted=persisted,
            anomaly_score=ws_payload["anomaly_score"],
            is_anomaly=ws_payload["anomaly"],
            alerts=alerts,
        )
