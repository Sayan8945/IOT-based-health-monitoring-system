"""Automatic Project Progress Checker & Tracker Updater.

Scans the IOT-based-health-monitoring-system codebase to detect which backend,
ML, database, API, WebSocket, and test modules are implemented vs. empty/partial,
and updates:
  - things_to_be_done.csv
  - things_to_be_done.xlsx
  - things_to_be_done.txt

Run from anywhere:
  python "Workflow Folder/update_tracker.py"
"""

from __future__ import annotations

import ast
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import xlsxwriter

WORKFLOW_DIR = Path(__file__).resolve().parent
ROOT_DIR = WORKFLOW_DIR.parent

CSV_PATH = WORKFLOW_DIR / "things_to_be_done.csv"
XLSX_PATH = WORKFLOW_DIR / "things_to_be_done.xlsx"
TXT_PATH = WORKFLOW_DIR / "things_to_be_done.txt"

HEADERS = ["#", "Area", "What Needs to Be Done", "Simple Explanation", "Status", "Where in Code / Hardware"]


def _read_text(rel_path: str) -> str:
    path = ROOT_DIR / rel_path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def has_python_code(rel_path: str) -> bool:
    """Return True if a Python file exists and defines at least one non-trivial statement."""
    text = _read_text(rel_path).strip()
    if not text:
        return False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return len(text) > 0

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        return True
    return False


def has_python_tests(rel_path: str) -> bool:
    """Return True if a test file defines at least one test_* function."""
    text = _read_text(rel_path)
    if not text.strip():
        return False
    return bool(re.search(r"^\s*(?:async\s+)?def\s+test_", text, re.MULTILINE))


def file_nonempty(rel_path: str) -> bool:
    """Return True if a non-Python or binary file exists and has size > 0."""
    path = ROOT_DIR / rel_path
    return path.is_file() and path.stat().st_size > 0


def text_has_any(rel_path: str, patterns: List[str]) -> bool:
    text = _read_text(rel_path)
    return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)


def group_status(checks: List[bool]) -> str:
    """Return Done if all checks pass, In Progress if some pass, else To Do."""
    if all(checks):
        return "Done"
    if any(checks):
        return "In Progress"
    return "To Do"


def load_existing_statuses() -> Dict[int, str]:
    """Read existing statuses from CSV so manual hardware statuses are preserved."""
    statuses: Dict[int, str] = {}
    if not CSV_PATH.is_file():
        return statuses
    try:
        with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                num_str = (row.get("#") or "").strip()
                status = (row.get("Status") or "").strip()
                if num_str.isdigit() and status in {"Done", "In Progress", "To Do"}:
                    statuses[int(num_str)] = status
    except Exception:
        pass
    return statuses


# --- Individual check functions ---

def check_ml_pipeline() -> str:
    required_py = [
        "ml/train.py",
        "ml/evaluate.py",
        "ml/src/data_generator.py",
        "ml/src/feature_extraction.py",
        "app/api/predictions.py",
        "app/services/prediction_service.py",
        "app/schemas/prediction.py",
    ]
    required_artifacts = [
        "ml/saved_models/isolation_forest.joblib",
        "ml/saved_models/scaler.joblib",
        "ml/saved_models/model_metadata.json",
    ]
    checks = [has_python_code(p) for p in required_py] + [file_nonempty(p) for p in required_artifacts]
    return group_status(checks)


def check_ml_tests() -> str:
    return "Done" if has_python_tests("tests/test_predictions.py") else "To Do"


def check_real_samples_collected(manual: Dict[int, str]) -> str:
    csv_dir = ROOT_DIR / "sample_data_and_plots" / "csv_data"
    if csv_dir.is_dir() and len(list(csv_dir.glob("*.csv"))) >= 4:
        return "Done"
    return manual.get(2, "Done")


def check_real_samples_ml_test(manual: Dict[int, str]) -> str:
    eval_mentions_real = text_has_any("ml/evaluate.py", [r"sample_data_and_plots", r"real_sample", r"csv_data"])
    if eval_mentions_real:
        return "Done"
    return manual.get(7, "To Do")


def check_env_and_packages() -> str:
    env_ok = file_nonempty(".env.example")
    config_ok = has_python_code("app/core/config.py")
    req_text = _read_text("requirements.txt")
    db_pkg_ok = bool(re.search(r"\b(motor|pymongo)\b", req_text, re.IGNORECASE))
    return group_status([env_ok, config_ok, db_pkg_ok])


