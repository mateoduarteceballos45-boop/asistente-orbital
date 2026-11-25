import io
import os
import re
import time
import threading
import urllib.parse
import webbrowser
import zipfile

import psutil
import pyautogui
import pyperclip
import sounddevice as sd
import speech_recognition as sr
import webview
from flask import Flask, jsonify, render_template_string, request
from scipy.io.wavfile import write as write_wav

app = Flask(__name__)

# Configuración general de automatización
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.25

OPERA_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\launcher.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
    r"C:\Program Files\Opera GX\launcher.exe",
    r"C:\Program Files\Opera\launcher.exe",
]

DISCORD_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\DiscordCanary\Update.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\DiscordPTB\Update.exe"),
]


def get_system_stats():
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    return {
        "cpu": round(psutil.cpu_percent(interval=0.2), 1),
        "ram": round(vm.percent, 1),
        "disk": round(disk.percent, 1),
    }


def open_in_browser(url: str):
    for path in OPERA_PATHS:
        if path and os.path.exists(path):
            try:
                os.startfile(f'"{path}" "{url}"')
                return
            except Exception:
                pass
    webbrowser.open(url)


def search_google(query: str):
    q = urllib.parse.quote_plus(query.strip())
    open_in_browser(f"https://www.google.com/search?q={q}")


def search_youtube(query: str):
    q = urllib.parse.quote_plus(query.strip())
    open_in_browser(f"https://www.youtube.com/results?search_query={q}")


def launch_discord_if_needed():
    running = any(
        "discord" in (p.info.get("name") or "").lower()
        for p in psutil.process_iter(["name"])
    )
    if not running:
        for path in DISCORD_PATHS:
            if path and os.path.exists(path):
                try:
                    if path.lower().endswith("update.exe"):
                        os.startfile(f'"{path}" --processStart Discord.exe')
                    else:
                        os.startfile(path)
                    time.sleep(4)
                    return
                except Exception:
                    pass


def send_discord_dm_ui(recipient: str, message: str) -> str:
    launch_discord_if_needed()
    try:
        # Abrir buscador rápido de Discord (Ctrl+K)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.5)
        pyperclip.copy(recipient)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(0.8)

        # Pegar y enviar mensaje en el chat activo
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.25)
        pyautogui.press("enter")
        return f"Mensaje enviado a {recipient} vía Discord."
    except Exception as e:
        return f"Error en automatización de Discord: {e}"


def listen_once(sample_rate: int = 16000, duration: int = 4) -> str:
    recognizer = sr.Recognizer()
    try:
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        wav_buffer = io.BytesIO()
        write_wav(wav_buffer, sample_rate, audio_data)
        wav_buffer.seek(0)

        with sr.AudioFile(wav_buffer) as source:
            recorded = recognizer.record(source)

        text = recognizer.recognize_google(recorded, language="es-ES")
        return text.strip()
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        return f"[error_voz: {e}]"


