"""Deterministic two-layer pet/professional-agent demo orchestration."""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DetectionResult:
    triggered: bool
    matches: tuple[str, ...]
    level: str


MEDIUM_RISK_TERMS = (
    "心情不好",
    "不想吃饭",
    "没胃口",
    "很难受",
    "很难过",
    "很焦虑",
    "睡不着",
    "不想说话",
    "不想见人",
)

HIGH_RISK_TERMS = (
    "不想活",
    "结束这一切",
    "自杀",
    "伤害自己",
    "活着没意思",
    "死了算了",
)


def detect_negative_emotion(text: str) -> DetectionResult:
    high_matches = tuple(term for term in HIGH_RISK_TERMS if term in text)
    if high_matches:
        return DetectionResult(triggered=True, matches=high_matches, level="HIGH")
    medium_matches = tuple(term for term in MEDIUM_RISK_TERMS if term in text)
    return DetectionResult(triggered=bool(medium_matches), matches=medium_matches, level="MEDIUM" if medium_matches else "LOW")


class EventStore:
    """Bounded cursor-based store for auditable demo-stage summaries."""

    def __init__(self, limit: int = 100):
        self._items: deque[dict[str, Any]] = deque(maxlen=limit)
        self._cursor = 0

    def clear(self) -> None:
        self._items.clear()
        self._cursor = 0

    def append(self, kind: str, status: str, title: str, summary: str, risk_level: str = "LOW") -> dict[str, Any]:
        self._cursor += 1
        item = {
            "id": self._cursor,
            "kind": kind,
            "status": status,
            "title": title,
            "summary": summary,
            "risk_level": risk_level,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._items.append(item)
        return item

    def after(self, cursor: int) -> dict[str, Any]:
        return {"cursor": self._cursor, "items": [item for item in self._items if item["id"] > cursor]}


PetResponder = Callable[[str], Awaitable[str | None]]
ProfessionalResponder = Callable[[str], Awaitable[str]]


class TwoLayerDemoOrchestrator:
    """Routes negative messages through a simulated professional layer before pet relay."""

    FALLBACK_ADVICE = "先承接学生当前的低落感受，温和了解持续时间与基本饮食情况，并鼓励从喝水或少量进食开始。"

    def __init__(self, professional_responder: ProfessionalResponder, events: EventStore):
        self._professional_responder = professional_responder
        self.events = events

    async def respond(self, message: str, pet_responder: PetResponder) -> str | None:
        detection = detect_negative_emotion(message)
        if not detection.triggered:
            return await pet_responder(message)

        evidence = "、".join(detection.matches)
        self.events.append("emotion", "complete", f"检测为{'高' if detection.level == 'HIGH' else '中'}风险", f"触发表达：{evidence}", detection.level)
        self.events.append("handoff", "complete", "转交小芯 AI", "已将学生原话交给演示专业咨询师智能体。", detection.level)

        try:
            advice = (await self._professional_responder(message)).strip() or self.FALLBACK_ADVICE
            professional_status = "complete"
        except Exception:
            advice = self.FALLBACK_ADVICE
            professional_status = "fallback"

        self.events.append("professional", professional_status, "小芯专业建议", advice, detection.level)
        relay_prompt = (
            "学生刚才说：\n"
            f"{message}\n\n"
            "小芯 AI 给心宠的专业建议：\n"
            f"{advice}\n\n"
            "请不要提及后台、系统或专业智能体。请严格按照当前心宠个性，用自然口语把建议转述给学生，控制在三句话以内。"
        )
        response = await pet_responder(relay_prompt)
        if response:
            self.events.append("relay", "complete", "心宠完成转述", response, detection.level)
        else:
            self.events.append("relay", "error", "心宠转述失败", "模型没有返回可播放的心宠回复。", detection.level)
        return response
