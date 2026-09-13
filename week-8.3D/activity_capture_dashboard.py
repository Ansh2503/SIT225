import base64
import csv
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import plotly.graph_objects as go
from arduino_iot_cloud import ArduinoCloudClient
from dash import Dash, Input, Output, dcc, html
from dotenv import load_dotenv


# ==================================================
# SETTINGS
# ==================================================

logging.basicConfig(level=logging.WARNING)

load_dotenv()

DEVICE_ID = os.getenv("DEVICE_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

if not DEVICE_ID or not SECRET_KEY:
    raise ValueError("DEVICE_ID or SECRET_KEY is missing from .env")

OUTPUT_FOLDER = Path("captured_activity_data")
OUTPUT_FOLDER.mkdir(exist_ok=True)

ANNOTATION_FILE = OUTPUT_FOLDER / "annotations.csv"

if not ANNOTATION_FILE.exists():
    with ANNOTATION_FILE.open("w", newline="") as file:
        csv.writer(file).writerow(
            ["filename", "activity_label"]
        )


# ==================================================
# SHARED DATA
# ==================================================

latest_values = {
    "x": None,
    "y": None,
    "z": None
}

samples = []

current_activity = {
    "label": "0",
    "name": "No activity"
}

latest_display = {
    "figure": None,
    "image": "",
    "message": "Waiting for the first capture"
}

data_lock = threading.Lock()
display_lock = threading.Lock()

camera = None


def get_next_sequence():
    numbers = []

    for file in OUTPUT_FOLDER.glob("*.csv"):
        first_part = file.stem.split("_")[0]

        if first_part.isdigit():
            numbers.append(int(first_part))

    return max(numbers, default=0) + 1


sequence_number = get_next_sequence()


# ==================================================
# RECEIVE ACCELEROMETER DATA
# ==================================================

def process_reading(axis, value):
    """Store a sensor value received from Arduino Cloud."""

    numeric_value = float(value)

    with data_lock:
        latest_values[axis] = numeric_value

        if all(
            item is not None
            for item in latest_values.values()
        ):
            samples.append([
                datetime.now(timezone.utc).isoformat(),
                latest_values["x"],
                latest_values["y"],
                latest_values["z"]
            ])

    print(f"{axis.upper()}: {numeric_value:.3f}")


def on_x_changed(client, value):
    process_reading("x", value)


def on_y_changed(client, value):
    process_reading("y", value)


def on_z_changed(client, value):
    process_reading("z", value)


# ==================================================
# ARDUINO CLOUD CONNECTION
# ==================================================

def run_arduino_cloud():
    """Connect and continuously process Cloud messages."""

    try:
        client = ArduinoCloudClient(
            device_id=DEVICE_ID,
            username=DEVICE_ID,
            password=SECRET_KEY,
            sync_mode=True
        )

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

        client.start()

        print("Arduino Cloud connected successfully.")
        print("Move the phone to generate readings.")

        # Required when sync_mode=True
        while True:
            client.update()
            time.sleep(0.1)

    except Exception as error:
        print("Arduino Cloud error:", repr(error))


# ==================================================
# CAMERA
# ==================================================

def initialise_camera():
    """Open the built-in MacBook camera."""

    global camera

    camera = cv2.VideoCapture(
        0,
        cv2.CAP_AVFOUNDATION
    )

    if not camera.isOpened():
        raise RuntimeError("MacBook camera could not open")

    time.sleep(2)

    for _ in range(20):
        camera.read()
        time.sleep(0.05)

    print("MacBook camera connected.")


def capture_image():
    """Capture a valid camera frame."""

    final_frame = None

    for _ in range(15):
        success, frame = camera.read()

        if success and frame is not None:
            final_frame = frame

        time.sleep(0.03)

    return final_frame


# ==================================================
# GRAPH
# ==================================================

def create_graph(rows, title):
    """Create a graph for one 10-second sample."""

    times = [row[0] for row in rows]
    x_data = [row[1] for row in rows]
    y_data = [row[2] for row in rows]
    z_data = [row[3] for row in rows]

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=times,
            y=x_data,
            name="X",
            mode="lines+markers",
            line={"color": "red"}
        )
    )

    figure.add_trace(
        go.Scatter(
            x=times,
            y=y_data,
            name="Y",
            mode="lines+markers",
            line={"color": "green"}
        )
    )

    figure.add_trace(
        go.Scatter(
            x=times,
            y=z_data,
            name="Z",
            mode="lines+markers",
            line={"color": "blue"}
        )
    )

    figure.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Acceleration",
        template="plotly_dark",
        hovermode="x unified"
    )

    return figure


# ==================================================
# SAVE MATCHING CSV AND JPG
# ==================================================

