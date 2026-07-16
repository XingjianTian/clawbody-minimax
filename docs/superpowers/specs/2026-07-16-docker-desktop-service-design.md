# Docker Desktop Service Design

## Goal

Package the existing ClawBody Gradio conversation service as one Docker container so it can be started from Docker Desktop with a single action.

## Architecture

The container runs the existing `clawbody` entry point with Gradio enabled and publishes port `7860`. Reachy Mini Control remains responsible for the Reachy daemon on the Windows host at port `8000`; the container reaches it through Docker Desktop's `host.docker.internal` hostname. The container does not access USB directly and does not start a second daemon.

## Configuration

The local `.env` file is passed to the container at runtime through Docker Compose. Credentials remain outside the image and are not copied into the build context. Compose supplies `ROBOT_HOST=host.docker.internal`, `ROBOT_PORT=8000`, and disables optional camera/OpenClaw integrations for the current voice conversation workflow.

## User Workflow

1. Start Reachy Mini Control and connect the robot so the host daemon is available.
2. Open the repository as a Compose project in Docker Desktop and click Run.
3. Open `http://localhost:7860` and start the conversation UI.

## Failure Handling

The container exits visibly if required credentials are missing or the host daemon is unavailable. Docker health status checks the Gradio HTTP endpoint. Logs remain available in Docker Desktop for diagnosing configuration, LLM, ASR/TTS, and robot connection errors.

## Validation

Build the image, start the Compose service, verify the health endpoint, and run the existing pure motion test plus Python compilation checks. Hardware conversation testing still requires the powered Reachy Mini and Reachy Mini Control daemon.