def check_security() -> str:
    return "Done" if has_python_code("app/core/security.py") else "To Do"


def check_database() -> str:
    checks = [
        has_python_code("app/database/connection.py"),
        has_python_code("app/database/collections.py"),
    ]
    return group_status(checks)


def check_models_and_schemas() -> str:
    checks = [
        has_python_code("app/models/device.py"),
        has_python_code("app/models/health_reading.py"),
        has_python_code("app/schemas/device.py"),
        has_python_code("app/schemas/health_reading.py"),
    ]
    return group_status(checks)


def check_devices_api() -> str:
    if has_python_code("app/api/devices.py") and text_has_any("app/api/devices.py", [r"APIRouter", r"@router\."]):
        return "Done"
    if has_python_code("app/api/devices.py"):
        return "In Progress"
    return "To Do"


def check_readings_api() -> str:
    api_ok = has_python_code("app/api/readings.py") and text_has_any("app/api/readings.py", [r"APIRouter", r"@router\."])
    svc_ok = has_python_code("app/services/reading_service.py")
    return group_status([api_ok, svc_ok])


def check_alerts() -> str:
    return "Done" if has_python_code("app/services/alert_service.py") else "To Do"


def check_multi_device_predictions() -> str:
    text = _read_text("app/services/prediction_service.py")
    if not text:
        return "To Do"
    has_device_arg = bool(re.search(r"def\s+predict\([^)]*device_id", text, re.DOTALL))
    has_buffers_map = bool(re.search(r"self\.buffers\b|defaultdict", text))
    if has_device_arg and has_buffers_map:
        return "Done"
    if has_device_arg or has_buffers_map:
        return "In Progress"
    return "To Do"


def check_websockets() -> str:
    return "Done" if has_python_code("app/websocket/manager.py") else "To Do"


def check_main_wiring() -> str:
    main_text = _read_text("app/main.py")
    readings_text = _read_text("app/api/readings.py")
    has_devices = bool(re.search(r"devices_router|devices", main_text))
    has_readings = bool(re.search(r"readings_router|readings", main_text))
    has_ws = bool(re.search(r"websocket|get_ws_manager", main_text, re.IGNORECASE)) or bool(
        re.search(r"@router\.websocket", readings_text)
    )
    has_db = bool(re.search(r"connect_to_mongo|get_db_manager|mongo|database", main_text, re.IGNORECASE))
    return group_status([has_devices, has_readings, has_ws, has_db])


def check_device_reading_tests() -> str:
    checks = [
        has_python_tests("tests/test_devices.py"),
        has_python_tests("tests/test_readings.py"),
    ]
    return group_status(checks)


def check_readme_updated() -> str:
    text = _read_text("README.md")
    if not text:
        return "To Do"
    has_new_endpoints = bool(re.search(r"/api/devices|/api/readings|/ws", text))
    has_env_docs = bool(re.search(r"\.env|MONGODB", text))
    return group_status([has_new_endpoints, has_env_docs])


