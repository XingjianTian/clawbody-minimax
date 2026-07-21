# 🤖 ClawBody

**Give your AI agent a physical robot body with voice conversation!**

ClawBody combines an OpenAI-compatible LLM with Reachy Mini's expressive robot body, using Baidu ASR/TTS for Chinese/English voice conversation. The current PsyTwin deployment uses Alibaba Cloud DashScope/Qwen while retaining legacy `MINIMAX_*` environment variable names for compatibility.

> 🦞 This is a fork of [tomrikert/clawbody](https://github.com/tomrikert/clawbody) with MiniMax LLM + Baidu ASR/TTS replacing OpenAI Realtime API.

## ✨ Features

- **🎤 Real-time Voice Conversation**: Baidu ASR for speech recognition + Baidu TTS for natural voice synthesis
- **🧠 Alibaba Cloud Qwen**: OpenAI-compatible model access through DashScope
- **👁️ Face Tracking**: Real-time face detection and eye contact (MediaPipe/YOLO)
- **💃 Expressive Movements**: Natural head movements, emotions, dances, and audio-driven wobble
- **🖥️ Simulator Support**: Works with or without physical hardware (MuJoCo simulation)
- **🔧 OpenClaw Integration**: Extended AI capabilities via OpenClaw Gateway

## 🏗️ Architecture

```
Your Voice → Baidu ASR → Pet AI ───────────────→ Baidu TTS → Robot Speaks
                          │ negative emotion              ↓
                          └→ XiaoXin demo advisor → Pet relay
                ↓
         Face Tracking / Reachy Actions
```

## 📋 Prerequisites

### Hardware
- **Option A**: [Reachy Mini](https://www.pollen-robotics.com/reachy-mini/) robot (Wireless or Lite with USB)
- **Option B**: Simulator (no hardware needed) - `pip install "reachy-mini[mujoco]"`

### Software
- Python 3.11+
- [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini)
- API Keys:
  - [MiniMax](https://www.minimax.chat/) API key
  - [Baidu Smart Cloud](https://cloud.baidu.com/) APP ID + API Key + Secret Key
  - (Optional) [OpenClaw](https://github.com/openclaw/openclaw) Gateway token

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/XingjianTian/clawbody-minimax.git
cd clawbody-minimax

# Create virtual environment
python -m venv reachy_mini_env
source reachy_mini_env/bin/activate

# Install dependencies
pip install -e ".[mediapipe_vision]"
pip install sounddevice pydub

# For simulator support
pip install "reachy-mini[mujoco]"
```

## ⚙️ Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your API keys:
```bash
# Alibaba Cloud DashScope LLM (OpenAI-compatible API)
# The MINIMAX_* names are retained for compatibility with the application.
MINIMAX_API_KEY=your-dashscope-api-key
MINIMAX_MODEL=qwen-plus
MINIMAX_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MINIMAX_MAX_TOKENS=80
HTTP_TRUST_ENV=false

# Baidu ASR/TTS
BAIDU_APP_ID=your-baidu-app-id
BAIDU_API_KEY=your-baidu-api-key
BAIDU_SECRET_KEY=your-baidu-secret-key
BAIDU_TTS_PER=111        # Voice: 0=female, 1=male, 111=duboxiong
BAIDU_TTS_SPD=5          # Speed: 0-15
BAIDU_TTS_PIT=5          # Pitch: 0-15
BAIDU_TTS_VOL=12         # Volume: 0-15
BAIDU_ASR_LANGUAGE=zh-CN # Language: zh-CN or en-US

# OpenClaw (optional)
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=your-token
OPENCLAW_AGENT_ID=main

# Robot Connection
ROBOT_HOST=localhost
ROBOT_PORT=8000
```

## 🎮 Usage

### Windows Host Bridge for Reachy Mini Lite

On Windows 10/11, the Host Bridge replaces Reachy Mini Control for USB discovery and daemon lifecycle management. It listens only on `127.0.0.1:7861`, authenticates every `/v1/*` request with `X-Host-Bridge-Key`, and owns only the daemon process it starts. Reachy Mini Control must be closed before starting the device so the USB serial port and daemon port are not already in use.

Create a Python 3.11 virtual environment named `.venv`, install this project and the supported Reachy Mini SDK, then copy the environment template:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "reachy-mini==1.8.0"
python -m pip install -e ".[dev,mediapipe_vision]"
Copy-Item .env.example .env
```

Generate separate long random values for `HOST_BRIDGE_API_KEY` and `SERVICE_API_KEY`, put them only in the local `.env`, and never commit or share that file. The Host Bridge refuses to start when its key is empty or still equals the example placeholder.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep these Host Bridge values on loopback. Sentinel must use `HOST_BRIDGE_URL=http://127.0.0.1:7861` and the same `HOST_BRIDGE_API_KEY`; the key stays on the Sentinel server and must never be exposed through a `NEXT_PUBLIC_*` variable or browser code.

```dotenv
HOST_BRIDGE_HOST=127.0.0.1
HOST_BRIDGE_PORT=7861
HOST_BRIDGE_API_KEY=replace-with-a-long-random-value
HOST_BRIDGE_DAEMON_URL=http://127.0.0.1:8000
HOST_BRIDGE_CLAWBODY_HEALTH_URL=http://127.0.0.1:7860/health
```

Install the fixed current-user login task from the repository root. `install` creates or updates `PsyTwin ClawBody Host Bridge`; `status` queries it; `restart` ends that exact task instance and starts it again; `uninstall --yes` removes only that exact task.

```powershell
.\.venv\Scripts\Activate.ps1
clawbody-host install
clawbody-host status
clawbody-host restart
clawbody-host uninstall --yes
```

Normally run `install` once, then `restart` to start it immediately (otherwise it starts at the next login). Use `uninstall --yes` only when intentionally removing autostart. For foreground diagnosis, close any scheduled instance first and run `clawbody-host-bridge` in an activated terminal; do not run both copies together.

Safe checks that do not start or move the robot:

```powershell
Invoke-RestMethod http://127.0.0.1:7861/health
$hostBridgeKey = Read-Host "HOST_BRIDGE_API_KEY"
Invoke-RestMethod http://127.0.0.1:7861/v1/device/discover -Headers @{"X-Host-Bridge-Key"=$hostBridgeKey}
```

The Host Bridge manages the Windows daemon at `127.0.0.1:8000`. The ClawBody Docker container reaches that same daemon at `host.docker.internal:8000`; port `7861` remains host-loopback-only and is not published to Docker. Device startup itself does not require a VPN and does not access Hugging Face, GitHub, OpenAI, or an application catalog. Online conversation still requires the configured Alibaba Cloud and Baidu services.

Daily operation is: start Docker, open Sentinel, select **心宠调试**, then click **启动设备**. Keep Reachy Mini Control closed.

### Sentinel Internal Service (Recommended)

The supported management UI is PsyTwin Sentinel. Start this project as a private device service; it does not expose a standalone web console:

```bash
clawbody-service
```

Configure `SERVICE_HOST`, `SERVICE_PORT`, and `SERVICE_API_KEY` in `.env`, then set the matching `CLAWBODY_SERVICE_URL` and `CLAWBODY_SERVICE_KEY` in Sentinel. The supported Docker runtime uses one headless container bound to `127.0.0.1:7860`.

The authenticated internal API provides:

- `GET /health` and `GET /v1/status` for service and device state.
- `POST /v1/session/start` and `POST /v1/session/stop` for the single Reachy session.
- `GET /v1/transcript?after=<cursor>` for in-memory ASR/final-response updates.
- `GET /v1/events?after=<cursor>` for the structured two-layer collaboration timeline.
- `POST /v1/text/respond` for a text-only rehearsal without microphone capture.

All `/v1/*` requests require `X-Service-Key`. Transcripts and collaboration events are memory-only, bounded to the latest 100 items, and are cleared when the session stops or the service restarts.

Starting a hardware session returns immediately with `state: "starting"`. Reachy connection, camera, audio, and movement initialization continue in a background thread so `/health`, status polling, and the Sentinel UI remain responsive. The state changes to `running` when initialization finishes, or to `error` with a readable message when it fails.

For local Reachy daemon playback, ClawBody adapts mono Baidu TTS output to the device's reported output-channel count, queues contiguous timestamped chunks without per-chunk scheduler gaps, and then waits for the full clip duration. This prevents live `appsrc` underruns and truncated playback. No extra setting is required; restart the internal service after updating the code.

### With Physical Robot (USB, diagnostics)

```bash
# Terminal 1: Start the desktop app (or daemon)
# The app must be running before starting ClawBody

# Terminal 2: Run ClawBody with USB connection
clawbody --usb

# The legacy Gradio UI remains available only for local diagnostics
clawbody --usb --gradio
```

### With Simulator

```bash
# Terminal 1: Start simulator
reachy-mini-daemon --sim

# Terminal 2: Run ClawBody
clawbody --gradio
```

### With Docker Desktop

See the step-by-step Chinese setup guide: [DOCKER_SETUP.md](DOCKER_SETUP.md).

For a new Windows computer, clone the repository, create a local configuration,
then start the robot and container:

```powershell
git clone https://github.com/XingjianTian/clawbody-minimax.git
cd clawbody-minimax
Copy-Item .env.example .env
notepad .env
docker compose up -d --build
```

Enter that person's own DashScope and Baidu credentials in `.env`; never commit
this file or share it through Git. Keep Reachy Mini Control closed. The Windows
Host Bridge starts the Reachy daemon at `127.0.0.1:8000` when Sentinel requests
**启动设备**.

Open this repository in Docker Desktop as a Compose project and click **Run**.
The container starts the private `clawbody-service` process and connects to the
host daemon through `host.docker.internal:8000`. It does not publish a web page;
Sentinel reaches it through the private container network. The first build
downloads and compiles robot dependencies, so it can take several minutes.

The local `.env` file is passed into the container at startup, so keep the
Baidu and LLM credentials there and do not add them to the Dockerfile. Useful
PowerShell commands are:

```powershell
docker compose ps
docker compose logs -f clawbody
docker compose down
```

### Preview Local Changes

Use the preview override while changing Python source. It mounts the local
`src/` directory into the same `clawbody-reachy` service, so it neither creates
a second container nor publishes another port.

```powershell
# Recreate the single service with local source mounted
docker compose -f docker-compose.yml -f docker-compose.preview.yml up -d

# After changing Python files, restart the same service without rebuilding
docker compose -f docker-compose.yml -f docker-compose.preview.yml restart clawbody

# Return to the image-only service
docker compose -f docker-compose.yml -f docker-compose.preview.yml down
docker compose up -d
```

After the preview is approved, update the normal service once:

```powershell
docker compose up -d --build
```

### Identity and Personality Layers

`robot_identity/AGENTS.md` is the shared first-layer foundation: safety boundaries,
truthfulness, concise speech, and Reachy body/action rules. It must not contain a
fixed student-facing pet name or pretend that the physical robot is XiaoXin.

Per-student personality comes from Sentinel's saved `PetAiProfile` (tone, response
style, initiative, identity constraints, and knowledge scope). Sentinel composes
that profile on the server and injects it into the next Reachy session; browsers do
not send or override the runtime identity. XiaoXin is a separate second-layer demo
advisor. It is invoked only for deterministic negative-emotion triggers, produces a
professional support summary, and never writes a real warning, work order, or
consultation record. The pet AI then rephrases that summary using the active
`PetAiProfile` before Baidu TTS speaks it.

When using Docker Compose, `robot_identity/` is mounted read-only inside the
container. Shared-rule edits are loaded before the next LLM answer. Student-level
personality changes should be made in Sentinel and take effect on the next device
session. Do not use the repository-root `AGENTS.md`; that file contains contributor
instructions.

### CLI Options

| Option | Description |
|--------|-------------|
| `--usb` | Use USB connection for Reachy Mini Lite |
| `--gradio` | Launch web UI at http://localhost:7860 |
| `--debug` | Enable debug logging |
| `--no-camera` | Disable camera |
| `--no-face-tracking` | Disable face tracking |
| `--local-vision` | Enable local vision (SmolVLM2) |

## 🧪 Testing

We provide several test scripts for debugging:

```bash
# Test Baidu ASR/TTS
python test_baidu_asr_tts.py

# Test complete voice pipeline (ASR → LLM → TTS)
python test_voice_pipeline.py

# Test MiniMax API key
python test_minimax_key.py

# Test robot connection
python test_robot_connection.py

# Simple hello world
python hello.py
```

## 🛠️ Robot Capabilities

| Capability | Description |
|------------|-------------|
| **Face Tracking** | Automatically tracks and looks at people |
| **Look** | Move head to look in directions |
| **See** | Capture images through camera |
| **Dance** | Perform dance animations |
| **Emotions** | Express emotions through movement |
| **Speak** | Voice output via Baidu TTS |
| **Listen** | Hear via microphone + Baidu ASR |

## 📄 License

Apache 2.0 License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- [Pollen Robotics](https://www.pollen-robotics.com/) - Reachy Mini robot and SDK
- [Alibaba Cloud Model Studio](https://www.alibabacloud.com/en/product/model-studio) - DashScope/Qwen LLM API
- [Baidu Smart Cloud](https://cloud.baidu.com/) - ASR/TTS API
- [OpenClaw](https://github.com/openclaw/openclaw) - AI assistant framework
