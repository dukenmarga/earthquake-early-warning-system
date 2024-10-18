import os
import random
import threading
import time
import uuid
from typing import Any

import numpy as np
from engineio.payload import Payload
from flask import Flask, current_app, send_from_directory, session
from flask_socketio import SocketIO
from numpy.typing import NDArray

from prediction import predict_earthquake_wave

Payload.max_decode_packets = 500

app = Flask(__name__, static_folder="template/build")
app.secret_key = "1112e8efe6124199aec2"
socketio = SocketIO(app, ping_timeout=40)

if __name__ == "__main__":
    socketio.run(
        app, debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080))
    )


@app.route("/_app/<path:path>")
def resources(path: str):
    if app.static_folder:
        return send_from_directory(app.static_folder, f"_app/{path}")
    return "Resource not found", 500


@app.route("/favicon.png")
def icon():
    if app.static_folder:
        return current_app.send_static_file("favicon.png")
    return "Resource not found", 500


@app.route("/")
def index():
    session["connection_id"] = str(uuid.uuid4())
    if app.static_folder:
        return current_app.send_static_file("index.html")
    return "Template not found", 500


connections: dict[str, Any] = {}

# Configuration
sampling_rate = 100  # 100 samples per second (100 Hz)
buffer_duration = 3  # Buffer for the last 3 seconds
buffer_size = (
    sampling_rate * buffer_duration
)  # Total samples in 3 seconds (e.g., 100 * 3 = 300)
sta_window = int(0.5 * sampling_rate)  # STA window (0.5 seconds)
lta_window = int(2 * sampling_rate)  # LTA window (2 seconds)
sta_lta_threshold = 3.0  # Threshold for detecting P-wave onset


@socketio.on("connect")
def handle_connect():
    # Create a new entry for the connection
    connection_id = str(session.get("connection_id"))
    connections[connection_id] = {
        "data_buffer": [],
        "p_wave_start": False,
        "s_wave_start": False,
        "p_wave_run_once": False,
        "s_wave_run_once": False,
        "global_p_wave_lock": threading.Lock(),
        "global_s_wave_lock": threading.Lock(),
        "p_wave_amplitude": 0,
        "s_wave_amplitude": 0,
    }
    print(f"New connection: {connection_id}")


@socketio.on("disconnect")
def handle_disconnect():
    connection_id = str(session.get("connection_id"))
    if connection_id in connections:
        # Clean up the data for this connection
        del connections[connection_id]
        print(f"Connection {connection_id} closed and data cleared.")


@socketio.on("seismic_wave")
def handle_seismic_wave(data: dict[str, int | float]):
    """
    Handle seismic wave data sent from the frontend.
    Expected data format: {'wave_sample': value, 'sampling_rate': 100}
    """
    connection_id = str(session.get("connection_id"))

    try:
        # Extract data from the incoming message
        wave_sample = data["wave_sample"]
        connections[connection_id]["data_buffer"].append(wave_sample)

        # Keep only the latest 'buffer_size' samples in the buffer
        if len(connections[connection_id]["data_buffer"]) > buffer_size:
            connections[connection_id]["data_buffer"].pop(
                0
            )  # Remove the oldest sample to maintain a fixed buffer size

        # global_lock is used to ensure only one P-wave is detected
        with connections[connection_id]["global_p_wave_lock"]:
            if not connections[connection_id]["p_wave_start"]:
                connections[connection_id]["p_wave_start"] = p_wave_detected()
            elif not connections[connection_id]["s_wave_start"]:
                pass
            else:
                # quick return if P-wave is already detected (do nothing)
                return

        if connections[connection_id]["p_wave_start"]:
            if not connections[connection_id]["p_wave_run_once"]:
                connections[connection_id]["p_wave_run_once"] = True
                naturalfreq = int(data["building_type"])
                pga = 0
                message = "<div style='color:blue'><strong>Earthquake Detected. Analysis in progress...</strong></div>"
                socketio.emit(
                    "seismic_update",
                    response(
                        {
                            "sent": True,
                            "message": "P-wave",
                        },
                        message,
                    ),
                )

                # Wait for 3 seconds before processing again.
                # We wait here to capture 3 seconds after the P-wave is detected
                time.sleep(3)

                # Convert the buffer into a NumPy array for processing
                wave_data = np.array(connections[connection_id]["data_buffer"])

                # PGA from P-wave (3 seconds)
                pga = pga_p_wave(wave_data)

                if connections[connection_id]["p_wave_amplitude"] == 0:
                    connections[connection_id]["p_wave_amplitude"] = mean_amplitude(
                        wave_data
                    )

                # Predict using the loaded model
                message, probability = predict_earthquake_wave(pga, naturalfreq)

                # Send processed data back to the client
                socketio.emit(
                    "seismic_update",
                    response(
                        {
                            "sent": True,
                            "message": "Inference",
                        },
                        message,
                    ),
                )

        if random.randint(0, 5) != 0:
            return

        with connections[connection_id]["global_s_wave_lock"]:
            if not connections[connection_id]["s_wave_start"]:
                connections[connection_id]["s_wave_start"] = s_wave_detected(
                    np.array(connections[connection_id]["data_buffer"])
                )
            else:
                # quick return if S-wave is already detected (do nothing)
                return

        if (
            connections[connection_id]["s_wave_start"]
            and connections[connection_id]["p_wave_run_once"]
        ):
            if not connections[connection_id]["s_wave_run_once"]:
                connections[connection_id]["s_wave_run_once"] = True
                message = ""
                socketio.emit(
                    "seismic_update",
                    response(
                        {
                            "sent": True,
                            "message": "S-wave",
                        },
                        message,
                    ),
                )

    except Exception as e:
        print(f"Error processing seismic wave data: {str(e)}")


