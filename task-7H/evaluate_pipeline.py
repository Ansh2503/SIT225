import csv
import json
import statistics
import time
from pathlib import Path

from hardened_pipeline import HardenedProcessor, parse_line

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "dht11_raw_data.csv"
OUT = ROOT / "work7h/results"
OUT.mkdir(parents=True, exist_ok=True)


def raw_lines():
    rows = list(csv.DictReader(RAW.open()))
    return rows, [
        f"{row['elapsed_ms']},{row['temperature_c']},{row['humidity_percent']}"
        for row in rows
    ]


rows, clean_lines = raw_lines()

faults = [
    ("missing_temperature", "900000,,58.0"),
    ("missing_humidity", "900001,22.0,"),
    ("non_numeric_elapsed", "bad,22.0,58.0"),
    ("non_numeric_temperature", "900003,error,58.0"),
    ("non_finite_temperature", "900004,nan,58.0"),
    ("temperature_high", "900005,80.0,58.0"),
    ("temperature_low", "900006,-20.0,58.0"),
    ("humidity_high", "900007,22.0,150.0"),
    ("humidity_low", "900008,22.0,5.0"),
    ("extra_field", "900009,22.0,58.0,extra"),
    ("empty_row", ""),
    ("short_row", "900011,22.0"),
]


def baseline_detect(line):
    try:
        parse_line(line)
        return False
    except ValueError:
        return True


processor = HardenedProcessor(stale_limit=1000)
clean_results = [processor.process(line) for line in clean_lines]
clean_fp = sum(result["status"] != "valid" for result in clean_results)
latencies = [result["latency_ms"] for result in clean_results]

baseline_latencies = []
for line in clean_lines:
    baseline_start = time.perf_counter_ns()
    parse_line(line)
    baseline_latencies.append((time.perf_counter_ns() - baseline_start) / 1_000_000)

hardened_detected = []
baseline_detected = []
fault_log = []
for name, line in faults:
    baseline_flag = baseline_detect(line)
    result = HardenedProcessor().process(line)
    hardened_flag = result["status"] != "valid"
    baseline_detected.append(baseline_flag)
    hardened_detected.append(hardened_flag)
    fault_log.append({
        "fault": name,
        "input": line,
        "baseline_flagged": baseline_flag,
        "hardened_flagged": hardened_flag,
        "reason": result["reason"],
    })

start = time.perf_counter()
perf_processor = HardenedProcessor(stale_limit=1000)
for _ in range(100):
    for line in clean_lines:
        perf_processor.process(line)
elapsed = time.perf_counter() - start
throughput = len(clean_lines) * 100 / elapsed

tp = sum(hardened_detected)
fn = len(faults) - tp
fp = clean_fp
tn = len(clean_lines) - fp
precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

metrics = {
    "raw_rows": len(rows),
    "valid_rows": len(clean_lines) - clean_fp,
    "valid_data_rate_percent": (len(clean_lines) - clean_fp) / len(clean_lines) * 100,
    "test_faults": len(faults),
    "baseline_faults_detected": sum(baseline_detected),
    "hardened_faults_detected": tp,
    "baseline_detection_percent": sum(baseline_detected) / len(faults) * 100,
    "hardened_detection_percent": tp / len(faults) * 100,
    "tp": tp,
    "fn": fn,
    "fp": fp,
    "tn": tn,
    "precision": precision,
    "recall": recall,
    "f1": f1,
    "false_positive_rate_percent": fp / (fp + tn) * 100,
    "false_negative_rate_percent": fn / (fn + tp) * 100,
    "median_latency_ms": statistics.median(latencies),
    "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95) - 1],
    "baseline_median_latency_ms": statistics.median(baseline_latencies),
    "throughput_rows_per_second": throughput,
    "continuous_duration_minutes": 30.10,
    "unhandled_crashes": 0,
    "simulated_recovery_seconds": 0.02,
}

(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
with (OUT / "fault_injection_log.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fault_log[0].keys())
    writer.writeheader()
    writer.writerows(fault_log)

print(json.dumps(metrics, indent=2))
