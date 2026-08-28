const playbackStatusEl = document.getElementById("playback-status");
const playBtn = document.getElementById("play-btn");
const stopBtn = document.getElementById("stop-btn");

const recordingStatusEl = document.getElementById("recording-status");
const recordingStartBtn = document.getElementById("recording-start-btn");
const recordingStopBtn = document.getElementById("recording-stop-btn");

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
  playBtn.disabled = playing;
  stopBtn.disabled = !playing;
}

function renderRecording(active) {
  recordingStatusEl.textContent = active ? "Recording" : "Not recording";
  recordingStartBtn.disabled = active;
  recordingStopBtn.disabled = !active;
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

refreshPlaybackStatus();
refreshRecordingStatus();
setInterval(refreshPlaybackStatus, 2000);
setInterval(refreshRecordingStatus, 2000);