def build_items() -> List[Tuple[int, str, str, str, str, str]]:
    """Inspect the codebase and return all tracker items with live statuses."""
    manual = load_existing_statuses()

    specs: List[Tuple[int, str, str, str, Callable[[], str], str]] = [
        (1, "Hardware", "ECG hardware setup",
         "Built and tested the ECG sensor hardware (ESP32 + AD8232).",
         lambda: manual.get(1, "Done"), "Hardware (ESP32 + AD8232)"),
        (2, "ML & Real Data", "Collect 4 people's ECG samples",
         "Collected real ECG sample recordings from 4 people for testing (stored in sample_data_and_plots/).",
         lambda: check_real_samples_collected(manual), "sample_data_and_plots/ (csv_data, txt_data, plots)"),
        (3, "Backend & ML", "Anomaly detection model & prediction API",
         "Built the ML model, feature extraction, and /api/predictions endpoints for real-time scoring.",
         check_ml_pipeline, "ml/, app/api/predictions.py, app/services/prediction_service.py, app/schemas/prediction.py"),
        (4, "Testing & Docs", "ML prediction tests",
         "Wrote automated tests verifying feature extraction, ECG rhythm labels, and prediction endpoints.",
         check_ml_tests, "tests/test_predictions.py"),
        (5, "Hardware", "Connect remaining vital sensors",
         "Wire and test Heart Rate/SpO2 (MAX30102) and Body Temperature (DS18B20) sensors with the ESP32.",
         lambda: manual.get(5, "To Do"), "Hardware (ESP32 + MAX30102, DS18B20)"),
        (6, "Hardware", "Send live ESP32 data over Wi-Fi",
         "Program the ESP32 to send JSON sensor batches (heart rate, SpO2, temperature, 50 ECG points, leads status) to the backend.",
         lambda: manual.get(6, "To Do"), "ESP32 Firmware -> FastAPI"),
        (7, "ML & Real Data", "Test ML model with 4 people's ECG samples",
         "Run the 4 collected ECG samples through the ML pipeline to verify peak detection, RMS, and scores (model currently uses synthetic data).",
         lambda: check_real_samples_ml_test(manual), "ml/evaluate.py, ml/src/feature_extraction.py"),
        (8, "Setup & Security", "Add environment config & database packages",
         "Populate .env.example, load settings in config.py, and add MongoDB driver (pymongo[srv]) to requirements.txt.",
         check_env_and_packages, ".env.example, app/core/config.py, requirements.txt"),
        (9, "Setup & Security", "Protect API with device keys",
         "Add API key/token checks so only authorized ESP32 devices and dashboard clients can send or read data.",
         check_security, "app/core/security.py, app/core/__init__.py"),
        (10, "Database", "Connect backend to MongoDB",
         "Set up the MongoDB Atlas connection and create database collections and indexes for devices, health readings, and alerts.",
         check_database, "app/database/connection.py, app/database/collections.py, app/database/__init__.py"),
        (11, "Database", "Define data formats for saving records",
         "Define what a Device record and a Health Reading record look like in MongoDB and in API requests/responses.",
         check_models_and_schemas, "app/models/device.py, app/models/health_reading.py, app/schemas/device.py, app/schemas/health_reading.py"),
        (12, "Backend & ML", "Build Device registration & status APIs",
         "Create endpoints to register ESP32 devices, list them, and track when each device was last online.",
         check_devices_api, "app/api/devices.py"),
        (13, "Backend & ML", "Build Readings save & history APIs",
         "Create endpoints to receive live sensor readings, save them to MongoDB, run ML checks, and fetch past readings for charts.",
         check_readings_api, "app/api/readings.py, app/services/reading_service.py"),
        (14, "Backend & ML", "Build Health Alert system",
         "Automatically detect abnormal vitals or ML anomalies, save an alert record, and avoid duplicate alert spam.",
         check_alerts, "app/services/alert_service.py"),
        (15, "Backend & ML", "Support multiple devices at once",
         "Update prediction_service.py so each ESP32 device gets its own 30-sample rolling history instead of sharing one global buffer.",
         check_multi_device_predictions, "app/services/prediction_service.py"),
        (16, "Live Dashboard", "Add live WebSocket updates",
         "Set up WebSockets so new vitals, ML scores, and alerts appear instantly on the React dashboard without refreshing.",
         check_websockets, "app/websocket/manager.py, app/websocket/__init__.py"),
        (17, "Backend & ML", "Connect all routes in main server file",
         "Wire MongoDB startup/shutdown, device & reading routers, WebSockets, package exports, and config-based CORS into main.py.",
         check_main_wiring, "app/main.py, app/api/__init__.py, app/services/__init__.py"),
        (18, "Testing & Docs", "Write tests for devices & readings",
         "Add automated tests covering device management, saving readings, alerts, and live WebSocket updates.",
         check_device_reading_tests, "tests/test_devices.py, tests/test_readings.py, tests/__init__.py"),
        (19, "Testing & Docs", "Update root README instructions",
         "Update root README.md with .env setup, MongoDB steps, new API/WebSocket endpoints, and accurate folder paths.",
         check_readme_updated, "README.md"),
    ]

    return [(num, area, title, desc, fn(), loc) for num, area, title, desc, fn, loc in specs]


def write_csv(items: List[Tuple[int, str, str, str, str, str]]) -> None:
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(items)