def process_command(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    lower = text.lower()

    if not text:
        return {"ok": False, "reply": "No detecté ningún comando."}

    if lower.startswith("buscar en google ") or lower.startswith("busca en google "):
        query = re.sub(r"^(buscar|busca) en google\s+", "", text, flags=re.I)
        search_google(query)
        return {"ok": True, "reply": f"Buscando en Google: {query}"}

    if lower.startswith("buscar en youtube ") or lower.startswith("busca en youtube ") or lower.startswith("youtube "):
        query = re.sub(r"^((buscar|busca) en youtube|youtube)\s+", "", text, flags=re.I)
        search_youtube(query)
        return {"ok": True, "reply": f"Buscando en YouTube: {query}"}

    dm_match = re.match(r"^(?:enviar|manda|mandar)\s+(?:por\s+)?discord\s+a\s+([^:]+):\s*(.+)$", text, flags=re.I)
    if dm_match:
        recipient = dm_match.group(1).strip()
        msg = dm_match.group(2).strip()
        status = send_discord_dm_ui(recipient, msg)
        return {"ok": True, "reply": status}

    if "estado" in lower or "sistema" in lower or "rendimiento" in lower:
        s = get_system_stats()
        return {
            "ok": True,
            "reply": f"CPU {s['cpu']}% · RAM {s['ram']}% · Disco {s['disk']}%",
        }

    return {
        "ok": True,
        "reply": f"Comando recibido: '{text}'. Usa 'buscar en google ...', 'youtube ...', 'estado' o 'enviar discord a usuario: mensaje'.",
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Orbital Assistant</title>
<style>
  :root {
    --bg: #070b14;
    --panel: rgba(14, 22, 38, 0.88);
    --accent: #38bdf8;
    --accent-2: #818cf8;
    --text: #e2e8f0;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: "Segoe UI", system-ui, sans-serif; }
  body {
    background: radial-gradient(circle at center, #0f1c33 0%, var(--bg) 75%);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 16px;
  }
  .top-bar {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 12px;
    background: var(--panel);
    padding: 8px 12px;
    border-radius: 999px;
    border: 1px solid rgba(56, 189, 248, 0.25);
  }
  .stage {
    position: relative;
    width: 250px;
    height: 250px;
    margin: auto;
    display: grid;
    place-items: center;
  }
  .ring {
    position: absolute;
    width: 210px;
    height: 210px;
    border-radius: 50%;
    border: 1px dashed rgba(56, 189, 248, 0.35);
    animation: spin 18s linear infinite;
  }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .core {
    width: 82px;
    height: 82px;
    border-radius: 50%;
    border: none;
    cursor: pointer;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: #04101f;
    font-weight: 700;
    box-shadow: 0 0 28px rgba(56, 189, 248, 0.45);
    z-index: 2;
  }
  .orbit-btn {
    position: absolute;
    width: 42px;
    height: 42px;
    border-radius: 50%;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: var(--panel);
    color: var(--text);
    cursor: pointer;
    font-size: 15px;
  }
  .orbit-btn:hover { border-color: var(--accent); transform: scale(1.08); }
  .b1 { top: 6px; left: 50%; transform: translateX(-50%); }
  .b2 { bottom: 6px; left: 50%; transform: translateX(-50%); }
  .b3 { left: 6px; top: 50%; transform: translateY(-50%); }
  .b4 { right: 6px; top: 50%; transform: translateY(-50%); }
  .console {
    background: var(--panel);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .status { font-size: 12px; color: var(--muted); min-height: 18px; }
  .row { display: flex; gap: 6px; }
  input {
    flex: 1;
    background: rgba(2, 6, 23, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 8px;
    padding: 7px 10px;
    color: var(--text);
    font-size: 13px;
  }
  button.send {
    background: var(--accent);
    color: #04101f;
    border: none;
    border-radius: 8px;
    padding: 0 12px;
    font-weight: 600;
    cursor: pointer;
  }
</style>
</head>
<body>
  <div class="top-bar">
    <span id="cpu">CPU: --%</span>
    <span id="ram">RAM: --%</span>
    <span id="disk">DISK: --%</span>
  </div>

  <div class="stage">
    <div class="ring"></div>
    <button class="core" onclick="voiceListen()">VOZ</button>
    <button class="orbit-btn b1" title="Google" onclick="quickCmd('buscar en google noticias')">G</button>
    <button class="orbit-btn b2" title="YouTube" onclick="quickCmd('youtube musica')">▶</button>
    <button class="orbit-btn b3" title="Estado" onclick="quickCmd('estado')">⚙</button>
    <button class="orbit-btn b4" title="Discord" onclick="promptDiscord()">💬</button>
  </div>

  <div class="console">
    <div class="status" id="status">Listo. Escribe o pulsa VOZ.</div>
    <div class="row">
      <input id="cmdInput" placeholder="Ej: buscar en google python / enviar discord a amigo: hola" onkeydown="if(event.key==='Enter') sendCmd()" />
      <button class="send" onclick="sendCmd()">Enviar</button>
    </div>
  </div>

<script>
  const statusEl = document.getElementById("status");
  const inputEl = document.getElementById("cmdInput");

  async function refreshStats() {
    try {
      const r = await fetch("/api/stats");
      const d = await r.json();
      document.getElementById("cpu").textContent = `CPU: ${d.cpu}%`;
      document.getElementById("ram").textContent = `RAM: ${d.ram}%`;
      document.getElementById("disk").textContent = `DISK: ${d.disk}%`;
    } catch (_) {}
  }

  async function sendText(text) {
    if (!text.trim()) return;
    statusEl.textContent = "Ejecutando...";
    const r = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: text })
    });
    const d = await r.json();
    statusEl.textContent = d.reply || "Completado.";
  }

  function sendCmd() {
    const val = inputEl.value;
    inputEl.value = "";
    sendText(val);
  }

  function quickCmd(cmd) {
    sendText(cmd);
  }

  function promptDiscord() {
    const user = prompt("Usuario o canal en Discord:");
    if (!user) return;
    const msg = prompt("Mensaje a enviar:");
    if (!msg) return;
    sendText(`enviar discord a ${user}: ${msg}`);
  }

  async function voiceListen() {
    statusEl.textContent = "Escuchando (4s)...";
    const r = await fetch("/api/listen", { method: "POST" });
    const d = await r.json();
    if (d.text) {
      statusEl.textContent = `Escuché: "${d.text}"`;
      await sendText(d.text);
    } else {
      statusEl.textContent = "No se entendió el audio.";
    }
  }

  refreshStats();
  setInterval(refreshStats, 2500);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/stats")
def api_stats():
    return jsonify(get_system_stats())


@app.route("/api/command", methods=["POST"])
def api_command():
    data = request.get_json(silent=True) or {}
    result = process_command(data.get("command", ""))
    return jsonify(result)


@app.route("/api/listen", methods=["POST"])
def api_listen():
    text = listen_once()
    return jsonify({"text": text})


def run_flask():
    app.run(host="127.0.0.1", port=5055, debug=False, use_reloader=False)


def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    webview.create_window(
        title="Orbital Assistant",
        url="http://127.0.0.1:5055",
        width=360,
        height=470,
        resizable=False,
        on_top=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
