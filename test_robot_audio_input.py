import asyncio
import wave
from unittest.mock import AsyncMock, patch

import numpy as np

from reachy_mini_openclaw.main import ClawBodyCore


class FakeMedia:
    def __init__(self) -> None:
        stereo = np.zeros((1600, 2), dtype=np.float32)
        stereo[:2] = [
            [0.25, 0.75],
            [-0.5, 0.5],
        ]
        self.samples = [
            stereo,
        ]

    def get_input_audio_samplerate(self) -> int:
        return 16000

    def get_audio_sample(self):
        return self.samples.pop(0) if self.samples else None


class FakeHandler:
    def __init__(self) -> None:
        self.frames = []

    async def receive(self, frame) -> None:
        self.frames.append(frame)


class FakePlaybackMedia:
    def __init__(self) -> None:
        self.chunks = []

    def push_audio_sample(self, chunk) -> None:
        self.chunks.append(chunk.copy())


class FakeDaemonPlaybackMedia:
    def __init__(self) -> None:
        self.played = []

    def play_sound(self, path: str) -> None:
        with wave.open(path, "rb") as wav_file:
            self.played.append(
                (
                    wav_file.getframerate(),
                    wav_file.getnchannels(),
                    wav_file.getsampwidth(),
                    wav_file.getnframes(),
                )
            )


class SplitFakeMedia:
    def __init__(self) -> None:
        self.samples = [
            np.full((800, 2), 0.25, dtype=np.float32),
            np.full((800, 2), 0.75, dtype=np.float32),
        ]

    def get_input_audio_samplerate(self) -> int:
        return 16000

    def get_audio_sample(self):
        return self.samples.pop(0) if self.samples else None


def test_network_record_loop_reads_reachy_webrtc_audio() -> None:
    core = ClawBodyCore.__new__(ClawBodyCore)
    core.robot = type("FakeRobot", (), {"media": FakeMedia()})()
    core.handler = FakeHandler()
    core._use_robot_audio_input = True
    core._should_stop = lambda: bool(core.handler.frames)

    asyncio.run(core.record_loop())

    sample_rate, mono = core.handler.frames[0]
    assert sample_rate == 16000
    assert mono.shape == (1600, 1)
    np.testing.assert_allclose(mono[:2], np.array([[0.5], [0.0]], dtype=np.float32))


def test_network_record_loop_combines_small_webrtc_packets() -> None:
    core = ClawBodyCore.__new__(ClawBodyCore)
    core.robot = type("FakeRobot", (), {"media": SplitFakeMedia()})()
    core.handler = FakeHandler()
    core._use_robot_audio_input = True
    core._should_stop = lambda: bool(core.handler.frames)

    asyncio.run(core.record_loop())

    sample_rate, mono = core.handler.frames[0]
    assert sample_rate == 16000
    assert mono.shape == (1600, 1)
    np.testing.assert_allclose(mono[:800], 0.25)
    np.testing.assert_allclose(mono[800:], 0.75)


def test_network_playback_streams_tts_in_realtime_chunks() -> None:
    core = ClawBodyCore.__new__(ClawBodyCore)
    media = FakePlaybackMedia()
    core.robot = type("FakeRobot", (), {"media": media})()
    core._should_stop = lambda: False
    audio = np.arange(1000, dtype=np.float32)

    with patch("reachy_mini_openclaw.main.asyncio.sleep", new=AsyncMock()) as sleep:
        asyncio.run(core._push_audio_realtime(audio, 16000))

    assert [len(chunk) for chunk in media.chunks] == [320, 320, 320, 40]
    np.testing.assert_array_equal(np.concatenate(media.chunks), audio)
    assert sleep.await_count == 4


def test_network_playback_uses_daemon_sound_file() -> None:
    core = ClawBodyCore.__new__(ClawBodyCore)
    media = FakeDaemonPlaybackMedia()
    core.robot = type("FakeRobot", (), {"media": media})()
    audio = np.linspace(-0.5, 0.5, 1600, dtype=np.float32)

    with patch("reachy_mini_openclaw.main.asyncio.sleep", new=AsyncMock()):
        asyncio.run(core._play_audio_via_daemon(audio, 16000))

    assert media.played == [(16000, 1, 2, 1600)]
