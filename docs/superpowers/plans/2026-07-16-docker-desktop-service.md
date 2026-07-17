# Docker Desktop Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the ClawBody Gradio conversation service as one Docker Compose service that Docker Desktop can start with one click.

**Architecture:** The image installs the Python package and runs `clawbody --gradio` with the existing voice pipeline. Compose publishes port `7860`, injects the host `.env`, and points the container at Reachy Mini Control's host daemon through `host.docker.internal:8000`.

**Tech Stack:** Docker, Docker Compose, Python 3.11, setuptools, Gradio, existing Reachy Mini SDK.

## Global Constraints

- The container does not access Reachy USB directly.
- Reachy Mini Control must provide the host daemon on port `8000`.
- Credentials remain in the local `.env` and are never copied into the image.
- The default container workflow disables camera, face tracking, and OpenClaw gateway integration.

---

### Task 1: Add the Docker build definition

**Files:**
- Create: `C:/Users/txj12/Desktop/PsyTwin/clawbody-minimax/Dockerfile`
- Create: `C:/Users/txj12/Desktop/PsyTwin/clawbody-minimax/.dockerignore`

**Interfaces:**
- Produces an image with the `clawbody` console script available on `PATH`.

- [ ] **Step 1: Add a Python 3.11 slim image and runtime dependencies**

  Use a non-development install with the Reachy Mini SDK pinned to `1.8.0`, matching the working local daemon. Install the Linux audio, GObject, GStreamer, and SDK runtime dependencies explicitly. Build the Reachy-required Rust `webrtcsrc` plugin from `gst-plugins-rs` because Debian does not ship it by default.

  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
  RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libportaudio2 portaudio19-dev ffmpeg git \
      && rm -rf /var/lib/apt/lists/*
  COPY pyproject.toml README.md LICENSE ./
  COPY src ./src
  RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal \
      && . /root/.cargo/env \
      && cargo install cargo-c \
      && git clone --depth 1 --branch 0.14.1 https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git /tmp/gst-plugins-rs \
      && cd /tmp/gst-plugins-rs \
      && cargo cinstall -p gst-plugin-webrtc --prefix=/opt/gst-plugins-rs --release
  RUN pip install --upgrade pip \
      && pip install . \
      && pip install sounddevice \
      && pip install PyGObject==3.46.0 pycairo pulsectl \
      && pip install reachy_mini==1.8.0 --no-deps \
      && pip install aiohttp asgiref libusb_package log-throttling psutil pyserial pyusb questionary reachy-mini-rust-kinematics reachy_mini_motor_controller rustypot toml tornado zeroconf
  EXPOSE 7860
  CMD ["clawbody", "--gradio", "--robot-host", "host.docker.internal", "--robot-port", "8000", "--no-openclaw", "--no-camera", "--no-face-tracking"]
  ```

- [ ] **Step 2: Exclude secrets and local build artifacts**

  `.dockerignore` must include `.env`, `.venv`, `.git`, `__pycache__`, test caches, generated audio, and local logs.

- [ ] **Step 3: Build the image**

  Run `docker build -t clawbody-reachy:local .`.

  Expected: `gst-inspect-1.0 webrtcsrc` succeeds, and the SDK connection test prints `REACHY_CONNECTION_OK`.

### Task 2: Add the Docker Desktop Compose service

**Files:**
- Create: `C:/Users/txj12/Desktop/PsyTwin/clawbody-minimax/docker-compose.yml`

**Interfaces:**
- Consumes: the repository `.env` file.
- Produces: service `clawbody` at `http://localhost:7860`.

- [ ] **Step 1: Define the service, port, environment, and restart policy**

  ```yaml
  services:
    clawbody:
      build: .
      container_name: clawbody-reachy
      env_file:
        - .env
      environment:
        ROBOT_HOST: host.docker.internal
        ROBOT_PORT: "8000"
        ENABLE_CAMERA: "false"
        ENABLE_FACE_TRACKING: "false"
        ENABLE_LLM_TOOLS: "false"
        ENABLE_AUTO_MOTION: "true"
      ports:
        - "7860:7860"
      extra_hosts:
        - "host.docker.internal:host-gateway"
      restart: unless-stopped
  ```

- [ ] **Step 2: Add a Gradio health check**

  Check `http://127.0.0.1:7860` using Python from inside the image, with a 30-second start grace period and 30-second interval.

- [ ] **Step 3: Validate Compose configuration**

  Run `docker compose config`.

  Expected: valid normalized YAML with one `clawbody` service and no secret values printed by the repository files.

### Task 3: Document the Docker Desktop workflow

**Files:**
- Modify: `C:/Users/txj12/Desktop/PsyTwin/clawbody-minimax/README.md`

**Interfaces:**
- Documents the exact Windows workflow for starting Reachy Mini Control, opening the Compose project, starting the service, and opening port `7860`.

- [ ] **Step 1: Add a short Docker Desktop section**

  State that Reachy Mini Control must be connected first, then the repository can be opened in Docker Desktop as a Compose project and started with `Run`.

- [ ] **Step 2: Document common checks**

  Include `docker compose ps`, `docker compose logs -f clawbody`, and `docker compose down`, plus the expected host daemon URL `host.docker.internal:8000`.

### Task 4: Verify the complete package

**Files:**
- Test: `C:/Users/txj12/Desktop/PsyTwin/clawbody-minimax/test_auto_motion.py`

- [ ] **Step 1: Run static checks**

  Run `python -m py_compile src/reachy_mini_openclaw/*.py` and `python test_auto_motion.py`.

  Expected: compilation succeeds and the motion test prints `auto motion tests passed`.

- [ ] **Step 2: Build and start Compose**

  Run `docker compose build` and `docker compose up -d`.

  Expected: `clawbody-reachy` is running and `docker compose ps` reports the service as healthy after startup.

- [ ] **Step 3: Check the browser endpoint and logs**

  Run `Invoke-WebRequest http://localhost:7860` and `docker compose logs --tail 80 clawbody`.

  Expected: HTTP status `200`, Gradio startup output, and no missing-credential or robot-host configuration error.

- [ ] **Step 4: Stop the service after validation if hardware is not being tested**

  Run `docker compose down` only when the user does not want the service left running.