def save_activity_sample():
    """Save one 10-second data batch and camera image."""

    global sequence_number

    with data_lock:
        rows = list(samples)
        samples.clear()

    if not rows:
        print("No accelerometer readings received.")
        return

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    base_name = f"{sequence_number}_{timestamp}"

    csv_name = f"{base_name}.csv"
    jpg_name = f"{base_name}.jpg"

    csv_path = OUTPUT_FOLDER / csv_name
    jpg_path = OUTPUT_FOLDER / jpg_name

    frame = capture_image()

    if frame is None:
        print("Camera capture failed.")
        return

    # Save X, Y and Z data
    with csv_path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "x", "y", "z"])
        writer.writerows(rows)

    # Save the matching activity photograph
    cv2.imwrite(str(jpg_path), frame)

    label = current_activity["label"]
    activity_name = current_activity["name"]

    # Add a row to the two-column annotation file
    with ANNOTATION_FILE.open("a", newline="") as file:
        csv.writer(file).writerow([
            csv_name,
            label
        ])

    # Convert the photograph for Dash
    with jpg_path.open("rb") as file:
        encoded_image = base64.b64encode(
            file.read()
        ).decode("utf-8")

    image_source = (
        f"data:image/jpeg;base64,{encoded_image}"
    )

    figure = create_graph(
        rows,
        f"{activity_name}: {base_name}"
    )

    message = (
        f"Saved {csv_name} and {jpg_name} | "
        f"Label {label}: {activity_name}"
    )

    with display_lock:
        latest_display["figure"] = figure
        latest_display["image"] = image_source
        latest_display["message"] = message

    print(message)

    sequence_number += 1


def capture_loop():
    """Save data and an image every 10 seconds."""

    while True:
        time.sleep(10)
        save_activity_sample()


# ==================================================
# DASHBOARD
# ==================================================

app = Dash(__name__)

empty_figure = go.Figure()

empty_figure.update_layout(
    title="Waiting for the first 10-second sample",
    xaxis_title="Time",
    yaxis_title="Acceleration",
    template="plotly_dark"
)

app.layout = html.Div(
    [
        html.H1(
            "Smartphone Activity Capture Dashboard"
        ),

        html.P(
            "Select the activity currently being performed:"
        ),

        dcc.RadioItems(
            id="activity-selector",
            options=[
                {
                    "label": "0 - No activity",
                    "value": "0"
                },
                {
                    "label": "1 - Waving",
                    "value": "1"
                },
                {
                    "label": "2 - Shaking",
                    "value": "2"
                }
            ],
            value="0",
            inline=True
        ),

        html.H3(id="activity-status"),

        dcc.Graph(
            id="activity-graph",
            figure=empty_figure
        ),

        html.H2("Matching webcam image"),

        html.Img(
            id="activity-image",
            style={
                "width": "60%",
                "maxHeight": "450px",
                "objectFit": "contain",
                "border": "2px solid black"
            }
        ),

        html.H3(id="capture-status"),

        dcc.Interval(
            id="display-timer",
            interval=1000,
            n_intervals=0
        )
    ],
    style={
        "maxWidth": "1300px",
        "margin": "auto",
        "padding": "20px",
        "fontFamily": "Arial"
    }
)


@app.callback(
    Output("activity-status", "children"),
    Input("activity-selector", "value")
)
def select_activity(label):
    names = {
        "0": "No activity",
        "1": "Waving",
        "2": "Shaking"
    }

    current_activity["label"] = label
    current_activity["name"] = names[label]

    return f"Current activity: {label} - {names[label]}"


@app.callback(
    Output("activity-graph", "figure"),
    Output("activity-image", "src"),
    Output("capture-status", "children"),
    Input("display-timer", "n_intervals")
)
def refresh_dashboard(n_intervals):
    with display_lock:
        figure = latest_display["figure"]
        image = latest_display["image"]
        message = latest_display["message"]

    if figure is None:
        return empty_figure, "", message

    return figure, image, message


# ==================================================
# START
# ==================================================

if __name__ == "__main__":
    try:
        initialise_camera()

        cloud_thread = threading.Thread(
            target=run_arduino_cloud,
            daemon=True
        )

        save_thread = threading.Thread(
            target=capture_loop,
            daemon=True
        )

        cloud_thread.start()
        save_thread.start()

        print("Open http://127.0.0.1:8052")
        print("Files will be saved every 10 seconds.")

        app.run(
            host="127.0.0.1",
            port=8052,
            debug=False,
            use_reloader=False
        )

    except KeyboardInterrupt:
        print("Program stopped.")

    finally:
        if camera is not None:
            camera.release()

        print("Camera released. Files saved.")