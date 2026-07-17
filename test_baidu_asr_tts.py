#!/usr/bin/env python3
"""Test Baidu ASR and TTS API integration.

Usage:
    conda activate reachy_mini_env
    cd /path/to/clawbody-minimax
    python test_baidu_asr_tts.py

Tests:
1. Baidu access token retrieval
2. TTS synthesis (text -> MP3 -> playback)
3. ASR transcription (microphone -> text)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def test_token():
    """Test Baidu access token retrieval."""
    logger.info("=" * 50)
    logger.info("Test 1: Baidu Access Token")
    logger.info("=" * 50)

    from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient

    client = BaiduVoiceClient()
    try:
        token = await client._get_access_token()
        logger.info("Token obtained successfully: %s...", token[:20])
        logger.info("Token length: %d", len(token))
        return True
    except Exception as e:
        logger.error("Token test failed: %s", e)
        return False
    finally:
        await client.close()


async def test_tts():
    """Test Baidu TTS synthesis and playback."""
    logger.info("=" * 50)
    logger.info("Test 2: Baidu TTS Synthesis")
    logger.info("=" * 50)

    from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient

    client = BaiduVoiceClient()
    try:
        test_texts = [
            "你好，我是Clawson，你的智能助手。",
            "Hello, I am Clawson, your intelligent assistant.",
        ]

        for text in test_texts:
            logger.info("Synthesizing: %s", text)
            audio_bytes = await client.tts_synthesize(text)

            if audio_bytes is None:
                logger.error("TTS failed for: %s", text)
                continue

            # Save to file for inspection
            output_file = Path(f"test_tts_output_{hash(text) % 10000}.mp3")
            output_file.write_bytes(audio_bytes)
            logger.info("Saved to: %s (%d bytes)", output_file, len(audio_bytes))

            # Try to play back
            try:
                from pydub import AudioSegment
                from pydub.playback import play

                audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                logger.info("Audio duration: %.1fs", len(audio) / 1000)
                logger.info("Playing audio...")
                play(audio)
                logger.info("Playback complete")
            except Exception as e:
                logger.warning("Playback failed (this is OK if no speakers): %s", e)

        return True
    except Exception as e:
        logger.error("TTS test failed: %s", e, exc_info=True)
        return False
    finally:
        await client.close()


async def test_asr():
    """Test Baidu ASR with live microphone input."""
    logger.info("=" * 50)
    logger.info("Test 3: Baidu ASR (Microphone)")
    logger.info("=" * 50)

    from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient
    import sounddevice as sd
    import numpy as np

    client = BaiduVoiceClient()
    try:
        SAMPLE_RATE = 16000
        DURATION = 5  # seconds

        logger.info("Recording %d seconds of audio...", DURATION)
        logger.info("Please speak now!")

        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.int16,
        )
        sd.wait()

        logger.info("Recording complete, transcribing...")
        audio = recording.flatten()
        text = await client.asr_transcribe(audio, sample_rate=SAMPLE_RATE)

        if text:
            logger.info("ASR Result: %s", text)
            return True
        else:
            logger.error("ASR returned no text")
            return False

    except Exception as e:
        logger.error("ASR test failed: %s", e, exc_info=True)
        return False
    finally:
        await client.close()


async def main():
    """Run all Baidu voice tests."""
    logger.info("Starting Baidu ASR/TTS Tests")
    logger.info("Make sure .env file is configured with BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY")
    logger.info("")

    results = []

    # Test 1: Token
    results.append(("Token", await test_token()))
    logger.info("")

    # Test 2: TTS
    results.append(("TTS", await test_tts()))
    logger.info("")

    # Test 3: ASR
    results.append(("ASR", await test_asr()))
    logger.info("")

    # Summary
    logger.info("=" * 50)
    logger.info("Test Results Summary")
    logger.info("=" * 50)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        logger.info("%s: %s", name, status)

    all_passed = all(r[1] for r in results)
    if all_passed:
        logger.info("All tests passed!")
    else:
        logger.error("Some tests failed. Check logs above.")

    return all_passed


if __name__ == "__main__":
    import io
    asyncio.run(main())
