"""Server business logic and analytical services."""

from app.services.alert_service import AlertService
from app.services.reading_service import ReadingService

__all__ = ["AlertService", "PredictionService", "ReadingService"]


def __getattr__(name: str):
    if name == "PredictionService":
        from app.services.prediction_service import PredictionService

        return PredictionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
