"""Interactive and High-Resolution ECG Plotter for CSV Data.

Supports single-column or multi-column CSV files, custom sampling frequencies (default 100 Hz),
calibrated ECG millimeter grid, and automatic R-peak detection with estimated Heart Rate (BPM).

Usage:
    python plot_ecg.py                     # Plots ecg_data.csv or sample_ecg.csv
    python plot_ecg.py my_ecg.csv          # Plots custom CSV file
    python plot_ecg.py my_ecg.csv --fs 250 # Custom sampling rate (e.g. 250 Hz)
    python plot_ecg.py --save plot.png     # Save to file
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks


def load_ecg_data(file_path: Path | str) -> tuple[np.ndarray, np.ndarray | None]:
    """Load ECG data from a CSV file.

    Handles header/no-header, single-column, and time/value column formats.
    Returns (ecg_signal, time_array_or_none).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    # Read CSV, trying with and without header detection
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise ValueError(f"Could not parse CSV file {path}: {e}")

    # If empty
    if df.empty:
        raise ValueError(f"CSV file {path} is empty.")

    # Find ECG column
    ecg_col = None
    time_col = None

    # Check common column names
    col_names_lower = [str(c).strip().lower() for c in df.columns]
    for idx, name in enumerate(col_names_lower):
        if name in ["ecg", "ecg_lead_1", "lead1", "voltage", "mv", "val", "signal", "reading"]:
            ecg_col = df.columns[idx]
        elif name in ["time", "timestamp", "sec", "seconds", "t"]:
            time_col = df.columns[idx]

    # If not found by name, pick the first numeric column for ECG
    if ecg_col is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            ecg_col = numeric_cols[0]
        else:
            # Try converting first column to float
            df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors="coerce")
            ecg_col = df.columns[0]

    ecg_signal = df[ecg_col].dropna().values.astype(np.float64)

    time_arr = None
    if time_col is not None:
        try:
            time_arr = df[time_col].dropna().values.astype(np.float64)
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
    """Generate medical-standard Lead-I ECG waveform plot."""
    signal, custom_time = load_ecg_data(csv_path)

    total_samples = len(signal)
    if total_samples == 0:
        raise ValueError("No valid numeric samples found in CSV.")

    # Determine slice range
    if duration_sec is not None and duration_sec > 0:
        max_samples = min(total_samples, int(duration_sec * fs))
    else:
        max_samples = total_samples

    signal_slice = signal[:max_samples]

    # Time array in seconds
    if custom_time is not None and len(custom_time) >= max_samples:
        time_slice = custom_time[:max_samples]
    else:
        time_slice = np.arange(max_samples) / float(fs)

    # Detect R-peaks using scipy find_peaks
    # Baseline peak distance corresponds to at least ~0.35s (170 bpm max)
    min_distance = max(10, int(0.35 * fs))
    signal_range = float(np.ptp(signal_slice))
    prominence = max(0.1, signal_range * 0.25) if signal_range > 0 else 0.2

    peaks, _ = find_peaks(signal_slice, distance=min_distance, prominence=prominence)

    # Estimate Heart Rate if at least 2 peaks found
    hr_text = ""
    if len(peaks) >= 2:
        rr_intervals = np.diff(time_slice[peaks])
        mean_rr = np.mean(rr_intervals)
        if mean_rr > 0:
            bpm = round(60.0 / mean_rr, 1)
            hr_text = f" | Estimated HR: {bpm} BPM"

    # Setup figure with ECG medical styling
    fig, ax = plt.subplots(figsize=(14, 4.8), dpi=120, facecolor="#fafafa")
    ax.set_facecolor("#ffffff")

    # ECG Millimeter Grid (major and minor gridlines)
    ax.minorticks_on()
    ax.grid(which="major", linestyle="-", linewidth=0.7, color="#f0b8b8", alpha=0.8)
    ax.grid(which="minor", linestyle=":", linewidth=0.4, color="#fcdada", alpha=0.8)

    # Plot ECG Waveform
    ax.plot(
        time_slice,
        signal_slice,
        color="#d32f2f",
        linewidth=1.2,
        label=f"ECG Signal (fs={fs} Hz{hr_text})",
        zorder=3,
    )

    # Mark detected R-peaks
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

    # Titles and Labels
    file_name = Path(csv_path).name
    ax.set_title(
        f"Electrocardiogram (ECG) Recording — {file_name}",
        fontsize=13,
        fontweight="bold",
        pad=10,
        color="#212121",
    )
    ax.set_xlabel("Time (seconds)", fontsize=11, fontweight="medium", color="#333333")
    ax.set_ylabel("Amplitude (mV / ADC units)", fontsize=11, fontweight="medium", color="#333333")

    # Aesthetics
    for spine in ax.spines.values():
        spine.set_color("#cccccc")
        spine.set_linewidth(0.8)

    ax.legend(loc="upper right", framealpha=0.9, facecolor="#ffffff", edgecolor="#e0e0e0")
    plt.tight_layout()

    # Save to file
    if save_path is None:
        save_path = Path("ecg_plot.png")
    else:
        save_path = Path(save_path)

    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"[+] ECG plot saved to: {save_path.resolve()}")

    if interactive and sys.stdout.isatty():
        try:
            plt.show()
        except Exception:
            pass
    else:
        plt.close(fig)

    return save_path


