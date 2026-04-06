---
name: clawbody
description: Give your OpenClaw AI agent a physical robot body with Reachy Mini. Works with physical robot OR simulator! Voice conversation via MiniMax M2.7 LLM and ElevenLabs TTS, vision, and expressive movements.
---

# ClawBody - Robot Body for OpenClaw

Give your OpenClaw agent (Clawson) a physical robot body with Reachy Mini.

## Overview

ClawBody embodies your OpenClaw AI assistant in a Reachy Mini robot, enabling it to:

- **Hear**: Listen to voice commands via the robot's microphone
- **See**: View the world through the robot's camera
- **Speak**: Respond with natural voice via ElevenLabs TTS through the robot's speaker
- **Move**: Express emotions through expressive head movements and dances

Using a pipeline architecture with MiniMax M2.7 for language intelligence, ElevenLabs for natural voice synthesis, and OpenClaw for memory and tools, the robot holds natural multi-turn conversations.

## Architecture

```
You speak → Reachy Mini 🎤
                ↓
         Energy-based VAD
      (detects speech end)
                ↓
     MiniMax STT (whisper-1)
    (speech-to-text transcript)
                ↓
        MiniMax M2.7 LLM
    (response + tool calls 🦞)
                ↓
      ElevenLabs TTS (PCM)
    (natural voice synthesis)
                ↓
   Robot speaks & moves 🤖💃
```

## Requirements

### Option A: Physical Robot
- [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) robot (Wireless or Lite)

### Option B: Simulator (No Hardware Required!)
- Any computer with Python 3.11+
- Install: `pip install "reachy-mini[mujoco]"`
- [Simulator Setup Guide](https://huggingface.co/docs/reachy_mini/platforms/simulation/get_started)

### Software (Both Options)
- Python 3.11+
- MiniMax API key (for LLM and STT)
- ElevenLabs API key (for TTS)
- OpenClaw gateway running on your network

## Installation

```bash
# Clone from GitHub
git clone https://github.com/tomrikert/clawbody
cd clawbody
pip install -e .
```

Or from HuggingFace:
```bash
git clone https://huggingface.co/spaces/tomrikert/clawbody
```

## Configuration

Create a `.env` file:

```bash
# MiniMax (LLM + STT)
MINIMAX_API_KEY=sk-api-your-minimax-key
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_BASE_URL=https://api.minimaxi.chat/v1/

# ElevenLabs (TTS)
ELEVENLABS_API_KEY=sk_your-elevenlabs-key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# OpenClaw gateway
OPENCLAW_GATEWAY_URL=http://your-host-ip:18789
OPENCLAW_TOKEN=your-gateway-token
```

## Usage

### With Simulator (No Robot Required)

```bash
# Terminal 1: Start simulator
reachy-mini-daemon --sim

# Terminal 2: Run ClawBody
clawbody --gradio
```

### With Physical Robot

```bash
# Run ClawBody
clawbody

# With debug logging
clawbody --debug

# With Gradio web UI
clawbody --gradio
```

## Features

### Voice Conversation Pipeline
Energy-based VAD detects when you stop speaking, then routes audio through MiniMax STT → MiniMax M2.7 LLM → ElevenLabs TTS for natural multi-turn dialogue.

### ElevenLabs Voice
High-quality, expressive voice synthesis using ElevenLabs. Choose any voice from the [ElevenLabs Voice Library](https://elevenlabs.io/voice-library) by setting `ELEVENLABS_VOICE_ID` in your `.env`.

### OpenClaw Intelligence
Full Clawson capabilities — tools, memory, personality — through the OpenClaw gateway.

### Expressive Movements
- Audio-driven head wobble while speaking
- Emotion expressions (happy, curious, thinking, excited)
- Dance animations
- Natural head tracking

### Vision
Ask Clawson to describe what it sees through the robot's camera, powered by MiniMax M2.7's vision capabilities.

## Links

- [GitHub Repository](https://github.com/tomrikert/clawbody)
- [HuggingFace Space](https://huggingface.co/spaces/tomrikert/clawbody)
- [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini)
- [OpenClaw Documentation](https://docs.openclaw.ai)

## Author

Tom (tomrikert)

## License

Apache 2.0
