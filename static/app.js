const playbackStatusEl = document.getElementById("playback-status");
const playbackDot = document.getElementById("playback-dot");
const playBtn = document.getElementById("play-btn");
const stopBtn = document.getElementById("stop-btn");

const recordingStatusEl = document.getElementById("recording-status");
const recordingDot = document.getElementById("recording-dot");
const recordingStartBtn = document.getElementById("recording-start-btn");
const recordingStopBtn = document.getElementById("recording-stop-btn");

const presetStatusEl = document.getElementById("preset-status");
const presetButtons = Array.from(document.querySelectorAll("[data-preset]"));
const presetLabels = {};
presetButtons.forEach((btn) => { presetLabels[btn.dataset.preset] = btn.textContent; });

const diagnosticStatusEl = document.getElementById("diagnostic-status");
const diagnosticDot = document.getElementById("diagnostic-dot");
const diagnosticOnBtn = document.getElementById("diagnostic-on-btn");
const diagnosticOffBtn = document.getElementById("diagnostic-off-btn");

const resetStatusEl = document.getElementById("reset-status");
const resetBtn = document.getElementById("reset-btn");

const errorBanner = document.getElementById("error-banner");

function showError(message) {
  if (!message) {
    errorBanner.classList.add("hidden");
    errorBanner.textContent = "";
    return;
  }
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

function renderPlayback(playing) {
  playbackStatusEl.textContent = playing ? "Playing…" : "Stopped";
  playbackDot.classList.toggle("on", playing);
  playbackDot.classList.toggle("off", !playing);
  playBtn.disabled = playing;
  stopBtn.disabled = !playing;
}

function renderRecording(active) {
  recordingStatusEl.textContent = active ? "Recording" : "Not recording";
  recordingDot.classList.toggle("on", active);
  recordingDot.classList.toggle("off", !active);
  recordingStartBtn.disabled = active;
  recordingStopBtn.disabled = !active;
}

function renderPresets(active, busy) {
  presetStatusEl.textContent = active
    ? `Active: ${presetLabels[active]}`
    : "Custom (doesn't match a preset)";
  presetButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.preset === active);
    btn.disabled = busy || btn.dataset.preset === active;
  });
}

function renderDiagnostic(active) {
  diagnosticStatusEl.textContent = active ? "Diagnostic mode ON" : "Diagnostic mode OFF";
  diagnosticDot.classList.toggle("on", active);
  diagnosticDot.classList.toggle("off", !active);
  diagnosticOnBtn.disabled = active;
  diagnosticOffBtn.disabled = !active;
}

async function refreshPlaybackStatus() {
  try {
    const res = await fetch("/api/playback/status");
    const data = await res.json();
    renderPlayback(data.playing);
    if (data.error) showError(data.error);
  } catch (err) {
    playbackStatusEl.textContent = "Can't reach the Pi";
  }
}

async function refreshRecordingStatus() {
  try {
    const res = await fetch("/api/recording/status");
    const data = await res.json();
    renderRecording(data.active);
  } catch (err) {
    recordingStatusEl.textContent = "Can't reach the Pi";
  }
}

async function refreshPresets() {
  try {
    const res = await fetch("/api/presets");
    const data = await res.json();
    if (data.error) {
      presetStatusEl.textContent = "Error reading presets";
      showError(data.error);
      return;
    }
    renderPresets(data.active, false);
  } catch (err) {
    presetStatusEl.textContent = "Can't reach the Pi";
  }
}

async function refreshDiagnostic() {
  try {
    const res = await fetch("/api/diagnostic");
    const data = await res.json();
    if (data.error) {
      diagnosticStatusEl.textContent = "Error reading diagnostic mode";
      showError(data.error);
      return;
    }
    renderDiagnostic(data.active);
  } catch (err) {
    diagnosticStatusEl.textContent = "Can't reach the Pi";
  }
}

async function call(endpoint, onResult) {
  try {
    const res = await fetch(endpoint, { method: "POST" });
    const data = await res.json();
    if (data.error) {
      showError(data.error);
    } else {
      showError(null);
    }
    onResult(data);
  } catch (err) {
    showError("Can't reach the Pi");
  }
}

playBtn.addEventListener("click", () => {
  playBtn.disabled = true;
  stopBtn.disabled = true;
  call("/api/playback/play", (data) => renderPlayback(data.playing));
});

stopBtn.addEventListener("click", () => {
  playBtn.disabled = true;
  stopBtn.disabled = true;
  call("/api/playback/stop", (data) => renderPlayback(data.playing));
});

recordingStartBtn.addEventListener("click", () => {
  recordingStartBtn.disabled = true;
  recordingStopBtn.disabled = true;
  call("/api/recording/start", (data) => renderRecording(data.active));
});

recordingStopBtn.addEventListener("click", () => {
  recordingStartBtn.disabled = true;
  recordingStopBtn.disabled = true;
  call("/api/recording/stop", (data) => renderRecording(data.active));
});

presetButtons.forEach((btn) => {
  btn.addEventListener("click", async () => {
    presetButtons.forEach((b) => { b.disabled = true; });
    presetStatusEl.textContent = `Applying ${presetLabels[btn.dataset.preset]}…`;
    await call(`/api/presets/${btn.dataset.preset}`, (data) => {
      renderPresets(data.applied && !data.error ? data.applied : null, false);
    });
    refreshPresets();
    refreshRecordingStatus();
  });
});

diagnosticOnBtn.addEventListener("click", () => {
  diagnosticOnBtn.disabled = true;
  diagnosticOffBtn.disabled = true;
  call("/api/diagnostic/on", (data) => renderDiagnostic(data.diagnostic)).then(() => {
    refreshRecordingStatus();
  });
});

diagnosticOffBtn.addEventListener("click", () => {
  diagnosticOnBtn.disabled = true;
  diagnosticOffBtn.disabled = true;
  call("/api/diagnostic/off", (data) => renderDiagnostic(data.diagnostic)).then(() => {
    refreshRecordingStatus();
  });
});

resetBtn.addEventListener("click", async () => {
  if (!confirm("Reset all parameters to factory defaults and start recording now?")) {
    return;
  }
  resetBtn.disabled = true;
  resetStatusEl.textContent = "Resetting…";
  try {
    const res = await fetch("/api/reset-defaults", { method: "POST" });
    const data = await res.json();
    if (data.error) {
      showError(data.error);
      resetStatusEl.textContent = "Reset failed";
    } else {
      showError(null);
      resetStatusEl.textContent = "Reset complete";
      refreshPresets();
      refreshDiagnostic();
      refreshRecordingStatus();
    }
  } catch (err) {
    showError("Can't reach the Pi");
    resetStatusEl.textContent = "Reset failed";
  }
  resetBtn.disabled = false;
});

refreshPlaybackStatus();
refreshRecordingStatus();
refreshPresets();
refreshDiagnostic();
setInterval(refreshPlaybackStatus, 2000);
setInterval(refreshRecordingStatus, 2000);
setInterval(refreshPresets, 4000);
setInterval(refreshDiagnostic, 4000);
