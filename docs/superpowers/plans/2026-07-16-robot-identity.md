# Robot Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load a manually maintained robot identity Markdown file before every LLM response, with Docker read-only mounting and safe fallback behavior.

**Architecture:** A focused identity loader resolves and validates the configured file. The voice handler composes that identity with robot-body instructions for every request, so bind-mounted edits are hot-reloaded without restarting.

**Tech Stack:** Python 3.11, pytest, Docker Compose, OpenAI-compatible Chat Completions.

## Global Constraints

- Never read the repository-root contributor `AGENTS.md` as robot identity.
- Never write to the robot identity file from application code.
- Default local path is `robot_identity/AGENTS.md`; Docker path is `/app/robot_identity/AGENTS.md`.
- Missing, blank, unreadable, or larger-than-64-KiB identity files fall back safely.
- Docker mounts `./robot_identity` read-only.

---

### Task 1: Identity Loader

**Files:**
- Create: `src/reachy_mini_openclaw/identity.py`
- Create: `test_robot_identity.py`

**Interfaces:**
- Produces: `load_robot_identity(path: str | Path, fallback: str) -> str`

- [x] Write tests proving a valid UTF-8 Markdown file loads, missing/blank/oversized files return fallback, and a changed file is read on the next call.
- [x] Run `python -m pytest -q test_robot_identity.py` and verify failure because the module is absent.
- [x] Implement path resolution, a 65,536-byte limit, UTF-8 reading, whitespace trimming, and warning-based fallback.
- [x] Run `python -m pytest -q test_robot_identity.py` and expect all tests to pass.

### Task 2: Per-Request Prompt Composition

**Files:**
- Modify: `src/reachy_mini_openclaw/config.py`
- Modify: `src/reachy_mini_openclaw/openai_realtime.py`
- Modify: `test_robot_identity.py`

**Interfaces:**
- Consumes: `load_robot_identity(path, fallback)`
- Produces: `VoiceHandler._get_system_instructions() -> str`

- [x] Add a failing test that edits the identity file between two calls and verifies the second system prompt contains the new identity.
- [x] Run the focused test and verify failure because prompts are currently cached at startup.
- [x] Add `ROBOT_IDENTITY_FILE` configuration and compose identity plus `ROBOT_BODY_INSTRUCTIONS` before every `_get_llm_response()` request.
- [x] Preserve OpenClaw context only as supplemental context; the local identity remains the explicit robot identity.
- [x] Run the identity and existing audio tests and expect all to pass.

### Task 3: Docker Mount and Editable Template

**Files:**
- Create: `robot_identity/AGENTS.md`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Docker provides `/app/robot_identity/AGENTS.md` through `ROBOT_IDENTITY_FILE`.

- [x] Add a Chinese Markdown template containing identity, relationship, personality, a friendly GPT-like speaking style, behavior, and manual memories.
- [x] Add the read-only bind mount and environment path to Compose.
- [x] Document that edits apply to the next answer and do not require a rebuild or restart.
- [x] Run `docker compose config` and verify the mount has `read_only: true`.

### Task 4: Container Verification

**Files:**
- No additional production files.

- [x] Build and recreate the container.
- [x] Start conversation and verify the identity path is logged without printing file contents.
- [x] Edit a harmless identity phrase on the host and verify a container-side loader call sees it immediately.
- [x] Restore the intended template phrase.
- [x] Run `pytest`, compile checks, focused Ruff checks, `git diff --check`, and Docker health verification.
