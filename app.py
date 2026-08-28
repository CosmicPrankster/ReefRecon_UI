"""
ReefRecon UI - minimal web app for triggering audio playback on the Pi.

Runs `aplay` inside the existing reef-recon repo (unmodified) as a
subprocess, and exposes Play/Stop over a small web UI so it can be
controlled from a phone browser on the same network (e.g. a hotspot).
"""
import os
import subprocess
import threading

from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Path to the existing reef-recon checkout on the Pi. Override with the
# REEF_RECON_DIR environment variable if it's not a sibling of this repo.
REEF_RECON_DIR = os.environ.get(
    "REEF_RECON_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reef-recon"),
)

# Equivalent to: cd reef-recon && aplay -D hw:CARD=sndrpihifiberry,DEV=0 tests/example_recordings/white_noise_0dbfs_peak.wav
PLAY_CMD = [
    "aplay",
    "-D", "hw:CARD=sndrpihifiberry,DEV=0",
    "tests/example_recordings/white_noise_0dbfs_peak.wav",
]

_lock = threading.Lock()
_proc = None  # currently running aplay subprocess, if any


def _is_playing():
    global _proc
    if _proc is None:
        return False
    if _proc.poll() is not None:
        # process finished on its own (e.g. reached end of file)
        _proc = None
        return False
    return True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    with _lock:
        return jsonify(playing=_is_playing())


@app.route("/api/play", methods=["POST"])
def play():
    global _proc
    with _lock:
        if _is_playing():
            return jsonify(playing=True, message="Already playing")
        try:
            _proc = subprocess.Popen(PLAY_CMD, cwd=REEF_RECON_DIR)
        except FileNotFoundError as exc:
            return jsonify(playing=False, error=str(exc)), 500
        return jsonify(playing=True)


@app.route("/api/stop", methods=["POST"])
def stop():
    global _proc
    with _lock:
        if not _is_playing():
            return jsonify(playing=False, message="Not playing")
        _proc.terminate()
        try:
            _proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _proc.kill()
            _proc.wait()
        _proc = None
        return jsonify(playing=False)


if __name__ == "__main__":
    # Bind to all interfaces so it's reachable from a phone on the same
    # hotspot network, e.g. http://<pi-ip-address>:5000
    app.run(host="0.0.0.0", port=5000)
