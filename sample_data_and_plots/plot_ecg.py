"""Standalone ECG CSV Plotter and Excel Chart Exporter.

Reads CSV files from `csv_data/` (or any specified CSV path) and generates:
1. High-resolution medical millimeter-grid ECG plot (.png) in `plots/`
2. Optional interactive Excel workbook (.xlsx) with embedded line chart in `plots/`

Usage:
    python plot_ecg.py                           # Plots newest CSV in csv_data/
    python plot_ecg.py csv_data/ECG_Test_1.csv   # Plots a specific CSV file
    python plot_ecg.py --excel                   # Creates both PNG image and Excel chart
    python plot_ecg.py --all --excel             # Processes every CSV in csv_data/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "csv_data"
PLOTS_DIR = BASE_DIR / "plots"


def load_ecg_data(file_path: Path | str) -> tuple[np.ndarray, np.ndarray | None]:
    """Load ECG amplitude and time (converted to seconds) from a CSV file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"CSV file {path} is empty.")

    ecg_col = None
    time_col = None

    col_names_lower = [str(c).strip().lower() for c in df.columns]
    for idx, name in enumerate(col_names_lower):
        if name in [
            "amplitude",
            "voltage_mv",
            "ecg",
            "ecg_lead_1",
            "lead1",
            "voltage",
            "mv",
            "val",
            "signal",
            "reading",
        ]:
            if ecg_col is None or (name == "amplitude" and str(ecg_col).strip().lower() != "amplitude"):
                ecg_col = df.columns[idx]
        elif name in [
            "milliseconds",
            "millis",
            "ms",
            "time_ms",
            "time",
            "timestamp",
            "sec",
            "seconds",
            "t",
        ]:
            time_col = df.columns[idx]

    if ecg_col is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            ecg_col = numeric_cols[0]
        else:
            df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors="coerce")
            ecg_col = df.columns[0]

    ecg_signal = df[ecg_col].dropna().values.astype(np.float64)

    time_arr = None
    if time_col is not None:
        try:
            raw_time = df[time_col].dropna().values.astype(np.float64)
            col_lower = str(time_col).lower()
            if "ms" in col_lower or "milli" in col_lower or (len(raw_time) > 1 and raw_time[1] >= 1.0):
                time_arr = raw_time / 1000.0
            else:
                time_arr = raw_time
            time_arr = time_arr[: len(ecg_signal)]
        except Exception:
            time_arr = None

    return ecg_signal, time_arr


def plot_ecg(
    csv_path: str | Path,
    fs: int = 100,
    duration_sec: float | None = 10.0,
    save_path: str | Path | None = None,
    show_peaks: bool = True,
    interactive: bool = True,
) -> Path:
    """Generate medical-standard Lead-I ECG waveform plot (.png)."""
    csv_p = Path(csv_path)
    signal, custom_time = load_ecg_data(csv_p)

    total_samples = len(signal)
    if total_samples == 0:
        raise ValueError("No valid numeric samples found in CSV.")

    max_samples = min(total_samples, int(duration_sec * fs)) if (duration_sec and duration_sec > 0) else total_samples
    signal_slice = signal[:max_samples]

    if custom_time is not None and len(custom_time) >= max_samples:
        time_slice = custom_time[:max_samples]
    else:
        time_slice = np.arange(max_samples) / float(fs)

    min_distance = max(10, int(0.35 * fs))
    signal_range = float(np.ptp(signal_slice))
    prominence = max(0.1, signal_range * 0.25) if signal_range > 0 else 0.2

    peaks, _ = find_peaks(signal_slice, distance=min_distance, prominence=prominence)

    hr_text = ""
    if len(peaks) >= 2:
        rr_intervals = np.diff(time_slice[peaks])
        mean_rr = np.mean(rr_intervals)
        if mean_rr > 0:
            bpm = round(60.0 / mean_rr, 1)
            hr_text = f" | Estimated HR: {bpm} BPM"

    fig, ax = plt.subplots(figsize=(14, 4.8), dpi=120, facecolor="#fafafa")
    ax.set_facecolor("#ffffff")

    ax.minorticks_on()
    ax.grid(which="major", linestyle="-", linewidth=0.7, color="#f0b8b8", alpha=0.8)
    ax.grid(which="minor", linestyle=":", linewidth=0.4, color="#fcdada", alpha=0.8)

    ax.plot(
        time_slice,
        signal_slice,
        color="#d32f2f",
        linewidth=1.2,
        label=f"ECG Signal (fs={fs} Hz{hr_text})",
        zorder=3,
    )

    if show_peaks and len(peaks) > 0:
        ax.scatter(
            time_slice[peaks],
            signal_slice[peaks],
            color="#1976d2",
            s=45,
            edgecolors="#0d47a1",
            linewidth=1.0,
            label=f"R-peaks ({len(peaks)} detected)",
            zorder=4,
        )

    ax.set_title(
        f"Electrocardiogram (ECG) Recording — {csv_p.name}",
        fontsize=13,
        fontweight="bold",
        pad=10,
        color="#212121",
    )
    ax.set_xlabel("Time (seconds)", fontsize=11, color="#333333")
    ax.set_ylabel("Amplitude (ADC / mV)", fontsize=11, color="#333333")

    for spine in ax.spines.values():
        spine.set_color("#cccccc")
        spine.set_linewidth(0.8)

    ax.legend(loc="upper right", framealpha=0.9, facecolor="#ffffff", edgecolor="#e0e0e0")
    plt.tight_layout()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(save_path) if save_path else (PLOTS_DIR / f"{csv_p.stem}_plot.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[+] ECG plot saved to: {out_path}")

    if interactive and sys.stdout.isatty():
        try:
            plt.show()
        except Exception:
            pass
    else:
        plt.close(fig)

    return out_path


