# SmartHealth IoT Health Monitoring — Workflow & Task Tracker

**Last Updated:** 2026-11-28  
**Project Folder:** `IOT-based-health-monitoring-system/`

This folder tracks what has already been completed and what still needs to be built across the hardware, machine learning, and FastAPI backend.

---

## Files in This Folder

- [`update_tracker.py`](update_tracker.py) — Python script that automatically scans the codebase and updates the CSV, Excel, and TXT tracker files. Run with:
  ```bash
  python "Workflow Folder/update_tracker.py"
  ```
- [`things_to_be_done.xlsx`](things_to_be_done.xlsx) — Simple Excel tracker with `Checklist` and `Overview` sheets.
- [`things_to_be_done.csv`](things_to_be_done.csv) — CSV export of the `Checklist` table.
- [`things_to_be_done.txt`](things_to_be_done.txt) — Plain-text checklist version.
- [`README.md`](README.md) — This workflow overview document.

---

## 1. Already Completed (14 Items)

### Hardware & Real Data
1. **ECG hardware setup** — Built and tested the ECG sensor circuit (`ESP32` + `AD8232`).
2. **Collect 4 people's ECG samples** — Collected real ECG sample recordings and plots in `sample_data_and_plots/` (`txt_data/`, `csv_data/`, `plots/`).

### Setup, Security & Database
3. **Environment config & database packages** — Populated `.env.example`, implemented `app/core/config.py`, and added `pymongo[srv]` to `requirements.txt`.
4. **API security with device keys** — Implemented token checks (`verify_device_token`, `verify_ws_token`) in `app/core/security.py`.
5. **MongoDB connection & collections** — Implemented `app/database/connection.py`, `app/database/collections.py`, and `app/database/__init__.py`.
6. **Data models & API schemas** — Implemented `app/models/device.py`, `app/models/health_reading.py`, `app/schemas/device.py`, and `app/schemas/health_reading.py`.

### Backend APIs, ML, WebSockets & Tests
7. **Anomaly detection model & prediction API** — Built `ml/` (`train.py`, `evaluate.py`, `src/*`, `saved_models/*`) and `/api/predictions` endpoints (`app/api/predictions.py`, `app/services/prediction_service.py`, `app/schemas/prediction.py`).
8. **Device registration & status APIs** — Implemented `app/api/devices.py`.
9. **Readings ingestion & history APIs** — Implemented `app/api/readings.py` and `app/services/reading_service.py`.
10. **Health Alert system** — Implemented `app/services/alert_service.py`.
11. **Live WebSocket updates** — Implemented `app/websocket/manager.py` and mounted WebSocket streaming in `app/api/readings.py`.
12. **Main server wiring** — Wired MongoDB lifecycle, `devices` / `readings` / `predictions` routers, and WebSocket manager into `app/main.py`.
13. **ML prediction tests** — Implemented `tests/test_predictions.py`.
14. **Devices & readings tests** — Implemented `tests/test_devices.py` and `tests/test_readings.py`.

---

## 2. Still To Be Done (5 Items)

### Hardware & Real Data
15. **Connect remaining vital sensors** — Wire and test the Heart Rate/`SpO2` (`MAX30102`) and Body Temperature (`DS18B20`) sensors with the ESP32.
16. **Send live ESP32 data over Wi-Fi** — Program the ESP32 to send JSON batches (heart rate, `SpO2`, temperature, 50-sample ECG buffer, leads status) to `POST /api/readings`.
17. **Test ML model with the 4 people's ECG samples** — Run the real ECG recordings in `sample_data_and_plots/csv_data/` through `ml/src/feature_extraction.py` and `ml/evaluate.py` to check peak detection, RMS values, and anomaly scores (the model is currently trained on synthetic data).

### Backend Refinement & Documentation
18. **Support multiple devices at once** — Update `app/services/prediction_service.py` so each ESP32 `device_id` maintains its own 30-sample rolling buffer instead of sharing one global `deque`.
19. **Update root README instructions** — Update the root `README.md` with `.env` configuration, MongoDB Atlas setup, `/api/devices`, `/api/readings`, WebSocket endpoints, `sample_data_and_plots/`, and accurate directory paths.
