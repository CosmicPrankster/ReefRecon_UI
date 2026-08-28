"""
ReefRecon UI - minimal web app for controlling audio on the Pi.

Two independent controls:
  - Test tone: runs `aplay` inside the existing reef-recon repo
    (unmodified) as a subprocess, for a quick speaker check.
  - Recording: starts/stops the `reef-recon` systemd service that does
    the actual recording.

Exposed over a small web UI so it can be controlled from a phone
browser on the same network (e.g. a hotspot), instead of SSHing in.
"""
import os
import subprocess
import threading
import time

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
WAV_PATH = os.path.join(REEF_RECON_DIR, "tests/example_recordings/white_noise_0dbfs_peak.wav")

# systemd unit that runs the actual recording. Starting/stopping it
# requires root, see README for the required passwordless-sudo setup.
RECORDING_SERVICE = "reef-recon"

_lock = threading.Lock()
_proc = None  # currently running aplay subprocess, if any
_last_play_error = None


def _is_playing():
    global _proc
    if _proc is None:
        return False
    if _proc.poll() is not None:
        # process finished on its own (e.g. reached end of file)
        _proc = None
        return False
    return True


def _watch_playback(proc):
    """Runs in a background thread; captures aplay's stderr so failures
    that happen after the initial request (e.g. device errors) still
    surface in the UI."""
    global _last_play_error
    stderr_output = proc.stderr.read() if proc.stderr else ""
    proc.wait()
    if proc.returncode != 0:
        _last_play_error = stderr_output.strip() or f"aplay exited with code {proc.returncode}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/playback/status")
def playback_status():
    with _lock:
        return jsonify(playing=_is_playing(), error=_last_play_error)


@app.route("/api/playback/play", methods=["POST"])
def playback_play():
    global _proc, _last_play_error
    with _lock:
        if _is_playing():
            return jsonify(playing=True, message="Already playing")

        _last_play_error = None

        if not os.path.isfile(WAV_PATH):
            error = f"White noise file not found at {WAV_PATH}. Check REEF_RECON_DIR."
            _last_play_error = error
            return jsonify(playing=False, error=error), 500

        try:
            _proc = subprocess.Popen(
                PLAY_CMD, cwd=REEF_RECON_DIR,
                stderr=subprocess.PIPE, text=True,
            )
        except FileNotFoundError as exc:
            _last_play_error = str(exc)
            return jsonify(playing=False, error=str(exc)), 500

        threading.Thread(target=_watch_playback, args=(_proc,), daemon=True).start()

    # Give aplay a brief moment to fail fast (e.g. bad ALSA device) so
    # the error can be returned in this same response.
    time.sleep(0.3)

    with _lock:
        if _proc is not None and _proc.poll() is not None:
            error = _last_play_error or f"aplay exited with code {_proc.returncode}"
            _proc = None
            return jsonify(playing=False, error=error), 500
        return jsonify(playing=True)


@app.route("/api/playback/stop", methods=["POST"])
def playback_stop():
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


def _systemctl(*args):
    return subprocess.run(
        ["sudo", "-n", "systemctl", *args, RECORDING_SERVICE],
        capture_output=True, text=True,
    )


@app.route("/api/recording/status")
def recording_status():
    result = _systemctl("is-active")
    state = result.stdout.strip() or result.stderr.strip()
    return jsonify(active=(state == "active"), state=state)


@app.route("/api/recording/start", methods=["POST"])
def recording_start():
    result = _systemctl("start")
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip() or "Failed to start recording"
        return jsonify(active=False, error=error), 500
    return jsonify(active=True)


@app.route("/api/recording/stop", methods=["POST"])
def recording_stop():
    result = _systemctl("stop")
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip() or "Failed to stop recording"
        return jsonify(active=True, error=error), 500
    return jsonify(active=False)


if __name__ == "__main__":
    # Bind to all interfaces so it's reachable from a phone on the same
    # hotspot network, e.g. http://<pi-ip-address>:5000
    app.run(host="0.0.0.0", port=5000)
