# ReefRecon UI

A minimal web app that lets you control the Pi from your phone's
browser instead of SSHing in and typing commands by hand. It runs
alongside the existing `reef-recon` repo/service without touching
either — it just shells out the same commands you'd type manually:

- **Test tone**: runs `aplay ... white_noise_0dbfs_peak.wav` inside
  `reef-recon`.
- **Recording**: runs `sudo systemctl start/stop reef-recon`.
- **Presets**: switches the 4 `USER_PARAMS` knobs in reef-recon's
  `parameters.json` between 5 named combinations (Balanced, Noise
  Hunter, Sensitive, Low Freq Focus, Shrimp Focus). Every other field
  in that file — including `USER_PARAM_PRESETS`, reef-recon's own
  lookup table — is read and written back untouched.
- **Diagnostic Mode**: toggles `ENABLE_INPUT_AGC` and
  `ENABLE_SPECTRAL_WHITENING` off/on in `parameters.json`, for
  listening to clean/unprocessed audio during a diagnostic dive.
- **Reset to defaults**: runs reef-recon's own
  `sudo ./scripts/install-pi-service.sh --enable --start`, which
  reinstalls its systemd unit and resets `parameters.json` to factory
  defaults.

Presets, Diagnostic Mode, and Reset to defaults all restart the
`reef-recon` service if (and only if) it's already recording, so the
new settings take effect immediately without surprise-starting a
recording that wasn't running. Reset to defaults is the one exception
— `--start` always starts it, matching the command as given.

## Setup on the Pi

1. Clone/copy this repo onto the Pi. `app.py` defaults to looking for
   `reef-recon` at `/home/reefrecon/reef-recon`. If yours lives
   somewhere else, either edit `REEF_RECON_DIR` at the top of `app.py`
   directly, or set the `REEF_RECON_DIR` environment variable to the
   full path before starting the app (the env var takes precedence).

2. Install dependencies (one-time):

   ```bash
   cd ReefRecon_UI
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Allow the app to control `reef-recon` and its config without a sudo
   password prompt (the web app has no terminal to type one into).
   Find the full paths first:

   ```bash
   which systemctl cat tee   # confirm these paths before pasting below
   ```

   Then add a sudoers drop-in (no editor navigation needed — adjust
   any path below that didn't match what `which` printed, and the
   `reef-recon` path if your checkout isn't at
   `/home/reefrecon/reef-recon`):

   ```bash
   echo "$(whoami) ALL=(ALL) NOPASSWD: \
   /usr/bin/systemctl start reef-recon, \
   /usr/bin/systemctl stop reef-recon, \
   /usr/bin/systemctl is-active reef-recon, \
   /usr/bin/cat /opt/reef-recon/etc/parameters.json, \
   /usr/bin/tee /opt/reef-recon/etc/parameters.json, \
   /home/reefrecon/reef-recon/scripts/install-pi-service.sh --enable --start" \
   | sudo tee /etc/sudoers.d/reefrecon-ui
   sudo chmod 0440 /etc/sudoers.d/reefrecon-ui
   sudo visudo -c
   ```

   This grants passwordless sudo for exactly those commands — nothing
   broader. (The multi-line `\` continuations above are just for
   readability; `visudo -c` will tell you if anything didn't parse.)

4. Run the app:

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
4. Under **Recording**, tap **Start recording** / **Stop recording** to
   run `sudo systemctl start/stop reef-recon`. The status line shows
   whether it's currently recording (polled every 2s).
5. Under **Test tone**, tap **Play white noise** to run:

   ```bash
   cd reef-recon
   aplay -D hw:CARD=sndrpihifiberry,DEV=0 tests/example_recordings/white_noise_0dbfs_peak.wav
   ```

   Tap **Stop** to kill the playback early.

6. Under **Noise Filter Preset**, tap any of the 5 presets to rewrite
   `USER_PARAMS` in `parameters.json` to that combination. The status
   line shows which preset (if any) matches the file's current
   values — "Custom" means it was edited manually and doesn't match
   any of the 5.
7. Under **Diagnostic Mode**, tap **Enable**/**Disable** to flip
   `ENABLE_INPUT_AGC` and `ENABLE_SPECTRAL_WHITENING` off/on for a
   diagnostic dive.
8. Under **Maintenance**, tap **Reset to defaults** to run
   reef-recon's own `install-pi-service.sh --enable --start`. This
   asks for confirmation first since it resets `parameters.json` and
   always starts a recording, even if one wasn't running.

If any action fails (missing file, bad ALSA device, sudoers not set up,
etc.) the error message appears directly in the UI instead of only in
the terminal.

## Optional: run as a systemd service

Running `python3 app.py` directly means the app dies the moment your
SSH session ends — including just closing your laptop lid, which
drops the connection. If you want it to keep running regardless (and
restart automatically if it ever crashes, and start on boot),
`deploy/reefrecon-ui.service` is provided, already configured for this
Pi's user/paths:

```bash
sudo cp deploy/reefrecon-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reefrecon-ui
```

(If your username or clone path is ever different from
`reefrecon`/`~/ReefRecon_UI`, edit `User=` and the two paths in the
`.service` file before copying it, then `daemon-reload` again.)

```bash
sudo systemctl status reefrecon-ui
journalctl -u reefrecon-ui -f   # live logs, Ctrl+C to exit
```

This is entirely optional — everything above works fine with a plain
`python3 app.py` in a terminal too.

This is intentionally minimal as a starting point to build on.
