"""
ReefRecon UI - minimal web app for controlling audio on the Pi.

Independent controls:
  - Test tone: runs `aplay` inside the existing reef-recon repo
    (unmodified) as a subprocess, for a quick speaker check.
  - Recording: starts/stops the `reef-recon` systemd service that does
    the actual recording.
  - Presets: switches the 4 USER_PARAMS knobs in reef-recon's
    parameters.json between 5 named combinations, leaving every other
    field in that file untouched.
  - Diagnostic mode: toggles ENABLE_INPUT_AGC and
    ENABLE_SPECTRAL_WHITENING off/on for a "clean" diagnostic dive.
  - Reset to defaults: runs reef-recon's own
    scripts/install-pi-service.sh --enable --start, which reinstalls
    its systemd unit and resets parameters.json to factory defaults.

Exposed over a small web UI so it can be controlled from a phone
browser on the same network (e.g. a hotspot), instead of SSHing in.
"""
import json
import os
import subprocess
import threading
import time

from flask import Flask, jsonify, render_template

app = Flask(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to the existing reef-recon checkout on the Pi. Override with the
# REEF_RECON_DIR environment variable if it lives somewhere else.
REEF_RECON_DIR = os.environ.get("REEF_RECON_DIR", "/home/reefrecon/reef-recon")

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

# reef-recon's own config file. Only the 4 USER_PARAMS fields below are
# ever touched; everything else (including USER_PARAM_PRESETS, which
# is reef-recon's internal lookup table from these LOW/MED/HIGH labels
# to actual DSP values) is read and written back untouched. Reading
# and writing it requires root, see README for the sudoers setup.
PARAMETERS_PATH = "/opt/reef-recon/etc/parameters.json"

PRESETS = {
    "balanced": {
        "SNAPPING_SHRIMP_SUPPRESSION": "MED",
        "LOW_FREQUENCY_SUPPRESSION": "MED",
        "TRANSIENT_DETECTION_SENSITIVITY": "MED",
        "HARMONIC_DETECTION_SENSITIVITY": "MED",
    },
    "noise_hunter": {
        "SNAPPING_SHRIMP_SUPPRESSION": "HIGH",
        "LOW_FREQUENCY_SUPPRESSION": "HIGH",
        "TRANSIENT_DETECTION_SENSITIVITY": "LOW",
        "HARMONIC_DETECTION_SENSITIVITY": "LOW",
    },
    "sensitive": {
        "SNAPPING_SHRIMP_SUPPRESSION": "LOW",
        "LOW_FREQUENCY_SUPPRESSION": "LOW",
        "TRANSIENT_DETECTION_SENSITIVITY": "HIGH",
        "HARMONIC_DETECTION_SENSITIVITY": "HIGH",
    },
    "low_freq_focus": {
        "SNAPPING_SHRIMP_SUPPRESSION": "HIGH",
        "LOW_FREQUENCY_SUPPRESSION": "LOW",
        "TRANSIENT_DETECTION_SENSITIVITY": "MED",
        "HARMONIC_DETECTION_SENSITIVITY": "MED",
    },
    "shrimp_focus": {
        "SNAPPING_SHRIMP_SUPPRESSION": "LOW",
        "LOW_FREQUENCY_SUPPRESSION": "HIGH",
        "TRANSIENT_DETECTION_SENSITIVITY": "HIGH",
        "HARMONIC_DETECTION_SENSITIVITY": "MED",
    },
}

PRESET_LABELS = {
    "balanced": "Balanced",
    "noise_hunter": "Noise Hunter",
    "sensitive": "Sensitive",
    "low_freq_focus": "Low Freq Focus",
    "shrimp_focus": "Shrimp Focus",
}

# Script reef-recon itself provides to reinstall its systemd unit and
# reset parameters.json to factory defaults. Run exactly as given
# (sudo ./scripts/install-pi-service.sh --enable --start from within
# the repo), requires root, see README for the sudoers setup.
INSTALL_SCRIPT = os.path.join(REEF_RECON_DIR, "scripts", "install-pi-service.sh")

# Fields toggled for a "diagnostic dive" (clean, unprocessed audio to
# evaluate what the DSP stages are doing). True is reef-recon's normal
# default for both; diagnostic mode flips them to False and back.
DIAGNOSTIC_FIELDS = ["ENABLE_INPUT_AGC", "ENABLE_SPECTRAL_WHITENING"]

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


def _read_parameters():
    result = subprocess.run(
        ["sudo", "-n", "cat", PARAMETERS_PATH], capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Failed to read {PARAMETERS_PATH}")
    return json.loads(result.stdout)


def _write_parameters(data):
    result = subprocess.run(
        ["sudo", "-n", "tee", PARAMETERS_PATH],
        input=json.dumps(data, indent=2) + "\n",
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Failed to write {PARAMETERS_PATH}")


@app.route("/api/presets")
def presets_list():
    try:
        current = _read_parameters().get("USER_PARAMS", {})
    except (RuntimeError, ValueError) as exc:
        return jsonify(error=str(exc)), 500

    active = next((key for key, values in PRESETS.items() if values == current), None)
    return jsonify(
        presets=[{"id": key, "label": PRESET_LABELS[key]} for key in PRESETS],
        active=active,
        current=current,
    )


@app.route("/api/presets/<preset_id>", methods=["POST"])
def presets_apply(preset_id):
    if preset_id not in PRESETS:
        return jsonify(error=f"Unknown preset '{preset_id}'"), 404

    try:
        data = _read_parameters()
        data["USER_PARAMS"] = PRESETS[preset_id]
        _write_parameters(data)
    except (RuntimeError, ValueError) as exc:
        return jsonify(error=str(exc)), 500

    was_active = _systemctl("is-active").stdout.strip() == "active"
    if was_active:
        _systemctl("stop")
        start_result = _systemctl("start")
        if start_result.returncode != 0:
            error = (
                start_result.stderr.strip()
                or "Applied preset, but failed to restart recording with it"
            )
            return jsonify(active=False, applied=preset_id, error=error), 500

    return jsonify(active=was_active, applied=preset_id)


@app.route("/api/reset-defaults", methods=["POST"])
def reset_defaults():
    result = subprocess.run(
        ["sudo", "-n", INSTALL_SCRIPT, "--enable", "--start"],
        cwd=REEF_RECON_DIR, capture_output=True, text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return jsonify(error=output or "install-pi-service.sh failed"), 500
    return jsonify(ok=True, output=output)


@app.route("/api/diagnostic")
def diagnostic_status():
    try:
        data = _read_parameters()
    except (RuntimeError, ValueError) as exc:
        return jsonify(error=str(exc)), 500
    active = all(data.get(field) is False for field in DIAGNOSTIC_FIELDS)
    return jsonify(active=active)


@app.route("/api/diagnostic/<state>", methods=["POST"])
def diagnostic_set(state):
    if state not in ("on", "off"):
        return jsonify(error=f"Unknown diagnostic state '{state}'"), 404

    try:
        data = _read_parameters()
        for field in DIAGNOSTIC_FIELDS:
            data[field] = (state == "off")
        _write_parameters(data)
    except (RuntimeError, ValueError) as exc:
        return jsonify(error=str(exc)), 500

    was_active = _systemctl("is-active").stdout.strip() == "active"
    if was_active:
        _systemctl("stop")
        start_result = _systemctl("start")
        if start_result.returncode != 0:
            error = (
                start_result.stderr.strip()
                or "Changed diagnostic mode, but failed to restart recording with it"
            )
            return jsonify(active=False, diagnostic=(state == "on"), error=error), 500

    return jsonify(active=was_active, diagnostic=(state == "on"))


if __name__ == "__main__":
    # Bind to all interfaces so it's reachable from a phone on the same
    # hotspot network, e.g. http://<pi-ip-address>:5000
    app.run(host="0.0.0.0", port=5000)
