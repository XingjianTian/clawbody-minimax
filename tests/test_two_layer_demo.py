import asyncio

from reachy_mini_openclaw.two_layer_demo import EventStore, TwoLayerDemoOrchestrator, detect_negative_emotion


def test_negative_emotion_detector_matches_the_demo_sentence():
    neutral = detect_negative_emotion("今天完成了作业，感觉还不错")
    negative = detect_negative_emotion("我今天心情不好，不想吃饭了")

    assert neutral.triggered is False
    assert negative.triggered is True
    assert "心情不好" in negative.matches
    assert "不想吃饭" in negative.matches


def test_negative_message_runs_professional_handoff_before_pet_relay():
    async def scenario():
        events = EventStore(limit=100)

        async def professional(message: str) -> str:
            assert "不想吃饭" in message
            return "先确认持续时间，并温和询问今天是否摄入了水和少量食物。"

        pet_inputs: list[str] = []

        async def pet(message: str) -> str:
            pet_inputs.append(message)
            return "听起来你今天很难受。我们先喝一点水，再看看能不能吃一小口，好吗？"

        orchestrator = TwoLayerDemoOrchestrator(professional, events)
        response = await orchestrator.respond("我今天心情不好，不想吃饭了", pet)

        assert response.startswith("听起来")
        assert "专业建议" in pet_inputs[0]
        result = events.after(0)
        assert [item["kind"] for item in result["items"]] == ["emotion", "handoff", "professional", "relay"]
        assert result["cursor"] == 4

    asyncio.run(scenario())


def test_neutral_message_uses_only_the_pet_agent():
    async def scenario():
        events = EventStore(limit=100)
        professional_calls = 0

        async def professional(_message: str) -> str:
            nonlocal professional_calls
            professional_calls += 1
            return "unused"

        async def pet(message: str) -> str:
            return f"心宠回复：{message}"

        response = await TwoLayerDemoOrchestrator(professional, events).respond("今天心情不错", pet)
        assert response == "心宠回复：今天心情不错"
        assert professional_calls == 0
        assert events.after(0)["items"] == []

    asyncio.run(scenario())


def test_event_store_is_bounded_and_cursor_based():
    store = EventStore(limit=3)
    for index in range(5):
        store.append("emotion", "complete", f"event-{index}", "summary")

    result = store.after(2)
    assert [item["title"] for item in result["items"]] == ["event-2", "event-3", "event-4"]
    assert result["cursor"] == 5