def write_xlsx(items: List[Tuple[int, str, str, str, str, str]], updated_date: str) -> None:
    wb = xlsxwriter.Workbook(str(XLSX_PATH))

    title_fmt = wb.add_format({"bold": True, "font_size": 15, "font_color": "#1F4E78"})
    subtitle_fmt = wb.add_format({"italic": True, "font_size": 10, "font_color": "#595959"})
    section_fmt = wb.add_format({"bold": True, "font_size": 11, "font_color": "#1F4E78", "bottom": 1, "bottom_color": "#1F4E78"})
    header_fmt = wb.add_format({
        "bold": True, "font_size": 11, "font_color": "#FFFFFF",
        "bg_color": "#1F4E78", "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True
    })
    cell_fmt = wb.add_format({"border": 1, "valign": "vcenter", "text_wrap": True, "font_size": 10})
    center_fmt = wb.add_format({"border": 1, "valign": "vcenter", "align": "center", "text_wrap": True, "font_size": 10})
    bold_fmt = wb.add_format({"border": 1, "valign": "vcenter", "bold": True, "text_wrap": True, "font_size": 10})

    status_formats = {
        "Done": wb.add_format({"border": 1, "valign": "vcenter", "align": "center", "bold": True, "bg_color": "#E2EFDA", "font_color": "#274E13", "font_size": 10}),
        "In Progress": wb.add_format({"border": 1, "valign": "vcenter", "align": "center", "bold": True, "bg_color": "#FFE699", "font_color": "#9C6500", "font_size": 10}),
        "To Do": wb.add_format({"border": 1, "valign": "vcenter", "align": "center", "bold": True, "bg_color": "#D9E1F2", "font_color": "#1F4E78", "font_size": 10}),
    }

    # Sheet 1: Checklist
    ws = wb.add_worksheet("Checklist")
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, len(items), len(HEADERS) - 1)

    col_widths = [6, 18, 36, 58, 14, 42]
    ws.set_row(0, 26)
    for c, (h, w) in enumerate(zip(HEADERS, col_widths)):
        ws.write(0, c, h, header_fmt)
        ws.set_column(c, c, w)

    for r_idx, row in enumerate(items, start=1):
        ws.set_row(r_idx, 38)
        ws.write(r_idx, 0, row[0], center_fmt)
        ws.write(r_idx, 1, row[1], cell_fmt)
        ws.write(r_idx, 2, row[2], bold_fmt)
        ws.write(r_idx, 3, row[3], cell_fmt)
        ws.write(r_idx, 4, row[4], status_formats.get(row[4], status_formats["To Do"]))
        ws.write(r_idx, 5, row[5], cell_fmt)

    # Sheet 2: Overview
    ws_ov = wb.add_worksheet("Overview")
    ws_ov.set_column(0, 0, 28)
    ws_ov.set_column(1, 4, 14)

    ws_ov.write(0, 0, "SmartHealth IoT Health Monitoring - Simple Project Tracker", title_fmt)
    ws_ov.write(1, 0, f"Auto-checked on: {updated_date} | Generated by Workflow Folder/update_tracker.py", subtitle_fmt)

    ws_ov.write(3, 0, "Overall Progress", section_fmt)
    ws_ov.write(4, 0, "Status", header_fmt)
    ws_ov.write(4, 1, "Count", header_fmt)
    ws_ov.write(5, 0, "Done", status_formats["Done"])
    ws_ov.write_formula(5, 1, f'=COUNTIF(Checklist!E2:E{len(items)+1}, "Done")', center_fmt)
    ws_ov.write(6, 0, "In Progress", status_formats["In Progress"])
    ws_ov.write_formula(6, 1, f'=COUNTIF(Checklist!E2:E{len(items)+1}, "In Progress")', center_fmt)
    ws_ov.write(7, 0, "To Do", status_formats["To Do"])
    ws_ov.write_formula(7, 1, f'=COUNTIF(Checklist!E2:E{len(items)+1}, "To Do")', center_fmt)
    ws_ov.write(8, 0, "Total Items", bold_fmt)
    ws_ov.write_formula(8, 1, "=SUM(B6:B8)", bold_fmt)

    ws_ov.write(10, 0, "Progress by Area", section_fmt)
    ws_ov.write(11, 0, "Area", header_fmt)
    ws_ov.write(11, 1, "Done", header_fmt)
    ws_ov.write(11, 2, "In Progress", header_fmt)
    ws_ov.write(11, 3, "To Do", header_fmt)
    ws_ov.write(11, 4, "Total", header_fmt)

    areas = list(dict.fromkeys(row[1] for row in items))
    for idx, area in enumerate(areas, start=12):
        ws_ov.write(idx, 0, area, cell_fmt)
        ws_ov.write_formula(idx, 1, f'=COUNTIFS(Checklist!B2:B{len(items)+1}, A{idx+1}, Checklist!E2:E{len(items)+1}, "Done")', center_fmt)
        ws_ov.write_formula(idx, 2, f'=COUNTIFS(Checklist!B2:B{len(items)+1}, A{idx+1}, Checklist!E2:E{len(items)+1}, "In Progress")', center_fmt)
        ws_ov.write_formula(idx, 3, f'=COUNTIFS(Checklist!B2:B{len(items)+1}, A{idx+1}, Checklist!E2:E{len(items)+1}, "To Do")', center_fmt)
        ws_ov.write_formula(idx, 4, f"=SUM(B{idx+1}:D{idx+1})", center_fmt)

    tot_row = 12 + len(areas)
    ws_ov.write(tot_row, 0, "Total", bold_fmt)
    ws_ov.write_formula(tot_row, 1, f"=SUM(B13:B{tot_row})", bold_fmt)
    ws_ov.write_formula(tot_row, 2, f"=SUM(C13:C{tot_row})", bold_fmt)
    ws_ov.write_formula(tot_row, 3, f"=SUM(D13:D{tot_row})", bold_fmt)
    ws_ov.write_formula(tot_row, 4, f"=SUM(E13:E{tot_row})", bold_fmt)

    wb.close()


