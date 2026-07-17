# 心宠 Console Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing Gradio interface to match `DESIGN.md` while preserving every conversation, identity, configuration, and Docker behavior.

**Architecture:** Keep the Python callbacks and Gradio runtime in `gradio_app.py`. Replace the current broad CSS overrides with a stable-ID component layer, and use semantic HTML for static status/configuration content. Validate through the source-mounted Docker preview on port 7861 before rebuilding the production container.

**Tech Stack:** Python 3.11+, Gradio 5.50, HTML, scoped CSS, Lucide-derived icon masks, Docker Compose preview.

## Global Constraints

- Preserve the four existing tabs and all callback signatures.
- Use Chinese UI copy, fixed 15–34px typography, 8px control radius, and a 1440px maximum content width.
- Use `#F5F5F7`, `#FCFCFD`, `#ECECF0`, `#1D1D1F`, and no more than 8% signal amber.
- Do not globally style Gradio `.wrap`, `.block`, or `button *` internals.
- Motion must communicate state and provide a `prefers-reduced-motion` fallback.
- Do not rebuild the production Docker image until the user approves the port 7861 preview.

---

### Task 1: Stable UI Structure

**Files:**
- Modify: `src/reachy_mini_openclaw/gradio_app.py`

**Interfaces:**
- Consumes: Existing `start_conversation`, `stop_conversation`, `apply_profile`, `save_profile`, and `get_transcript` callbacks.
- Produces: Stable element IDs for the header, controls, status, transcript, identity fields, settings list, and about flow.

- [ ] Replace the marketing-style header with a compact device bar.
- [ ] Rebuild the conversation page as an 8/4 task grid with a semantic configuration list.
- [ ] Rebuild the identity page with visible labels, placeholders, inline status outputs, and stable IDs.
- [ ] Render settings and about content as semantic HTML without exposing API keys.
- [ ] Keep all callback inputs and outputs connected to their original functions.

### Task 2: Scoped Design System

**Files:**
- Modify: `src/reachy_mini_openclaw/gradio_app.py`

**Interfaces:**
- Consumes: Stable IDs from Task 1 and tokens from `DESIGN.md`.
- Produces: `UI_CSS` implementing the approved layout and component states.

- [ ] Replace the existing mint/coral CSS with the silver-lab token set.
- [ ] Add primary, secondary, field, status, transcript, panel, and navigation states.
- [ ] Add Lucide-derived Play, Square, Save, Search, and status icons without character glyph substitutes.
- [ ] Add structural breakpoints at 960px and 640px.
- [ ] Add visible focus states and reduced-motion behavior.

### Task 3: Preview Verification

**Files:**
- Verify: `src/reachy_mini_openclaw/gradio_app.py`

**Interfaces:**
- Consumes: Source-mounted `docker-compose.preview.yml` service.
- Produces: A visually reviewed preview at `http://localhost:7861`.

- [ ] Run `python -m py_compile src/reachy_mini_openclaw/gradio_app.py` and expect exit code 0.
- [ ] Restart with `docker compose -f docker-compose.preview.yml restart clawbody-preview`.
- [ ] Confirm `docker compose -f docker-compose.preview.yml ps` reports the preview healthy.
- [ ] Inspect all four tabs at 1920×1080 and 390×844.
- [ ] Confirm no right black edge, invisible input, clipped text, or decorative infinite motion remains.
