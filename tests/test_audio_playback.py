import asyncio

import numpy as np

from reachy_mini_openclaw.main import ClawBodyCore


class FakeMedia:
    def __init__(self):
        self.pushed = []

    def get_output_channels(self):
        return 2

    def push_audio_sample(self, data):
        self.pushed.append(data.copy())


def test_realtime_playback_expands_mono_tts_to_reachy_output_channels():
    async def scenario():
        core = object.__new__(ClawBodyCore)
        core.robot = type("Robot", (), {"media": FakeMedia()})()
        core._should_stop = lambda: False
        mono = np.linspace(-0.5, 0.5, 40, dtype=np.float32)

        await core._push_audio_realtime(mono, sample_rate=1000)

        pushed = np.concatenate(core.robot.media.pushed, axis=0)
        assert pushed.shape == (40, 2)
        np.testing.assert_allclose(pushed[:, 0], mono)
        np.testing.assert_allclose(pushed[:, 1], mono)

    asyncio.run(scenario())


def test_realtime_playback_buffers_chunks_before_waiting_for_completion(monkeypatch):
    sleeps = []

    async def capture_sleep(duration):
        sleeps.append(duration)

    monkeypatch.setattr("reachy_mini_openclaw.main.asyncio.sleep", capture_sleep)

    async def scenario():
        core = object.__new__(ClawBodyCore)
        core.robot = type("Robot", (), {"media": FakeMedia()})()
        core._should_stop = lambda: False

        await core._push_audio_realtime(np.zeros(40, dtype=np.float32), sample_rate=1000)

        assert len(core.robot.media.pushed) == 2
        assert sleeps == [0.04]

    asyncio.run(scenario())
