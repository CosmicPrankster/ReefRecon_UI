# ReefRecon UI

A minimal web app that lets you control the Pi from your phone's
browser instead of SSHing in and typing commands by hand. It runs
alongside the existing `reef-recon` repo/service without touching
either — it just shells out the same commands you'd type manually:

- **Test tone**: runs `aplay ... white_noise_0dbfs_peak.wav` inside
  `reef-recon`.
- **Recording**: runs `sudo systemctl start/stop reef-recon`.
- **Update**: runs `git pull` on this repo and restarts itself, so
  changes pushed to GitHub show up without SSHing back into the Pi.

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

3. Allow the app to start/stop the `reef-recon` service without a sudo
   password prompt (the web app has no terminal to type one into).
   Find the full path to `systemctl` first:

   ```bash
   which systemctl   # usually /usr/bin/systemctl or /bin/systemctl
   ```

   Then run `sudo visudo` and add this line at the end (replace
   `pi` with whichever user will run the app, and the path with
   whatever `which systemctl` printed):

   ```
   pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl start reef-recon, /usr/bin/systemctl stop reef-recon, /usr/bin/systemctl is-active reef-recon
   ```

   This grants passwordless sudo for exactly those three commands on
   exactly that service — nothing broader.

4. Install the app itself as a systemd service, so it survives reboots
   and SSH disconnects, and so **Check for updates** actually works
   (see note below on why this is required, not optional):

   ```bash
   sudo cp deploy/reefrecon-ui.service /etc/systemd/system/
   sudo nano /etc/systemd/system/reefrecon-ui.service   # fix User/paths for your setup
   sudo systemctl daemon-reload
   sudo systemctl enable --now reefrecon-ui
   ```

   Check it started cleanly:

   ```bash
   sudo systemctl status reefrecon-ui
   journalctl -u reefrecon-ui -f   # live logs, Ctrl+C to exit
   ```

   From now on you never need to run `python3 app.py` by hand — the
   service starts it on boot and restarts it if it ever exits.

## Using it from your phone

1. Connect both the Pi and your phone to the same personal hotspot
   (same as your current SSH workflow).
2. Find the Pi's IP address on that network (e.g. `hostname -I` on the
   Pi).
3. On your phone, open a browser and go to `http://<pi-ip>:5000`.
4. Under **Recording**, tap **Start recording** / **Stop recording** to
   run `sudo systemctl start/stop reef-recon`. The status line shows
   whether it's currently recording (polled every 2s).
5. Under **Test tone**, tap **Play white noise** to run:

   ```bash
   cd reef-recon
   aplay -D hw:CARD=sndrpihifiberry,DEV=0 tests/example_recordings/white_noise_0dbfs_peak.wav
   ```

   Tap **Stop** to kill the playback early.

6. Under **App**, tap **Check for updates** to `git pull` the latest
   pushed changes and restart automatically. The page reloads itself
   once the app is back online (usually a couple seconds).

If any action fails (missing file, bad ALSA device, sudoers not set up,
a `git pull` conflict, etc.) the error message appears directly in the
UI instead of only in the terminal.

### A note on self-update

`git pull` only fast-forwards — if you've made local edits directly on
the Pi (not recommended) it will fail with a clear error instead of
overwriting them.

**The systemd service in step 4 is required for the Update button to
work**, not just a nice-to-have: after pulling, the app exits on
purpose (`os._exit`) so the new code gets loaded on the next start.
Something has to actually restart the process — that's what
`Restart=always` in `reefrecon-ui.service` does, a couple seconds
later once the port is free. If you instead run `python3 app.py`
directly in a terminal, hitting Update will just kill it and you'll
be back to typing commands over SSH to bring it back up.

This is intentionally minimal as a starting point to build on.
