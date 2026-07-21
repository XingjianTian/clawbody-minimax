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

### Sentinel Internal Service (Recommended)

The supported management UI is PsyTwin Sentinel. Start this project as a private device service; it does not expose a standalone web console:

```bash
clawbody-service
```

Configure `SERVICE_HOST`, `SERVICE_PORT`, and `SERVICE_API_KEY` in `.env`, then set the matching `CLAWBODY_SERVICE_URL` and `CLAWBODY_SERVICE_KEY` in Sentinel. Keep port 7862 on localhost or a private container network.

The authenticated internal API provides:

- `GET /health` and `GET /v1/status` for service and device state.
- `POST /v1/session/start` and `POST /v1/session/stop` for the single Reachy session.
- `GET /v1/transcript?after=<cursor>` for in-memory ASR/final-response updates.
- `GET /v1/events?after=<cursor>` for the structured two-layer collaboration timeline.
- `POST /v1/text/respond` for a text-only rehearsal without microphone capture.

All `/v1/*` requests require `X-Service-Key`. Transcripts and collaboration events are memory-only, bounded to the latest 100 items, and are cleared when the session stops or the service restarts.

Starting a hardware session returns immediately with `state: "starting"`. Reachy connection, camera, audio, and movement initialization continue in a background thread so `/health`, status polling, and the Sentinel UI remain responsive. The state changes to `running` when initialization finishes, or to `error` with a readable message when it fails.

For local Reachy Mini Control playback, ClawBody adapts mono Baidu TTS output to the device's reported output-channel count, queues contiguous timestamped chunks without per-chunk scheduler gaps, and then waits for the full clip duration. This prevents live `appsrc` underruns and truncated playback. No extra setting is required; restart the internal service after updating the code.

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
this file or share it through Git. Start Reachy Mini Control first, connect the
robot, and make sure it provides the Reachy daemon at `localhost:8000` before
running the Docker command.

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

Use the preview service while changing Python source. It mounts
the local `src/` directory into the existing image, so it does not rebuild or
download dependencies. It remains private and does not publish another web port.

```powershell
# Start the local-source preview once
docker compose -f docker-compose.preview.yml up -d

# After changing Python or UI files, restart in a few seconds without rebuilding
docker compose -f docker-compose.preview.yml restart clawbody-preview

# Stop the preview when it is no longer needed
docker compose -f docker-compose.preview.yml down
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