def export_to_excel(
    csv_path: str | Path,
    output_excel: str | Path | None = None,
    fs: int = 100,
    max_samples: int = 600,
) -> Path:
    """Export ECG data to an Excel (.xlsx) workbook with a native interactive line chart."""
    csv_p = Path(csv_path)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(output_excel) if output_excel else (PLOTS_DIR / f"{csv_p.stem}_waveform.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import openpyxl
        from openpyxl.chart import LineChart, Reference
    except ImportError:
        print("[!] openpyxl is required for Excel export. Install via: pip install openpyxl")
        return out_path

    signal, custom_time = load_ecg_data(csv_p)
    n = min(len(signal), max_samples)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ECG_Data"

    ws.append(["Milliseconds (ms)", "Time (s)", "ECG Amplitude"])

    for i in range(n):
        t_sec = round(custom_time[i], 3) if (custom_time is not None and i < len(custom_time)) else round(i / float(fs), 3)
        t_ms = int(round(t_sec * 1000))
        ws.append([t_ms, t_sec, float(signal[i])])

    chart = LineChart()
    chart.title = f"ECG Waveform — {csv_p.name}"
    chart.style = 13
    chart.y_axis.title = "Amplitude"
    chart.x_axis.title = "Time (ms)"
    chart.width = 24
    chart.height = 12

    data_ref = Reference(ws, min_col=3, min_row=1, max_row=n + 1)
    cats_ref = Reference(ws, min_col=1, min_row=2, max_row=n + 1)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    ws.add_chart(chart, "E2")

    wb.save(out_path)
    print(f"[+] Excel workbook with embedded ECG graph created: {out_path}")
    return out_path


def resolve_input_csvs(file_arg: str | None, process_all: bool) -> list[Path]:
    """Locate target CSV file(s) from explicit path or `csv_data/` directory."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    if file_arg:
        candidate = Path(file_arg)
        if candidate.exists():
            return [candidate]
        in_csv_dir = CSV_DIR / file_arg
        if in_csv_dir.exists():
            return [in_csv_dir]
        raise FileNotFoundError(f"CSV file not found: {file_arg}")

    csv_files = sorted(CSV_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csv_files:
        raise FileNotFoundError(
            f"No .csv files found in {CSV_DIR}. Put raw .txt files in txt_data/ and run: python txt_to_csv.py"
        )

    return csv_files if process_all else [csv_files[0]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot ECG CSV data and export to PNG / Excel.")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path or filename of CSV in csv_data/ (defaults to newest CSV in csv_data/)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot all CSV files inside csv_data/",
    )
    parser.add_argument(
        "--fs",
        type=int,
        default=100,
        help="Sampling frequency in Hz (default: 100 Hz)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Seconds to display in PNG plot (default: 10.0s; 0 for entire file)",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Custom output .png path (defaults to plots/<name>_plot.png)",
    )
    parser.add_argument(
        "--no-peaks",
        action="store_true",
        help="Disable automatic R-peak markers",
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Also export an Excel (.xlsx) workbook with an embedded interactive chart to plots/",
    )

    args = parser.parse_args()
    targets = resolve_input_csvs(args.file, args.all)

    for csv_file in targets:
        print(f"[*] Reading ECG data from: {csv_file}")
        plot_ecg(
            csv_path=csv_file,
            fs=args.fs,
            duration_sec=args.duration if args.duration > 0 else None,
            save_path=args.save if len(targets) == 1 else None,
            show_peaks=not args.no_peaks,
            interactive=not args.all,
        )
        if args.excel:
            export_to_excel(csv_path=csv_file, fs=args.fs)


if __name__ == "__main__":
    main()
