"""Baidu Smart Cloud ASR/TTS client.

Provides Chinese/English speech recognition and synthesis via Baidu API.
Uses OAuth2 client_credentials flow for access token management.
"""

import io
import json
import base64
import asyncio
import logging
import time
from typing import Optional

import httpx
import numpy as np
from numpy.typing import NDArray

from reachy_mini_openclaw.config import config

logger = logging.getLogger(__name__)

# Baidu API endpoints
BAIDU_AUTH_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_ASR_URL = "https://vop.baidu.com/server_api"
BAIDU_TTS_URL = "https://tsn.baidu.com/text2audio"

# Token cache
_token_cache: Optional[tuple[str, float]] = None


class BaiduVoiceClient:
    """Client for Baidu ASR and TTS APIs."""

    def __init__(self) -> None:
        """Initialize with config credentials."""
        self.api_key = config.BAIDU_API_KEY
        self.secret_key = config.BAIDU_SECRET_KEY
        self.app_id = config.BAIDU_APP_ID
        self.http = httpx.AsyncClient(timeout=30.0)

    async def _get_access_token(self) -> str:
        """Fetch or reuse cached access token."""
        global _token_cache
        now = time.time()

        if _token_cache is not None:
            token, expiry = _token_cache
            if now < expiry - 60:  # Refresh 60s before expiry
                return token

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }
        response = await self.http.post(BAIDU_AUTH_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if "access_token" not in data:
            raise RuntimeError(f"Baidu auth failed: {data}")

        token = data["access_token"]
        expires_in = data.get("expires_in", 2592000)  # Default 30 days
        _token_cache = (token, now + expires_in)
        logger.debug("Baidu access token refreshed")
        return token

    async def asr_transcribe(
        self,
        audio: NDArray[np.int16],
        sample_rate: int = 16000,
    ) -> Optional[str]:
        """Transcribe audio to text using Baidu ASR.

        Args:
            audio: int16 PCM audio data
            sample_rate: Audio sample rate (must be 16000 for best results)

        Returns:
            Transcribed text or None if failed
        """
        token = await self._get_access_token()

        # Baidu ASR requires specific format
        if sample_rate != 16000:
            from scipy.signal import resample
            num_samples = int(len(audio) * 16000 / sample_rate)
            audio_float = audio.astype(np.float32)
            resampled: np.ndarray = resample(audio_float, num_samples)
            audio = resampled.astype(np.int16)

        # Encode audio as base64
        audio_bytes = audio.tobytes()
        speech_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        payload = {
            "format": "pcm",
            "rate": 16000,
            "channel": 1,
            "cuid": self.app_id or "reachy_mini_clawbody",
            "token": token,
            "speech": speech_base64,
            "len": len(audio_bytes),
        }

        headers = {"Content-Type": "application/json"}
        response = await self.http.post(BAIDU_ASR_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        err_no = data.get("err_no", -1)
        if err_no != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error("Baidu ASR error %d: %s", err_no, err_msg)
            return None

        result = data.get("result", [])
        if result and len(result) > 0:
            text = result[0]
            logger.info("Baidu ASR: %s", text)
            return text

        logger.debug("Baidu ASR: no speech detected")
        return None

    async def tts_synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to speech using Baidu TTS.

        Args:
            text: Text to synthesize (max 1024 bytes UTF-8)

        Returns:
            MP3 audio bytes or None if failed
        """
        token = await self._get_access_token()

        # Truncate if too long (Baidu limit: 1024 bytes)
        text_bytes = text.encode("utf-8")
        if len(text_bytes) > 1024:
            # Truncate to ~1000 bytes to be safe
            text = text_bytes[:1000].decode("utf-8", errors="ignore")
            logger.warning("TTS text truncated to 1000 bytes")

        params = {
            "tex": text,
            "tok": token,
            "cuid": self.app_id or "reachy_mini_clawbody",
            "ctp": 1,
            "lan": "zh" if "zh" in config.BAIDU_ASR_LANGUAGE else "en",
            "spd": config.BAIDU_TTS_SPD,
            "pit": config.BAIDU_TTS_PIT,
            "vol": config.BAIDU_TTS_VOL,
            "per": config.BAIDU_TTS_PER,
            "aue": 3,  # MP3 format
        }

        response = await self.http.post(BAIDU_TTS_URL, data=params)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            # Error response
            data = response.json()
            err_msg = data.get("err_msg", "Unknown TTS error")
            err_no = data.get("err_no", -1)
            logger.error("Baidu TTS error %d: %s", err_no, err_msg)
            return None

        # Success: binary audio data (MP3)
        logger.info("Baidu TTS: %d bytes MP3", len(response.content))
        return response.content

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http.aclose()
