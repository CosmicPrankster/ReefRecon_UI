const statusEl = document.getElementById("status");
const playBtn = document.getElementById("play-btn");
const stopBtn = document.getElementById("stop-btn");

function render(playing) {
  statusEl.textContent = playing ? "Playing…" : "Stopped";
  playBtn.disabled = playing;
  stopBtn.disabled = !playing;
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    render(data.playing);
  } catch (err) {
    statusEl.textContent = "Can't reach the Pi";
  }
}

async function call(endpoint) {
  playBtn.disabled = true;
  stopBtn.disabled = true;
  try {
    const res = await fetch(endpoint, { method: "POST" });
    const data = await res.json();
    if (data.error) {
      statusEl.textContent = `Error: ${data.error}`;
    } else {
      render(data.playing);
    }
  } catch (err) {
    statusEl.textContent = "Can't reach the Pi";
  }
}

playBtn.addEventListener("click", () => call("/api/play"));
stopBtn.addEventListener("click", () => call("/api/stop"));

refreshStatus();
setInterval(refreshStatus, 2000);
