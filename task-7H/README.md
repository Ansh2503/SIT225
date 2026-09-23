# SIT225 Task 7H Hardened Environmental Monitoring Pipeline

This folder contains the reproducible code and evidence for Ansh Avasthi, student ID s225577153.

## System

The system uses an Arduino Nano and DHT11 sensor. Python validates incoming serial rows, rejects incomplete and physically impossible values, applies a five-sample moving average, detects stale sequences and retries temporary serial failures.

## Files

* `hardened_pipeline.py` contains parsing, validation, smoothing and retry functions.
* `test_sensor_pipeline.py` contains 12 automated unit, edge-case and recovery tests.
* `evaluate_pipeline.py` compares baseline and hardened processing with controlled faults.
* `make_evidence.py` creates the evidence figures from the measured outputs.
* `results/metrics.json` contains quantitative results.
* `results/fault_injection_log.csv` contains the controlled fault outcomes.
* `dht11_raw_data.csv` is the real 30-minute dataset from Task 4P.

## Run

```bash
python -m unittest -v test_sensor_pipeline.py
python evaluate_pipeline.py
python make_evidence.py
```

## Measured results

* 12 of 12 automated tests passed.
* 889 of 889 real readings were retained.
* Baseline fault detection was 66.7%.
* Hardened fault detection was 100.0%.
* Precision, recall and F1 were 1.00 in the controlled validation set.
* Median in-process latency was approximately 0.0024 ms.

These results apply only to the supplied dataset and controlled fault cases. They do not establish calibrated sensor accuracy or readiness for safety-critical use.
