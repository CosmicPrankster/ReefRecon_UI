# ReefRecon UI

A minimal web app that lets you play/stop an audio test track on the Pi
from your phone's browser, instead of SSHing in and typing the command
by hand. It runs alongside the existing `reef-recon` repo without
touching anything in it — it just shells out to `aplay` the same way you
do manually.

## Setup on the Pi

1. Clone/copy this repo onto the Pi, e.g. as a sibling of `reef-recon`:

   ```
   ~/reef-recon
   ~/ReefRecon_UI
   ```

   If it lives somewhere else, set the `REEF_RECON_DIR` environment
   variable to the full path of your `reef-recon` checkout before
   starting the app.

2. Install dependencies (one-time):

   ```bash
   cd ReefRecon_UI
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   source venv/bin/activate   # if not already active
   python3 app.py
   ```

   You should see it start on `http://0.0.0.0:5000`.

## Using it from your phone

1. Connect both the Pi and your phone to the same personal hotspot
   (same as your current SSH workflow).
2. Find the Pi's IP address on that network (e.g. `hostname -I` on the
   Pi).
3. On your phone, open a browser and go to `http://<pi-ip>:5000`.
4. Tap **Play white noise** to run:

   ```bash
   cd reef-recon
   aplay -D hw:CARD=sndrpihifiberry,DEV=0 tests/example_recordings/white_noise_0dbfs_peak.wav
   ```

   Tap **Stop** to kill the playback early.

This is intentionally minimal — one command, one button — as a starting
point to build on.
