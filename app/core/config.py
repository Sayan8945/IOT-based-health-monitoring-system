"""Application configuration settings loaded from environment variables and .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_once() -> None:
    """Populate os.environ from project .env without overriding already-set variables."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.is_file():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv_once()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings for MongoDB, telemetry ingestion, ML normalization, and WebSockets."""

    mongodb_uri: str = ""
    mongodb_db_name: str = "smarthealth_iot"
    mongodb_ttl_days: int = 30
    mongodb_timeout_ms: int = 5000
    device_auth_token: str = ""
    ws_auth_token: str = ""
    ecg_adc_max: int = 4095
    ecg_mv_range: float = 3.3
    telemetry_history_maxlen: int = 100
    spo2_warning_threshold: float = 95.0
    spo2_critical_threshold: float = 90.0
    hr_high_threshold: float = 100.0
    hr_low_threshold: float = 60.0
    temp_high_threshold: float = 37.5
    temp_low_threshold: float = 35.5


def get_settings() -> Settings:
    """Read current settings from environment variables."""
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI", "").strip(),
        mongodb_db_name=os.getenv("MONGODB_DB_NAME", "smarthealth_iot").strip() or "smarthealth_iot",
        mongodb_ttl_days=max(1, _env_int("MONGODB_TTL_DAYS", 30)),
        mongodb_timeout_ms=max(500, _env_int("MONGODB_TIMEOUT_MS", 5000)),
        device_auth_token=os.getenv("DEVICE_AUTH_TOKEN", "").strip(),
        ws_auth_token=os.getenv("WS_AUTH_TOKEN", "").strip(),
        ecg_adc_max=max(1, _env_int("ECG_ADC_MAX", 4095)),
        ecg_mv_range=max(0.1, _env_float("ECG_MV_RANGE", 3.3)),
        telemetry_history_maxlen=max(1, _env_int("TELEMETRY_HISTORY_MAXLEN", 100)),
        spo2_warning_threshold=_env_float("SPO2_WARNING_THRESHOLD", 95.0),
        spo2_critical_threshold=_env_float("SPO2_CRITICAL_THRESHOLD", 90.0),
        hr_high_threshold=_env_float("HR_HIGH_THRESHOLD", 100.0),
        hr_low_threshold=_env_float("HR_LOW_THRESHOLD", 60.0),
        temp_high_threshold=_env_float("TEMP_HIGH_THRESHOLD", 37.5),
        temp_low_threshold=_env_float("TEMP_LOW_THRESHOLD", 35.5),
    )
