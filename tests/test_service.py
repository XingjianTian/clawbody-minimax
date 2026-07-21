import asyncio
import time

from reachy_mini_openclaw.service import ClawBodyService, TranscriptStore


class FakeCore:
    def __init__(self):
        self.handler = type("Handler", (), {"display_history": [], "runtime_identity": None})()
        self.stopped = False

    async def run(self):
        await asyncio.sleep(60)

    def stop(self):
        self.stopped = True


async def wait_for_core(service: ClawBodyService):
    for _ in range(50):
        if service.core is not None:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("background core did not start")


def test_service_rejects_a_second_session():
    async def scenario():
        service = ClawBodyService(core_factory=lambda: FakeCore())
        await service.start("stu-zhangyu", "温暖的心宠")
        await wait_for_core(service)
        assert service.core.handler.runtime_identity == "温暖的心宠"

        try:
            await service.start("stu-zhangyu", "温暖的心宠")
            raise AssertionError("second session should be rejected")
        except RuntimeError as exc:
            assert "already running" in str(exc)

        await service.stop()

    asyncio.run(scenario())


def test_transcript_store_limits_history_and_supports_cursor():
    store = TranscriptStore(limit=3)
    for index in range(5):
        store.append("user", f"message-{index}")

    result = store.after(2)
    assert [item["content"] for item in result["items"]] == ["message-2", "message-3", "message-4"]
    assert result["cursor"] == 5


def test_transcript_risk_is_inherited_by_pet_reply_and_escalates_session_status():
    service = ClawBodyService(core_factory=lambda: FakeCore())
    service.core = FakeCore()
    service.core.handler.display_history = [
        {"role": "user", "content": "我今天心情不好，不想吃饭了"},
        {"role": "assistant", "content": "我们先慢慢喝一点水，好吗？"},
        {"role": "user", "content": "我不想活了，想结束这一切"},
        {"role": "assistant", "content": "我会陪着你，我们马上联系可信赖的大人。"},
    ]

    items = service.transcript_after(0)["items"]

    assert [item["risk_level"] for item in items] == ["MEDIUM", "MEDIUM", "HIGH", "HIGH"]
    assert service.status()["risk_level"] == "HIGH"


def test_hardware_session_installs_two_layer_orchestration_and_exposes_events():
    async def professional(_message: str) -> str:
        return "专业建议"

    async def scenario():
        service = ClawBodyService(core_factory=lambda: FakeCore(), professional_responder=professional)
        await service.start("stu-test", "测试心宠个性")
        await wait_for_core(service)

        assert callable(service.core.handler.response_orchestrator)
        assert callable(service.core.handler.runtime_event_sink)
        service.core.handler.runtime_event_sink("tts", "complete", "语音合成", "百度 TTS 已就绪")
        assert service.events_after(0)["items"][0]["kind"] == "tts"
        await service.stop()
        assert service.events_after(0) == {"cursor": 0, "items": []}

    asyncio.run(scenario())


def test_start_returns_while_slow_hardware_connection_runs_in_background():
    def slow_core_factory():
        time.sleep(0.2)
        return FakeCore()

    async def scenario():
        service = ClawBodyService(core_factory=slow_core_factory)
        started_at = time.perf_counter()
        status = await service.start("stu-test", "测试心宠个性")
        elapsed = time.perf_counter() - started_at

        try:
            assert elapsed < 0.1
            assert status["state"] == "starting"
        finally:
            await asyncio.sleep(0.25)
            await service.stop()

    asyncio.run(scenario())
