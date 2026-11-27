"""Convert raw ESP32 / Serial Monitor .txt ECG dumps into timestamped CSV files.

Reads raw numeric amplitude lines from files in `txt_data/` and writes clean CSV files
with `milliseconds`, `amplitude`, and `voltage_mv` columns into `csv_data/`.

Usage:
    python txt_to_csv.py                        # Converts all .txt files in txt_data/
    python txt_to_csv.py "txt_data/ECG Test 1.txt"
    python txt_to_csv.py --fs 250               # Custom sampling rate (default: 100 Hz)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
TXT_DIR = BASE_DIR / "txt_data"
CSV_DIR = BASE_DIR / "csv_data"


def parse_numeric_samples(txt_path: Path) -> list[int | float]:
    """Extract numeric ECG amplitude readings from a raw text file, skipping text headers."""
    samples: list[int | float] = []
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            token = raw_line.strip()
            if not token:
                continue
            try:
                val = float(token)
                samples.append(int(val) if val.is_integer() else val)
            except ValueError:
                # Skip non-numeric header/label lines like "ECG Test 1" or "output:"
                continue
    return samples


def convert_txt_to_csv(txt_path: Path, output_csv: Path | None = None, fs: int = 100) -> Path:
    """Convert a single .txt ECG recording into a CSV file with millisecond timestamps."""
    if not txt_path.exists():
        raise FileNotFoundError(f"TXT file not found: {txt_path}")

    samples = parse_numeric_samples(txt_path)
    if not samples:
        raise ValueError(f"No numeric ECG readings found in: {txt_path}")

    CSV_DIR.mkdir(parents=True, exist_ok=True)
    if output_csv is None:
        safe_stem = txt_path.stem.strip().replace(" ", "_")
        output_csv = CSV_DIR / f"{safe_stem}.csv"

    dt_ms = 1000.0 / float(fs)
    milliseconds = [int(round(i * dt_ms)) for i in range(len(samples))]
    voltage_mv = [round((float(val) / 4095.0) * 3300.0, 2) for val in samples]

    df = pd.DataFrame(
        {
            "milliseconds": milliseconds,
            "amplitude": samples,
            "voltage_mv": voltage_mv,
        }
    )
    df.to_csv(output_csv, index=False)
    print(f"[+] Converted '{txt_path.name}' ({len(df)} samples @ {fs} Hz) -> {output_csv}")
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert raw ECG .txt dumps to .csv with milliseconds.")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Optional path to a specific .txt file (defaults to converting all .txt files in txt_data/)",
    )
    parser.add_argument(
        "--fs",
        type=int,
        default=100,
        help="Sampling frequency in Hz (default: 100 Hz -> 10 ms step)",
    )
    args = parser.parse_args()

    if args.file:
        target = Path(args.file)
        if not target.exists():
            target = TXT_DIR / args.file
        convert_txt_to_csv(target, fs=args.fs)
        return

    TXT_DIR.mkdir(parents=True, exist_ok=True)
    txt_files = sorted(TXT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"[!] No .txt files found in {TXT_DIR}")
        return

    for txt_file in txt_files:
        convert_txt_to_csv(txt_file, fs=args.fs)


if __name__ == "__main__":
    main()
