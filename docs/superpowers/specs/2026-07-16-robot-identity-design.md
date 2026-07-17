# Robot Identity Design

## Goal

Give Reachy Mini a manually maintained identity and memory that influences every LLM response. The existing repository-root `AGENTS.md` remains a contributor guide and is never used as robot personality data.

## Identity File

The robot identity lives at `robot_identity/AGENTS.md`. It contains the robot's name, background, personality, relationship with the user, speaking style, behavioral rules, and manually curated memories. The starter speaking style is GPT-like: friendly, natural, clear, calm, direct, and concise for voice conversation. The application never writes to this file.

## Prompt Assembly

Before every LLM request, the voice handler reads the identity file and combines it with the existing robot-body instructions. Identity instructions take priority over the built-in fallback personality. The current bounded conversation history remains unchanged.

The file path is configurable through `ROBOT_IDENTITY_FILE`, defaulting to `/app/robot_identity/AGENTS.md` in Docker and `robot_identity/AGENTS.md` for local development. Empty, missing, oversized, or unreadable files produce a warning and fall back to the current identity so conversation remains available.

## Docker Integration

Docker Compose mounts `./robot_identity` at `/app/robot_identity` as read-only. Because the file is read for each LLM request, edits on Windows affect the next answer without rebuilding or restarting the container.

## User Experience

A Chinese starter template documents the supported sections without requiring a strict parser. Users edit ordinary Markdown and can verify loading through a concise startup/request log that reports the path and character count without printing private identity content.

## Testing

Tests cover successful loading, fallback behavior, per-request hot reload, and prompt composition. Docker configuration validation confirms the read-only bind mount and environment path.
