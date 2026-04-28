#!/usr/bin/env python3
"""Test the complete voice pipeline with Baidu ASR/TTS + MiniMax LLM.

Usage:
    conda activate reachy_mini_env
    cd /path/to/clawbody-minimax
    python test_voice_pipeline.py

This test runs the full voice conversation loop:
1. Record audio from microphone
2. Baidu ASR transcribe to text
3. MiniMax LLM generate response
4. Baidu TTS synthesize response to speech
5. Play back the audio
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def record_audio(duration: int = 5) -> tuple[int, "np.ndarray"]:
    """Record audio from microphone."""
    import sounddevice as sd
    import numpy as np

    SAMPLE_RATE = 16000
    logger.info("Recording %d seconds... Please speak!", duration)

    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
    )
    sd.wait()

    logger.info("Recording complete")
    return SAMPLE_RATE, recording.flatten()


async def test_asr(audio: "np.ndarray", sample_rate: int) -> str:
    """Test Baidu ASR."""
    from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient

    client = BaiduVoiceClient()
    try:
        text = await client.asr_transcribe(audio, sample_rate=sample_rate)
        if text:
            logger.info("ASR Result: %s", text)
            return text
        else:
            logger.error("ASR returned no text")
            return ""
    finally:
        await client.close()


async def test_llm(user_text: str) -> str:
    """Test MiniMax LLM response generation."""
    from openai import AsyncOpenAI
    from reachy_mini_openclaw.config import config

    logger.info("Sending to MiniMax LLM: %s", user_text)

    client = AsyncOpenAI(
        api_key=config.MINIMAX_API_KEY,
        base_url=config.MINIMAX_BASE_URL,
    )

    try:
        response = await client.chat.completions.create(
            model=config.MINIMAX_MODEL,
            messages=[
                {"role": "system", "content": "You are a friendly AI assistant named Clawson. Keep responses short (1-2 sentences)."},
                {"role": "user", "content": user_text},
            ],
            max_tokens=200,
            temperature=0.8,
        )

        text = response.choices[0].message.content or ""
        # Strip <think> tags
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        logger.info("LLM Response: %s", text)
        return text

    except Exception as e:
        logger.error("LLM failed: %s", e)
        return "Sorry, I couldn't process that."


async def test_tts(text: str):
    """Test Baidu TTS and playback."""
    from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient
    import numpy as np
    from scipy.signal import resample

    client = BaiduVoiceClient()
    try:
        logger.info("Synthesizing TTS for: %s", text[:50])
        audio_bytes = await client.tts_synthesize(text)

        if audio_bytes is None:
            logger.error("TTS failed")
            return

        # Decode MP3 to PCM using pydub
        from pydub import AudioSegment
        audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))

        # Convert to desired format: 24kHz, mono, int16
        target_rate = 24000
        audio_segment = audio_segment.set_frame_rate(target_rate).set_channels(1)
        samples = np.array(audio_segment.get_array_of_samples(), dtype=np.int16)

        logger.info("TTS audio: %d samples (%.1fs)", len(samples), len(samples) / target_rate)

        # Play back
        try:
            import sounddevice as sd
            logger.info("Playing response...")
            sd.play(samples, samplerate=target_rate)
            sd.wait()
            logger.info("Playback complete")
        except Exception as e:
            logger.warning("Playback failed: %s", e)

    finally:
        await client.close()


async def main():
    """Run the complete voice pipeline test."""
    logger.info("=" * 60)
    logger.info("Voice Pipeline Test (Baidu ASR/TTS + MiniMax LLM)")
    logger.info("=" * 60)
    logger.info("")
    logger.info("This test will:")
    logger.info("1. Record your voice (5 seconds)")
    logger.info("2. Transcribe with Baidu ASR")
    logger.info("3. Generate response with MiniMax LLM")
    logger.info("4. Synthesize with Baidu TTS")
    logger.info("5. Play back the response")
    logger.info("")

    # Step 1: Record
    sample_rate, audio = await record_audio(duration=5)

    # Step 2: ASR
    user_text = await test_asr(audio, sample_rate)
    if not user_text:
        logger.error("ASR failed, stopping test")
        return False

    # Step 3: LLM
    response_text = await test_llm(user_text)
    if not response_text:
        logger.error("LLM failed, stopping test")
        return False

    # Step 4 & 5: TTS + Playback
    await test_tts(response_text)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Voice pipeline test complete!")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    import io
    import numpy as np
    asyncio.run(main())
