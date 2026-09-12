import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from arduino_iot_cloud import ArduinoCloudClient


# Load Arduino Cloud credentials from .env
load_dotenv()

DEVICE_ID = os.getenv("DEVICE_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

if not DEVICE_ID or not SECRET_KEY:
    raise ValueError("Arduino Cloud credentials are missing from .env")


# CSV files
X_FILE = Path("accelerometer_x.csv")
Y_FILE = Path("accelerometer_y.csv")
Z_FILE = Path("accelerometer_z.csv")
COMBINED_FILE = Path("accelerometer_xyz.csv")


# Store the latest sensor values
latest_values = {
    "x": None,
    "y": None,
    "z": None
}

# Track whether each axis has received a new reading
new_reading = {
    "x": False,
    "y": False,
    "z": False
}


def timestamp():
    """Return the current time in UTC."""

    return datetime.now(timezone.utc).isoformat()


def create_csv(file_path, headings):
    """Create a CSV file and add headings."""

    if not file_path.exists():
        with file_path.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headings)


def save_axis_reading(file_path, value):
    """Save one timestamp and accelerometer value."""

    with file_path.open("a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp(), value])


def save_combined_reading():
    """Save one row when fresh X, Y and Z readings are available."""

    if all(new_reading.values()):
        with COMBINED_FILE.open("a", newline="") as file:
            writer = csv.writer(file)

            writer.writerow([
                timestamp(),
                latest_values["x"],
                latest_values["y"],
                latest_values["z"]
            ])

        print(
            f"Combined: X={latest_values['x']:.3f}, "
            f"Y={latest_values['y']:.3f}, "
            f"Z={latest_values['z']:.3f}"
        )

        new_reading["x"] = False
        new_reading["y"] = False
        new_reading["z"] = False


# Callback for Accelerometer X
def on_x_changed(client, value):
    latest_values["x"] = value
    new_reading["x"] = True

    save_axis_reading(X_FILE, value)
    print(f"X: {value:.3f}")

    save_combined_reading()


# Callback for Accelerometer Y
def on_y_changed(client, value):
    latest_values["y"] = value
    new_reading["y"] = True

    save_axis_reading(Y_FILE, value)
    print(f"Y: {value:.3f}")

    save_combined_reading()


# Callback for Accelerometer Z
def on_z_changed(client, value):
    latest_values["z"] = value
    new_reading["z"] = True

    save_axis_reading(Z_FILE, value)
    print(f"Z: {value:.3f}")

    save_combined_reading()


# Create separate and combined CSV files
create_csv(X_FILE, ["timestamp", "x"])
create_csv(Y_FILE, ["timestamp", "y"])
create_csv(Z_FILE, ["timestamp", "z"])
create_csv(COMBINED_FILE, ["timestamp", "x", "y", "z"])


# Connect to Arduino IoT Cloud
client = ArduinoCloudClient(
    device_id=DEVICE_ID,
    username=DEVICE_ID,
    password=SECRET_KEY,
    sync_mode=True
)


# Register the synchronised variables and callbacks
client.register(
    "accelerometer_x",
    value=None,
    on_write=on_x_changed
)

client.register(
    "accelerometer_y",
    value=None,
    on_write=on_y_changed
)

client.register(
    "accelerometer_z",
    value=None,
    on_write=on_z_changed
)


print("Connecting to Arduino Cloud...")

try:
    client.start()

    print("Connected successfully.")
    print("Receiving accelerometer data...")
    print("Press Control + C to stop.")

    while True:
        client.update()
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nProgram stopped.")
    print("All CSV files have been saved.")

except Exception as error:
    print("Connection error:", error)