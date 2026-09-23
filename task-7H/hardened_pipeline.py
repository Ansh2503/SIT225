"""Fault-tolerant processing for the SIT225 DHT11 monitoring system."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable

TEMP_MIN = 0.0
TEMP_MAX = 50.0
HUM_MIN = 20.0
HUM_MAX = 90.0


@dataclass
class Reading:
    elapsed_ms: int
    temperature_c: float
    humidity_percent: float


def parse_line(line: str) -> Reading:
    parts = line.strip().split(",")
    if len(parts) != 3 or any(part.strip() == "" for part in parts):
        raise ValueError("incomplete row")
    try:
        reading = Reading(int(parts[0]), float(parts[1]), float(parts[2]))
    except (TypeError, ValueError) as error:
        raise ValueError("non-numeric row") from error
    if not all(
        math.isfinite(value)
        for value in (reading.temperature_c, reading.humidity_percent)
    ):
        raise ValueError("non-finite value")
    return reading


def validate_reading(reading: Reading) -> tuple[bool, str]:
    if not TEMP_MIN <= reading.temperature_c <= TEMP_MAX:
        return False, "temperature_out_of_range"
    if not HUM_MIN <= reading.humidity_percent <= HUM_MAX:
        return False, "humidity_out_of_range"
    return True, "valid"


def moving_average(values: Iterable[float], window: int = 5) -> float:
    if window < 1:
        raise ValueError("window must be positive")
    recent = list(values)[-window:]
    if not recent:
        raise ValueError("values cannot be empty")
    return sum(recent) / len(recent)


class HardenedProcessor:
    def __init__(self, stale_limit: int = 5, noise_threshold: float = 5.0):
        self.stale_limit = stale_limit
        self.noise_threshold = noise_threshold
        self.previous: Reading | None = None
        self.repeat_count = 0
        self.temperatures = deque(maxlen=5)
        self.humidities = deque(maxlen=5)

    def process(self, line: str) -> dict:
        started = time.perf_counter_ns()
        try:
            reading = parse_line(line)
            valid, reason = validate_reading(reading)
            if not valid:
                raise ValueError(reason)

            if self.previous and (
                reading.temperature_c == self.previous.temperature_c
                and reading.humidity_percent == self.previous.humidity_percent
            ):
                self.repeat_count += 1
            else:
                self.repeat_count = 0

            if self.repeat_count >= self.stale_limit:
                raise ValueError("stale_sequence")

            noisy = False
            if self.previous:
                noisy = (
                    abs(reading.temperature_c - self.previous.temperature_c)
                    > self.noise_threshold
                    or abs(reading.humidity_percent - self.previous.humidity_percent)
                    > self.noise_threshold
                )

            self.temperatures.append(reading.temperature_c)
            self.humidities.append(reading.humidity_percent)
            self.previous = reading
            result = {
                "status": "valid",
                "reason": "sudden_change" if noisy else "valid",
                "reading": reading,
                "temperature_smooth": moving_average(self.temperatures),
                "humidity_smooth": moving_average(self.humidities),
            }
        except ValueError as error:
            result = {
                "status": "degraded",
                "reason": str(error),
                "reading": None,
                "temperature_smooth": None,
                "humidity_smooth": None,
            }
        result["latency_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        return result


def read_with_retry(serial_port, retries: int = 3, retry_delay: float = 0.01):
    """Retry transient serial failures, then return a labelled degraded state."""
    started = time.perf_counter()
    for attempt in range(retries):
        try:
            raw = serial_port.readline()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="strict")
            result = HardenedProcessor().process(raw)
            if result["status"] == "valid":
                result["attempts"] = attempt + 1
                result["recovery_seconds"] = time.perf_counter() - started
                return result
        except (OSError, UnicodeDecodeError):
            pass
        if attempt < retries - 1:
            time.sleep(retry_delay)
    return {
        "status": "degraded",
        "reason": "serial_retry_exhausted",
        "attempts": retries,
        "recovery_seconds": time.perf_counter() - started,
    }
