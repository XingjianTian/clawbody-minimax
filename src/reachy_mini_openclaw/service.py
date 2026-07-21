"""Headless service boundary for Sentinel and Reachy Mini integration."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from reachy_mini_openclaw.two_layer_demo import EventStore, ProfessionalResponder, TwoLayerDemoOrchestrator


class TranscriptStore:
    """Bounded, cursor-based in-memory transcript."""

    def __init__(self, limit: int = 100):
        self._items: deque[dict[str, Any]] = deque(maxlen=limit)
        self._cursor = 0

    def clear(self) -> None:
        self._items.clear()
        self._cursor = 0

    def append(self, role: str, content: str) -> dict[str, Any]:
        self._cursor += 1
        item = {
            "id": self._cursor,
            "role": role,
            "content": content,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._items.append(item)
        return item

    def after(self, cursor: int) -> dict[str, Any]:
        return {"cursor": self._cursor, "items": [item for item in self._items if item["id"] > cursor]}


class ClawBodyService:
    """Owns the single hardware session exposed to Sentinel."""

    def __init__(
        self,
        core_factory: Callable[[], Any],
        text_responder: Callable[[str, str], Awaitable[str]] | None = None,
        professional_responder: ProfessionalResponder | None = None,
    ):
        self._core_factory = core_factory
        self._text_responder = text_responder
        self.events = EventStore(limit=100)
        self._orchestrator = TwoLayerDemoOrchestrator(
            professional_responder or self._fallback_professional_response,
            self.events,
        )
        self.core: Any | None = None
        self._task: asyncio.Task | None = None
        self._core_loop: asyncio.AbstractEventLoop | None = None
        self._core_task: asyncio.Task | None = None
        self._student_id: str | None = None
        self._state = "idle"
        self._error: str | None = None
        self._stop_requested = False
        self._seen_display_items = 0
        self.transcript = TranscriptStore(limit=100)

    @property
    def running(self) -> bool:
        return self._state == "running" and self._task is not None and not self._task.done()

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, student_id: str, identity: str) -> dict[str, Any]:
        if self.active:
            raise RuntimeError("session already running")
        self.transcript.clear()
        self.events.clear()
        self._seen_display_items = 0
        self._student_id = student_id
        self._state = "starting"
        self._error = None
        self._stop_requested = False
        self._task = asyncio.create_task(self._prepare_and_run(identity), name="clawbody-hardware-session")
        await asyncio.sleep(0)
        return self.status()

    async def _prepare_and_run(self, identity: str) -> None:
        try:
            core = await asyncio.to_thread(self._core_factory)
            if self._stop_requested:
                await asyncio.to_thread(core.stop)
                return
            self.core = core
            self.core.handler.runtime_identity = identity.strip() or None
            self.core.handler.response_orchestrator = self._orchestrator.respond
            self.core.handler.runtime_event_sink = self._append_runtime_event
            await asyncio.to_thread(self._run_core_in_thread)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._state = "error"
            self._error = str(exc)
        finally:
            if self._state not in {"error", "stopping"}:
                self._state = "idle"

    def _run_core_in_thread(self) -> None:
        loop = asyncio.new_event_loop()
        self._core_loop = loop
        asyncio.set_event_loop(loop)
        try:
            if self._stop_requested:
                self.core.stop()
                return
            self._core_task = loop.create_task(self._run_core())
            loop.run_until_complete(self._core_task)
        except asyncio.CancelledError:
            pass
        finally:
            self._core_task = None
            self._core_loop = None
            loop.close()

    async def _run_core(self) -> None:
        try:
            self._state = "running"
            await self.core.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._state = "error"
            self._error = str(exc)
        finally:
            if self._state != "error":
                self._state = "idle"

    async def stop(self) -> dict[str, Any]:
        self._stop_requested = True
        self._state = "stopping"
        if self.core is not None:
            for _ in range(50):
                if self._core_loop is not None or self._task is None or self._task.done():
                    break
                await asyncio.sleep(0.01)
            if self._core_loop is not None and self._core_loop.is_running():
                def stop_core() -> None:
                    self.core.stop()
                    if self._core_task is not None:
                        self._core_task.cancel()

                self._core_loop.call_soon_threadsafe(stop_core)
            else:
                await asyncio.to_thread(self.core.stop)
        if self._task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=5)
            except TimeoutError:
                self._task.cancel()
        self._task = None
        self.core = None
        self._core_loop = None
        self._core_task = None
        self._student_id = None
        self._state = "idle"
        self._stop_requested = False
        self.transcript.clear()
        self.events.clear()
        return self.status()

    def _sync_transcript(self) -> None:
        if self.core is None:
            return
        history = list(getattr(self.core.handler, "display_history", []))
        for item in history[self._seen_display_items :]:
            self.transcript.append(item.get("role", "assistant"), item.get("content", ""))
        self._seen_display_items = len(history)

    def transcript_after(self, cursor: int) -> dict[str, Any]:
        self._sync_transcript()
        return self.transcript.after(cursor)

    def events_after(self, cursor: int) -> dict[str, Any]:
        return self.events.after(cursor)

    def _append_runtime_event(self, kind: str, status: str, title: str, summary: str) -> None:
        self.events.append(kind, status, title, summary)

    @staticmethod
    async def _fallback_professional_response(_message: str) -> str:
        return TwoLayerDemoOrchestrator.FALLBACK_ADVICE

    def status(self) -> dict[str, Any]:
        if self._task is not None and self._task.done() and self._state == "running":
            self._state = "idle"
        return {
            "running": self.running,
            "student_id": self._student_id,
            "state": self._state,
            "error": self._error,
        }

    async def respond_text(self, message: str, identity: str) -> str:
        if self.running and self.core is not None:
            self.core.handler.runtime_identity = identity.strip() or None
            response = await self._orchestrator.respond(message, self.core.handler._get_llm_response)
            if not response:
                raise RuntimeError("model returned an empty response")
            return response
        if self._text_responder is None:
            raise RuntimeError("text responder is not configured")
        async def pet_responder(pet_message: str) -> str:
            return await self._text_responder(pet_message, identity)

        response = await self._orchestrator.respond(message, pet_responder)
        if not response:
            raise RuntimeError("model returned an empty response")
        return response
