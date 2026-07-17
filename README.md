# 🤖 ClawBody

**Give your AI agent a physical robot body with voice conversation!**

ClawBody combines MiniMax LLM intelligence with Reachy Mini's expressive robot body, using Baidu ASR/TTS for Chinese/English voice conversation. Your AI assistant can now see, hear, speak, and move in the physical world.

> 🦞 This is a fork of [tomrikert/clawbody](https://github.com/tomrikert/clawbody) with MiniMax LLM + Baidu ASR/TTS replacing OpenAI Realtime API.

## ✨ Features

- **🎤 Real-time Voice Conversation**: Baidu ASR for speech recognition + Baidu TTS for natural voice synthesis
- **🧠 MiniMax M2.7 LLM**: Powerful language model with tool calling support
- **👁️ Face Tracking**: Real-time face detection and eye contact (MediaPipe/YOLO)
- **💃 Expressive Movements**: Natural head movements, emotions, dances, and audio-driven wobble
- **🖥️ Simulator Support**: Works with or without physical hardware (MuJoCo simulation)
- **🔧 OpenClaw Integration**: Extended AI capabilities via OpenClaw Gateway

## 🏗️ Architecture

```
Your Voice → Baidu ASR → MiniMax LLM (+ Tools) → Baidu TTS → Robot Speaks
                ↓                                        ↓
         Face Tracking                            Head Wobble
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

### With Physical Robot (USB)

```bash
# Terminal 1: Start the desktop app (or daemon)
# The app must be running before starting ClawBody

# Terminal 2: Run ClawBody with USB connection
clawbody --usb

# Or with Gradio web UI
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
The container starts the Gradio conversation service and connects to the host
daemon through `host.docker.internal:8000`. Open <http://localhost:7860> in a
browser to talk with Reachy Mini. The first build downloads and compiles robot
dependencies, so it can take several minutes.

The local `.env` file is passed into the container at startup, so keep the
Baidu and LLM credentials there and do not add them to the Dockerfile. Useful
PowerShell commands are:

```powershell
docker compose ps
docker compose logs -f clawbody
docker compose down
```

### Customize Robot Identity and Tone

Edit `robot_identity/AGENTS.md` to change the robot's name, personality,
speaking style, rules, and manually maintained memories. The default tone is
friendly, natural, clear, and concise, similar to GPT's conversational style.

When using Docker Compose, this directory is mounted read-only inside the
container. Saved edits are loaded before the next LLM answer, so changing the
identity does not require rebuilding or restarting the container. Do not use
the repository-root `AGENTS.md`; that file contains contributor instructions.

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
- [MiniMax](https://www.minimax.chat/) - LLM API
- [Baidu Smart Cloud](https://cloud.baidu.com/) - ASR/TTS API
- [OpenClaw](https://github.com/openclaw/openclaw) - AI assistant framework