# Extract PGA from P-wave (within limited buffer size)
def pga_p_wave(wave_data: NDArray[np.float64]) -> float:
    """
    Example function to extract features from seismic wave data.
    """
    # We purposely raise error to prevent inference.
    # Hence, the user can refresh the browser and try other simulation.
    if len(wave_data) < 100:
        raise ValueError("Wave data must be at least 100 samples long.")
    pga = np.max(np.abs(wave_data))
    return pga.item()


# Response format to send back to socket client
def response(
    signal: dict[str, str | float],
    message: str,
) -> dict[str, Any]:
    return {
        "signal": {
            "sent": signal["sent"],
            "message": signal["message"],
        },
        "message": message,
    }


# Check if P-wave is detected
def p_wave_detected() -> bool:
    connection_id = str(session.get("connection_id"))

    # Process only if we have enough data
    if len(connections[connection_id]["data_buffer"]) >= buffer_size:
        # Get the last 3 seconds of data
        data_to_process = np.array(
            connections[connection_id]["data_buffer"][-buffer_size:]
        )

        # If STA/LTA ratio is above threshold, then P-wave is detected
        return is_sta_lta_ratio_above_threshold(data_to_process)

    return False


# Check if STA/LTA ratio is above threshold
def is_sta_lta_ratio_above_threshold(data: NDArray[np.float64]):
    """
    Detect the onset of a P-wave using the STA/LTA method.
    """
    sta_lta_ratio = calculate_sta_lta_ratio(data, sta_window, lta_window)

    # Check if the STA/LTA ratio exceeds the threshold
    if sta_lta_ratio >= sta_lta_threshold:
        return True
    return False


# Calculate STA/LTA ratio
def calculate_sta_lta_ratio(
    data: NDArray[np.float64], sta_window: int, lta_window: int
) -> float:
    """
    Calculate the STA/LTA ratio for a given data segment.
    """
    if len(data) < lta_window:
        return 0  # Not enough data for LTA

    # Compute STA (short-term average)
    sta = float(np.mean(np.abs(data[-sta_window:])))

    # Compute LTA (long-term average)
    lta = float(np.mean(np.abs(data[-lta_window:])))

    # Avoid division by zero
    if lta == 0:
        return 0

    # Calculate the STA/LTA ratio
    sta_lta_ratio = sta / lta
    return sta_lta_ratio


def s_wave_detected(data: NDArray[np.float64], threshold_multiplier: int = 4) -> bool:
    connection_id = str(session.get("connection_id"))

    # Return if p_wave_amplitude is zero
    if connections[connection_id]["p_wave_amplitude"] < 0.0001:
        return False

    avg_amplitude = float(np.max(np.abs(data[-100:-50])))
    max_amplitude = float(np.max(np.abs(data[-50:])))

    # Look for where amplitude exceeds the threshold (likely S-wave)
    for _, datapoint in enumerate(data):
        connections[connection_id]["s_wave_amplitude"] = np.abs(datapoint)
        if max_amplitude > threshold_multiplier * avg_amplitude:
            return True

    return False


def mean_amplitude(data_wave: NDArray[np.float64]) -> float:
    # Calculate mean amplitude of P-wave region (before S-wave)
    return float(np.mean(np.abs(data_wave)))
