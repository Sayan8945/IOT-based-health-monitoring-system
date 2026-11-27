# ECG Data & Plotting Workspace

Dedicated folder for raw `.txt` sensor logs, millisecond-timestamped `.csv` datasets, and generated ECG graphs (`.png` images and `.xlsx` Excel charts).

---

## Folder Structure

```text
sample_data_and_plots/
├── txt_data/      # Put raw ESP32 / Serial Monitor .txt logs here
├── csv_data/      # Converted .csv files (milliseconds, amplitude, voltage_mv)
├── plots/         # Generated .png waveform images & .xlsx Excel charts
├── txt_to_csv.py  # Converts .txt files in txt_data/ -> csv_data/
└── plot_ecg.py    # Plots .csv files in csv_data/ -> plots/
```

---

## Quick Commands

Run these from inside `server/sample_data_and_plots/` (or prefix with `sample_data_and_plots\` from `server/`):

### 1. Convert `.txt` logs to `.csv` (adds `milliseconds` + `voltage_mv`)
```bash
python txt_to_csv.py
```

### 2. Generate PNG graph only
```bash
python plot_ecg.py
```

### 3. Generate BOTH PNG graph AND Excel chart (`.xlsx`)
```bash
python plot_ecg.py --excel
```

### 4. Plot a specific CSV or show full duration
```bash
python plot_ecg.py csv_data/ECG_Test_1.csv --duration 15 --excel
```
*(Use `--duration 0` to plot the entire recording, or `--all` to plot every CSV in `csv_data/`.)*