def export_to_excel(
    csv_path: str | Path,
    output_excel: str | Path = "ecg_waveform.xlsx",
    fs: int = 100,
    max_samples: int = 600,
) -> Path:
    """Export ECG data to an Excel (.xlsx) workbook with a native interactive line chart embedded."""
    try:
        import openpyxl
        from openpyxl.chart import LineChart, Reference
    except ImportError:
        print("[!] openpyxl is required for Excel export. Install via: pip install openpyxl")
        return Path(output_excel)

    signal, custom_time = load_ecg_data(csv_path)
    n = min(len(signal), max_samples)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ECG_Data"

    # Header
    ws.append(["Time (seconds)", "ECG Amplitude (mV)"])

    # Rows
    for i in range(n):
        t = round(custom_time[i], 3) if custom_time is not None and i < len(custom_time) else round(i / float(fs), 3)
        ws.append([t, float(signal[i])])

    # Build Native Excel Line Chart
    chart = LineChart()
    chart.title = f"ECG Waveform — {Path(csv_path).name}"
    chart.style = 13
    chart.y_axis.title = "Amplitude (mV / ADC)"
    chart.x_axis.title = "Time (seconds)"
    chart.width = 24
    chart.height = 12

    data_ref = Reference(ws, min_col=2, min_row=1, max_row=n + 1)
    cats_ref = Reference(ws, min_col=1, min_row=2, max_row=n + 1)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    # Place chart next to the tabular data
    ws.add_chart(chart, "D2")

    out_path = Path(output_excel)
    wb.save(out_path)
    print(f"[+] Excel workbook with embedded ECG graph created: {out_path.resolve()}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Plot ECG CSV data with clinical millimeter grid.")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to the ECG CSV file (defaults to ecg_data.csv or sample_ecg.csv)",
    )
    parser.add_argument(
        "--fs",
        type=int,
        default=100,
        help="Sampling frequency in Hz (default: 100 Hz for ESP32/AD8232)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Number of seconds to display (default: 10.0s; 0 for all)",
    )
    parser.add_argument(
        "--save",
        type=str,
        default="ecg_plot.png",
        help="Output image file path (default: ecg_plot.png)",
    )
    parser.add_argument(
        "--no-peaks",
        action="store_true",
        help="Disable automatic R-peak markers",
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Also export to an Excel (.xlsx) file with a native interactive ECG line chart embedded",
    )

    args = parser.parse_args()

    # Determine input file
    csv_file = args.file
    if csv_file is None:
        # Check standard default names
        for candidate in ["ecg_data.csv", "sample_ecg.csv", "ecg.csv"]:
            if Path(candidate).exists():
                csv_file = candidate
                break

    if csv_file is None or not Path(csv_file).exists():
        # Generate sample_ecg.csv automatically so the user can test immediately
        print("[!] No CSV file specified or found. Generating 'sample_ecg.csv' (1,000 samples @ 100 Hz)...")
        from ml.src.data_generator import generate_synthetic_ecg_buffer

        csv_file = "sample_ecg.csv"
        # Generate 10 seconds of realistic ECG at 100 Hz (1000 samples)
        samples = []
        for _ in range(20):  # 20 * 50 = 1000 samples
            samples.extend(generate_synthetic_ecg_buffer(heart_rate=72.0, num_samples=50))
        df_sample = pd.DataFrame({"ecg": samples})
        df_sample.to_csv(csv_file, index=False)
        print(f"[+] Created '{csv_file}' successfully!")

    print(f"[*] Reading ECG data from: {csv_file}")
    plot_ecg(
        csv_path=csv_file,
        fs=args.fs,
        duration_sec=args.duration if args.duration > 0 else None,
        save_path=args.save,
        show_peaks=not args.no_peaks,
        interactive=True,
    )

    if args.excel:
        export_to_excel(csv_path=csv_file, fs=args.fs)


if __name__ == "__main__":
    main()
