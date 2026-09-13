import csv
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html, no_update
from dotenv import load_dotenv
from arduino_iot_cloud import ArduinoCloudClient


# Load private Arduino Cloud credentials
load_dotenv()

DEVICE_ID = os.getenv("DEVICE_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

if not DEVICE_ID or not SECRET_KEY:
    raise ValueError("DEVICE_ID or SECRET_KEY is missing from .env")


class SmoothDashStream:
    """
    Reusable wrapper for smooth live Plotly Dash updates.

    add_sample() stores incoming sensor readings in short buffers.
    get_new_points() returns only readings that have not been graphed.
    build_extend_data() formats those readings for Plotly extendData.
    max_points limits the number of points displayed on the graph.
    """

    def __init__(self, series_names, max_points=200):
        self.series_names = series_names
        self.max_points = max_points
        self.lock = threading.Lock()

        self.buffers = {
            name: deque()
            for name in series_names
        }

    def add_sample(self, series_name, value, timestamp=None):
        """Add one new sensor reading to its buffer."""

        if series_name not in self.buffers:
            raise ValueError(f"Unknown data series: {series_name}")

        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        with self.lock:
            self.buffers[series_name].append(
                (timestamp, float(value))
            )

    def get_new_points(self):
        """Collect and remove points waiting to be graphed."""

        new_points = {}

        with self.lock:
            for name, buffer in self.buffers.items():
                new_points[name] = list(buffer)
                buffer.clear()

        return new_points

    def build_extend_data(self, trace_order):
        """
        Build a Plotly extendData response.

        Only new points are sent to the browser. The existing graph
        is not completely redrawn.
        """

        new_points = self.get_new_points()

        x_values = []
        y_values = []
        trace_indices = []

        for trace_index, series_name in enumerate(trace_order):
            points = new_points.get(series_name, [])

            if points:
                x_values.append([
                    point[0] for point in points
                ])

                y_values.append([
                    point[1] for point in points
                ])

                trace_indices.append(trace_index)

        if not trace_indices:
            return None

        return (
            {
                "x": x_values,
                "y": y_values
            },
            trace_indices,
            self.max_points
        )


# Create the reusable streaming wrapper
stream = SmoothDashStream(
    series_names=["x", "y", "z"],
    max_points=200
)


# Store combined data for GitHub evidence
DATA_FILE = Path("live_accelerometer_data.csv")

if not DATA_FILE.exists():
    with DATA_FILE.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "x", "y", "z"])


latest_values = {
    "x": None,
    "y": None,
    "z": None
}

fresh_values = {
    "x": False,
    "y": False,
    "z": False
}

data_lock = threading.Lock()


def save_combined_data():
    """Save one row after new X, Y and Z readings arrive."""

    with data_lock:
        if not all(fresh_values.values()):
            return

        timestamp = datetime.now(timezone.utc).isoformat()

        with DATA_FILE.open("a", newline="") as file:
            writer = csv.writer(file)

            writer.writerow([
                timestamp,
                latest_values["x"],
                latest_values["y"],
                latest_values["z"]
            ])

        fresh_values["x"] = False
        fresh_values["y"] = False
        fresh_values["z"] = False


def process_reading(axis, value):
    """Send a reading to the graph buffer and CSV file."""

    numeric_value = float(value)

    stream.add_sample(axis, numeric_value)

    with data_lock:
        latest_values[axis] = numeric_value
        fresh_values[axis] = True

    save_combined_data()

    print(f"{axis.upper()}: {numeric_value:.3f}")


# Arduino Cloud callback functions
def on_x_changed(client, value):
    process_reading("x", value)


def on_y_changed(client, value):
    process_reading("y", value)


def on_z_changed(client, value):
    process_reading("z", value)


def run_arduino_cloud():
    """Receive Arduino Cloud data in a background thread."""

    try:
        cloud_client = ArduinoCloudClient(
            device_id=DEVICE_ID,
            username=DEVICE_ID,
            password=SECRET_KEY,
            sync_mode=True
        )

        cloud_client.register(
            "accelerometer_x",
            value=None,
            on_write=on_x_changed
        )

        cloud_client.register(
            "accelerometer_y",
            value=None,
            on_write=on_y_changed
        )

        cloud_client.register(
            "accelerometer_z",
            value=None,
            on_write=on_z_changed
        )

        print("Connecting to Arduino Cloud...")

        cloud_client.start()

        print("Arduino Cloud connected.")
        print("Waiting for phone accelerometer data...")

        while True:
            cloud_client.update()
            time.sleep(0.05)

    except Exception as error:
        print("Arduino Cloud error:", repr(error))


# Build the original empty Plotly graph
figure = go.Figure()

figure.add_trace(
    go.Scattergl(
        x=[],
        y=[],
        mode="lines",
        name="X",
        line={"color": "#ef4444", "width": 2}
    )
)

figure.add_trace(
    go.Scattergl(
        x=[],
        y=[],
        mode="lines",
        name="Y",
        line={"color": "#22c55e", "width": 2}
    )
)

figure.add_trace(
    go.Scattergl(
        x=[],
        y=[],
        mode="lines",
        name="Z",
        line={"color": "#3b82f6", "width": 2}
    )
)

figure.update_layout(
    title="Live Smartphone Accelerometer Data",
    xaxis_title="Time",
    yaxis_title="Acceleration",
    yaxis={"range": [-3, 3]},
    template="plotly_dark",
    hovermode="x unified",
    uirevision="keep",
    margin={"l": 60, "r": 30, "t": 70, "b": 60}
)


# Create the Dash application
app = Dash(__name__)

app.layout = html.Div(
    [
        html.H1(
            "Live Smartphone Accelerometer Dashboard"
        ),

        html.P(
            "Arduino IoT Cloud data with smooth incremental updates"
        ),

        dcc.Graph(
            id="live-accelerometer-graph",
            figure=figure,
            style={"height": "72vh"}
        ),

        # Update the graph four times per second
        dcc.Interval(
            id="graph-update-timer",
            interval=250,
            n_intervals=0
        )
    ],
    style={
        "maxWidth": "1400px",
        "margin": "0 auto",
        "padding": "20px",
        "fontFamily": "Arial"
    }
)


@app.callback(
    Output(
        "live-accelerometer-graph",
        "extendData"
    ),
    Input(
        "graph-update-timer",
        "n_intervals"
    )
)
def update_live_graph(n_intervals):
    """
    Add only fresh readings to the existing graph.

    Plotly extendData avoids rebuilding the full figure, resulting
    in smoother updates and lower browser and network workload.
    """

    update = stream.build_extend_data(
        trace_order=["x", "y", "z"]
    )

    if update is None:
        return no_update

    return update


if __name__ == "__main__":
    # Run Arduino Cloud separately from the Dash web server
    cloud_thread = threading.Thread(
        target=run_arduino_cloud,
        daemon=True
    )

    cloud_thread.start()

    print("Starting Plotly Dash...")
    print("Open http://127.0.0.1:8051")

    app.run(
        host="127.0.0.1",
        port=8051,
        debug=False,
        use_reloader=False
    )
