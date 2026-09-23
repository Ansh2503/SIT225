import csv
import glob
import time
from datetime import datetime, timedelta
from pathlib import Path

import serial


COLLECTION_MINUTES = 30
RATING_INTERVAL_MINUTES = 5
BAUD_RATE = 9600

RAW_FILE = Path("dht11_raw_data.csv")
RATINGS_FILE = Path("focus_comfort_ratings.csv")
LOG_FILE = Path("collection_log.txt")


def find_arduino_port():
    possible_ports = (
        glob.glob("/dev/cu.usbmodem*")
        + glob.glob("/dev/cu.usbserial*")
    )

    if not possible_ports:
        raise RuntimeError(
            "Arduino port not found. Connect the Nano and close Serial Monitor."
        )

    return possible_ports[0]


def get_rating(name):
    while True:
        try:
            value = int(
                input(f"Enter {name} rating from 1 to 5: ")
            )

            if 1 <= value <= 5:
                return value

            print("Please enter a number from 1 to 5.")

        except ValueError:
            print("Please enter a whole number.")


def record_rating(writer, elapsed_minutes):
    print()
    print("Rating checkpoint")

    focus = get_rating("focus")
    comfort = get_rating("comfort")

    writer.writerow([
        datetime.now().isoformat(),
        round(elapsed_minutes, 2),
        focus,
        comfort
    ])

    print("Rating saved. Data collection continues.")
    print()


port = find_arduino_port()

print(f"Arduino found on {port}")
print("Opening serial connection...")

arduino = serial.Serial(
    port,
    BAUD_RATE,
    timeout=2
)

time.sleep(3)
arduino.reset_input_buffer()

start_time = datetime.now()
end_time = start_time + timedelta(
    minutes=COLLECTION_MINUTES
)

next_rating_time = start_time

valid_rows = 0
invalid_rows = 0

with RAW_FILE.open("w", newline="") as raw_file, \
     RATINGS_FILE.open("w", newline="") as ratings_file:

    raw_writer = csv.writer(raw_file)
    ratings_writer = csv.writer(ratings_file)

    raw_writer.writerow([
        "timestamp",
        "elapsed_ms",
        "temperature_c",
        "humidity_percent"
    ])

    ratings_writer.writerow([
        "timestamp",
        "elapsed_minutes",
        "focus_rating",
        "comfort_rating"
    ])

    print()
    print("Starting 30-minute DHT11 collection.")
    print(f"Start: {start_time.isoformat()}")
    print(f"Expected end: {end_time.isoformat()}")
    print("Give focus and comfort ratings when requested.")
    print()

    while datetime.now() < end_time:
        current_time = datetime.now()

        if current_time >= next_rating_time:
            elapsed_minutes = (
                current_time - start_time
            ).total_seconds() / 60

            record_rating(
                ratings_writer,
                elapsed_minutes
            )

            ratings_file.flush()

            next_rating_time += timedelta(
                minutes=RATING_INTERVAL_MINUTES
            )

        line = arduino.readline().decode(
            "utf-8",
            errors="ignore"
        ).strip()

        if not line:
            continue

        if line.startswith("elapsed_ms"):
            continue

        if line.startswith("ERROR"):
            invalid_rows += 1
            print(line)
            continue

        parts = line.split(",")

        if len(parts) != 3:
            invalid_rows += 1
            continue

        try:
            elapsed_ms = int(parts[0])
            temperature = float(parts[1])
            humidity = float(parts[2])

            raw_writer.writerow([
                datetime.now().isoformat(),
                elapsed_ms,
                temperature,
                humidity
            ])

            raw_file.flush()
            valid_rows += 1

            print(
                f"{valid_rows}: "
                f"{temperature:.1f} C, "
                f"{humidity:.1f}%"
            )

        except ValueError:
            invalid_rows += 1

    # Final rating at the end
    elapsed_minutes = (
        datetime.now() - start_time
    ).total_seconds() / 60

    record_rating(
        ratings_writer,
        elapsed_minutes
    )

arduino.close()

actual_end_time = datetime.now()

with LOG_FILE.open("w") as file:
    file.write(f"Start time: {start_time.isoformat()}\n")
    file.write(f"End time: {actual_end_time.isoformat()}\n")
    file.write(f"Valid rows: {valid_rows}\n")
    file.write(f"Invalid rows: {invalid_rows}\n")
    file.write(f"Serial port: {port}\n")
    file.write("Sensor: DHT11\n")
    file.write("Sampling interval: approximately 2 seconds\n")

print()
print("Collection complete.")
print(f"Valid rows: {valid_rows}")
print(f"Invalid rows: {invalid_rows}")
print("Saved dht11_raw_data.csv")
print("Saved focus_comfort_ratings.csv")
print("Saved collection_log.txt")
