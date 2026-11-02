"""Synthetic Physiological Telemetry Generator.

Generates realistic human vital sign time-series streams (Heart Rate, SpO2, Body Temperature)
along with 100 Hz Lead-I ECG waveform buffers matching ESP32 hardware batching.
Supports baseline normal resting telemetry and clinical anomaly injection.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple


def generate_synthetic_ecg_buffer(
    heart_rate: float,
    num_samples: int = 50,
    sampling_rate_hz: int = 100,
    leads_connected: bool = True,
    noise_level: float = 0.02,
    seed: int | None = None,
) -> List[float]:
    """Generate a 50-sample synthetic Lead-I ECG buffer with realistic P-Q-R-S-T morphology.

    At 100 Hz, a 50-sample buffer represents 500 ms of real-time cardiac signal.
    """
    if seed is not None:
        random.seed(seed)

    if not leads_connected:
        # Leads-off baseline noise
        return [round((random.random() - 0.5) * 0.05, 3) for _ in range(num_samples)]

    # Calculate cardiac cycle duration in seconds and samples
    bps = max(30.0, min(220.0, heart_rate)) / 60.0
    period_samples = sampling_rate_hz / bps

    samples: List[float] = []
    # Use random initial phase offset for continuous variety
    phase_offset = random.random()

    for i in range(num_samples):
        phase = ((i / period_samples) + phase_offset) % 1.0
        val = 0.0

        # P-wave (atrial depolarization: gentle rounded dome)
        if 0.10 <= phase <= 0.20:
            p = (phase - 0.15) / 0.045
            val += 0.15 * math.exp(-p * p * 4)

        # Q-dip (septal depolarization: brief negative dip)
        if 0.28 <= phase <= 0.315:
            q = (phase - 0.30) / 0.012
            val -= 0.14 * math.exp(-q * q * 10)

        # R-peak (ventricular depolarization: tall sharp positive spike)
        if 0.315 <= phase <= 0.37:
            r = (phase - 0.34) / 0.018
            val += 0.72 * math.exp(-r * r * 8)

        # S-dip (late ventricular depolarization: sharp negative dip)
        if 0.37 <= phase <= 0.42:
            s = (phase - 0.395) / 0.016
            val -= 0.24 * math.exp(-s * s * 8)

        # T-wave (ventricular repolarization: medium rounded wave)
        if 0.54 <= phase <= 0.70:
            t = (phase - 0.62) / 0.07
            val += 0.22 * math.exp(-t * t * 3.5)

        # Add Gaussian-like analog noise
        noise = (random.random() - 0.5) * noise_level
        val += noise

        # Quantize to 3 decimal places (mV)
        samples.append(round(val, 3))

    return samples


def generate_telemetry_record(
    state: str = "nominal",
    prev_hr: float = 72.0,
    prev_spo2: float = 98.5,
    prev_temp: float = 36.7,
    time_step_sec: float = 1.0,
) -> Tuple[Dict[str, any], float, float, float]:
    """Generate a single time-step telemetry packet with smooth autoregressive random walk."""
    is_anomaly = False
    anomaly_type = "none"

    if state == "nominal":
        # Physiological drift towards baseline
        target_hr = 72.0 + (random.random() - 0.5) * 8.0
        target_spo2 = 98.5 + (random.random() - 0.5) * 1.5
        target_temp = 36.7 + (random.random() - 0.5) * 0.3

        # Autoregressive smoothing (alpha = 0.15)
        hr = prev_hr + 0.15 * (target_hr - prev_hr) + (random.random() - 0.5) * 1.0
        spo2 = prev_spo2 + 0.15 * (target_spo2 - prev_spo2) + (random.random() - 0.5) * 0.3
        temp = prev_temp + 0.15 * (target_temp - prev_temp) + (random.random() - 0.5) * 0.03

        hr = max(58.0, min(88.0, hr))
        spo2 = max(96.0, min(99.5, spo2))
        temp = max(36.4, min(37.2, temp))

    elif state == "hypoxia":
        # Rapid or steady desaturation with compensatory tachycardia
        target_spo2 = 87.0 + (random.random() - 0.5) * 3.0
        target_hr = 108.0 + (random.random() - 0.5) * 8.0
        target_temp = prev_temp + (random.random() - 0.5) * 0.1

        hr = prev_hr + 0.25 * (target_hr - prev_hr)
        spo2 = prev_spo2 + 0.30 * (target_spo2 - prev_spo2)
        temp = prev_temp + 0.10 * (target_temp - prev_temp)
        is_anomaly = True
        anomaly_type = "hypoxia"

    elif state == "tachycardia":
        # Elevated heart rate above 110 bpm
        target_hr = 125.0 + (random.random() - 0.5) * 12.0
        target_spo2 = prev_spo2 - 0.1
        target_temp = prev_temp + 0.02

        hr = prev_hr + 0.25 * (target_hr - prev_hr)
        spo2 = max(92.0, min(99.0, prev_spo2))
        temp = prev_temp
        is_anomaly = True
        anomaly_type = "tachycardia"

    elif state == "bradycardia":
        # Depressed heart rate below 50 bpm
        target_hr = 43.0 + (random.random() - 0.5) * 6.0
        hr = prev_hr + 0.25 * (target_hr - prev_hr)
        spo2 = max(94.0, min(99.0, prev_spo2))
        temp = max(35.5, prev_temp - 0.02)
        is_anomaly = True
        anomaly_type = "bradycardia"

    elif state == "fever":
        # Hyperthermia > 38.0°C with elevated metabolic rate
        target_temp = 38.6 + (random.random() - 0.5) * 0.6
        target_hr = 104.0 + (random.random() - 0.5) * 8.0
        temp = prev_temp + 0.20 * (target_temp - prev_temp)
        hr = prev_hr + 0.20 * (target_hr - prev_hr)
        spo2 = max(94.0, prev_spo2 - 0.1)
        is_anomaly = True
        anomaly_type = "fever"

    elif state == "lead_disconnect":
        hr = prev_hr
        spo2 = prev_spo2
        temp = prev_temp
        is_anomaly = True
        anomaly_type = "lead_disconnect"

    else:
        hr, spo2, temp = prev_hr, prev_spo2, prev_temp

    leads_connected = state != "lead_disconnect"
    ecg_buffer = generate_synthetic_ecg_buffer(
        heart_rate=hr,
        num_samples=50,
        sampling_rate_hz=100,
        leads_connected=leads_connected,
    )

    record = {
        "heart_rate": round(hr, 1),
        "spo2": round(spo2, 1),
        "temperature": round(temp, 2),
        "ecg_samples": ecg_buffer,
        "leads_connected": leads_connected,
        "is_anomaly": is_anomaly,
        "anomaly_type": anomaly_type,
    }

    return record, hr, spo2, temp


def generate_dataset(
    total_records: int = 5000,
    anomaly_ratio: float = 0.05,
    seed: int = 42,
) -> List[Dict[str, any]]:
    """Generate a combined sequential dataset with nominal periods and intermittent anomaly episodes."""
    random.seed(seed)
    records: List[Dict[str, any]] = []

    hr, spo2, temp = 72.0, 98.5, 36.7
    current_state = "nominal"
    state_remaining = 0

    anomaly_states = ["hypoxia", "tachycardia", "bradycardia", "fever", "lead_disconnect"]

    for i in range(total_records):
        if state_remaining <= 0:
            # Decide next state transition
            if random.random() < anomaly_ratio:
                current_state = random.choice(anomaly_states)
                state_remaining = random.randint(15, 45)  # Anomaly lasts 15-45 seconds
            else:
                current_state = "nominal"
                state_remaining = random.randint(60, 200)  # Nominal lasts 1-3 minutes

        record, hr, spo2, temp = generate_telemetry_record(
            state=current_state,
            prev_hr=hr,
            prev_spo2=spo2,
            prev_temp=temp,
        )
        record["timestamp_index"] = i
        records.append(record)
        state_remaining -= 1

    return records
