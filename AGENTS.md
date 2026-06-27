# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python package for ClawBody, a Reachy Mini voice and movement integration using MiniMax, Baidu ASR/TTS, and optional OpenClaw tooling. Core code lives in `src/reachy_mini_openclaw/`: `main.py` contains the CLI/app entry point, `config.py` loads environment settings, `baidu_voice.py` handles Baidu speech APIs, `moves.py` defines robot motions, and `gradio_app.py` serves the web UI. Supporting modules are grouped under `audio/`, `vision/`, `tools/`, and `prompts/`. Top-level `test_*.py` files are integration/debug scripts. Static landing/demo assets are `index.html` and `style.css`. OpenClaw skill metadata lives in `openclaw-skill/`.

## Build, Test, and Development Commands

Create a local environment with Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,mediapipe_vision]"
```

Run the app with `clawbody --gradio` for the browser UI, or `clawbody --usb --gradio` for a USB Reachy Mini Lite. Use `python hello.py` for a minimal robot check. Run focused diagnostics with `python test_minimax_key.py`, `python test_baidu_asr_tts.py`, `python test_voice_pipeline.py`, and `python test_robot_connection.py`. Run project checks with `pytest`, `ruff check .`, `ruff format .`, and `mypy src`.

## Coding Style & Naming Conventions

Follow PEP 8 with type hints for public interfaces. Ruff is configured for Python 3.11, 120-character lines, import sorting, pyupgrade rules, and naming checks. Use four-space indentation, `snake_case` for functions/modules, `PascalCase` for classes, and uppercase names for constants and environment variables. Keep hardware/API side effects isolated behind small functions or classes so simulator, USB, and network paths remain testable.

## Testing Guidelines

Prefer `pytest` tests for pure logic and small integration boundaries. Name new tests `test_<feature>.py` and test functions `test_<behavior>()`. For scripts that require credentials, robot hardware, audio devices, or the Reachy simulator, document required `.env` keys and skip gracefully when prerequisites are unavailable.

## Commit & Pull Request Guidelines

Recent history uses concise imperative summaries, for example `Replace ElevenLabs with Baidu ASR/TTS...`. Keep commits focused and describe the user-visible change. Pull requests should include a clear summary, setup or configuration changes, tests run, linked issues when relevant, and screenshots for Gradio or static UI changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` and keep real MiniMax, Baidu, and OpenClaw credentials out of git. Avoid committing generated audio, local robot logs, virtual environments, or machine-specific simulator files.
