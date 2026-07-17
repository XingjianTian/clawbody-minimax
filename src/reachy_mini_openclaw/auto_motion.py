"""Local lightweight motion cues for voice conversation."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MOTION_SEQUENCES: dict[str, list[str]] = {
    "happy": ["up", "front"],
    "curious": ["right", "left", "front"],
    "confused": ["left", "right", "front"],
    "thinking": ["up", "left", "front"],
    "nod": ["down", "front"],
}


def choose_auto_motion(text: str) -> str:
    """Pick a small expressive motion from assistant text."""
    normalized = text.lower()

    if any(token in normalized for token in ("不确定", "不知道", "不太确定", "抱歉", "听不清", "没听清", "confused")):
        return "confused"

    if any(token in normalized for token in ("？", "?", "怎么", "什么", "为什么", "吗", "呢", "curious")):
        return "curious"

    if any(token in normalized for token in ("开心", "太好了", "很好", "当然", "可以", "happy", "great", "nice")):
        return "happy"

    if any(token in normalized for token in ("想想", "让我看看", "稍等", "thinking")):
        return "thinking"

    return "nod"


def trigger_auto_motion(deps: Any, text: str) -> str | None:
    """Queue a short local motion without involving the LLM tool loop."""
    motion = choose_auto_motion(text)
    sequence = MOTION_SEQUENCES.get(motion)
    if not sequence:
        return None

    try:
        from reachy_mini_openclaw.moves import HeadLookMove

        for direction in sequence:
            _, current_ant = deps.robot.get_current_joint_positions()
            current_head = deps.robot.get_current_head_pose()
            deps.movement_manager.queue_move(
                HeadLookMove(
                    direction=direction,
                    start_pose=current_head,
                    start_antennas=tuple(current_ant),
                    duration=0.35,
                )
            )
        logger.info("Auto motion: %s", motion)
        return motion
    except Exception as exc:
        logger.debug("Auto motion failed: %s", exc)
        return None