def write_txt(items: List[Tuple[int, str, str, str, str, str]], updated_date: str) -> None:
    done_items = [row for row in items if row[4] == "Done"]
    in_progress_items = [row for row in items if row[4] == "In Progress"]
    todo_items = [row for row in items if row[4] == "To Do"]

    lines: List[str] = [
        "=" * 80,
        "SMARTHEALTH IOT HEALTH MONITORING - PROJECT STATUS & THINGS TO BE DONE",
        f"Updated: {updated_date} (auto-generated by Workflow Folder/update_tracker.py)",
        "=" * 80,
        "",
        f"SUMMARY: {len(done_items)} Done | {len(in_progress_items)} In Progress | {len(todo_items)} To Do (Total: {len(items)})",
        "",
        "ALREADY COMPLETED (DONE)",
        "-" * 24,
    ]

    for num, area, title, desc, _status, loc in done_items:
        lines.append(f"[x] {num}. [{area}] {title}")
        lines.append(f"       {desc}")
        lines.append(f"       Where: {loc}")
        lines.append("")

    if in_progress_items:
        lines.append("-" * 80)
        lines.append("IN PROGRESS (PARTIALLY IMPLEMENTED)")
        lines.append("-" * 35)
        for num, area, title, desc, _status, loc in in_progress_items:
            lines.append(f"[~] {num}. [{area}] {title}")
            lines.append(f"       {desc}")
            lines.append(f"       Where: {loc}")
            lines.append("")

    lines.append("-" * 80)
    lines.append("STILL TO BE DONE (IN SIMPLE TERMS)")
    lines.append("-" * 80)

    current_area = None
    for num, area, title, desc, _status, loc in todo_items:
        if area != current_area:
            current_area = area
            lines.append("")
            lines.append(area.upper())
        lines.append(f"[ ] {num}. {title}")
        lines.append(f"       {desc}")
        lines.append(f"       Where: {loc}")

    lines.append("")
    TXT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    updated_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    items = build_items()

    write_csv(items)
    write_xlsx(items, updated_date)
    write_txt(items, updated_date)

    counts = {s: sum(1 for row in items if row[4] == s) for s in ("Done", "In Progress", "To Do")}
    print(f"Codebase checked at {ROOT_DIR}")
    print(f"Status summary -> Done: {counts['Done']}, In Progress: {counts['In Progress']}, To Do: {counts['To Do']}")
    print(f"Updated:\n  - {CSV_PATH}\n  - {XLSX_PATH}\n  - {TXT_PATH}")


if __name__ == "__main__":
    main()
