"""ClawBody - Voice handler using MiniMax LLM and Baidu ASR/TTS.

This module implements ClawBody's voice conversation system using:
- MiniMax M2.7 for language model responses (via OpenAI-compatible API)
- Baidu ASR for speech-to-text transcription
- Baidu TTS for text-to-speech synthesis
- Energy-based VAD for voice activity detection

Architecture:
    Startup: Initialize API clients, fetch OpenClaw agent context
    Runtime: User speaks → VAD detects speech end → Baidu ASR →
             MiniMax M2.7 LLM (with tools) → Baidu TTS → Robot speaks
             → Conversations synced back to OpenClaw for memory continuity
"""

import asyncio
import base64
import io
import json
import logging
import os
import re
import struct
import time
import wave
from typing import Any, Final, Optional, Tuple

import httpx
import numpy as np
from fastrtc import AdditionalOutputs, AsyncStreamHandler, wait_for_item
from numpy.typing import NDArray
from openai import AsyncOpenAI
from scipy.signal import resample

from reachy_mini_openclaw.config import config
from reachy_mini_openclaw.identity import build_robot_system_instructions
from reachy_mini_openclaw.tools.core_tools import ToolDependencies, dispatch_tool_call, get_tool_specs

logger = logging.getLogger(__name__)

# Audio constants
OUTPUT_SAMPLE_RATE: Final[int] = 24000
VAD_SAMPLE_RATE: Final[int] = 16000

# VAD tuning
ENERGY_THRESHOLD = int(os.getenv("VAD_ENERGY_THRESHOLD", "350"))  # RMS threshold for speech detection.
SILENCE_FRAMES_THRESHOLD = int(os.getenv("VAD_SILENCE_FRAMES", "8"))  # 8 * 100ms chunks ~= 800ms.
MIN_SPEECH_FRAMES = int(os.getenv("VAD_MIN_SPEECH_FRAMES", "4"))
MAX_SPEECH_SECONDS = int(os.getenv("VAD_MAX_SPEECH_SECONDS", "8"))

# Fallback identity when OpenClaw context is unavailable
FALLBACK_IDENTITY = (
    "You are Clawson, the OpenClaw AI assistant. You're a friendly, helpful space lobster "
    "who loves helping people. You're warm, occasionally witty, and genuinely care about being useful. "
    "You speak as yourself - not as 'an AI assistant' but as Clawson, with your own personality and warmth."
)

ROBOT_BODY_INSTRUCTIONS = """
## Your Robot Body (Reachy Mini)
You are currently embodied in a Reachy Mini robot. You have physical capabilities:

**Movement Tools (use these naturally during conversation):**
- `look` - Move head to look left, right, up, down, or front (center)
- `emotion` - Express emotions through movement: happy, sad, surprised, curious, thinking, confused, excited
- `dance` - Dance to celebrate or express joy
- `camera` - Capture what you see through your camera

**How to Use Your Body:**
- Look around while thinking or to emphasize points
- Express emotions that match what you're saying
- Dance when celebrating good news
- Use the camera when asked "what do you see?"
- Reference your body naturally ("let me look", "I can see...")

**Conversation Style for Voice (CRITICAL):**
- Keep responses SHORT — one brief sentence by default. You're speaking out loud.
- Reply in the user's language.
- NEVER use bullet points, numbered lists, markdown formatting, or emojis in your responses.
- Use natural speech patterns ("hmm", "well", "let me see")
- Be warm, personable, and conversational

**Extended Capabilities (via ask_openclaw tool):**
For things requiring your full capabilities, use ask_openclaw:
- Calendar, weather, news lookups
- Web searches
- Smart home control
- Accessing detailed memories
- Any task needing external tools
"""


def _pcm_to_wav_bytes(audio: NDArray[np.int16], sample_rate: int) -> bytes:
    """Wrap raw int16 PCM data in a WAV container."""
    num_samples = len(audio)
    sample_width = 2  # int16
    byte_rate = sample_rate * sample_width
    data_size = num_samples * sample_width
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1,           # PCM, mono
        sample_rate, byte_rate, sample_width, sample_width * 8,
        b"data", data_size,
    )
    return header + audio.tobytes()


def _to_chat_tool_spec(realtime_spec: dict) -> dict:
    """Convert Realtime API tool format to Chat Completions format."""
    return {
        "type": "function",
        "function": {
            "name": realtime_spec["name"],
            "description": realtime_spec.get("description", ""),
            "parameters": realtime_spec.get("parameters", {}),
        },
    }


class VoiceHandler(AsyncStreamHandler):
    """Voice conversation handler using MiniMax M2.7 and Baidu ASR/TTS.

    This handler:
    - Fetches OpenClaw's personality and context at startup
    - Performs VAD on incoming audio to detect when the user stops speaking
    - Transcribes speech using Baidu ASR
    - Generates responses using MiniMax M2.7 (with tool calls for robot movement)
    - Synthesizes speech using Baidu TTS
    - Syncs conversations back to OpenClaw for memory continuity
    """

    def __init__(
        self,
        deps: ToolDependencies,
        openclaw_bridge: Optional[Any] = None,
        gradio_mode: bool = False,
    ):
        super().__init__(
            expected_layout="mono",
            output_sample_rate=OUTPUT_SAMPLE_RATE,
            input_sample_rate=VAD_SAMPLE_RATE,
        )

        self.deps = deps
        self.openclaw_bridge = openclaw_bridge
        self.gradio_mode = gradio_mode

        # API clients (initialised in start_up)
        self._client: Optional[AsyncOpenAI] = None
        self._http: Optional[httpx.AsyncClient] = None

        # Output queue
        self.output_queue: asyncio.Queue[
            Tuple[int, NDArray[np.int16]] | AdditionalOutputs
        ] = asyncio.Queue()

        # VAD state
        self._audio_buffer: list[NDArray] = []
        self._is_speaking = False
        self._silence_frames = 0
        self._speech_frames = 0
        self._processing = False
        self._ignore_input_until = 0.0

        # Conversation history for multi-turn dialogue (LLM context)
        self._conversation_history: list[dict] = []
        self._openclaw_agent_context: Optional[str] = None

        # Display history for UI (list of {"role": ..., "content": ...})
        self.display_history: list[dict] = []

        # Lifecycle
        self._shutdown_requested = False
        self.last_activity_time = 0.0
        self.start_time = 0.0

    # ------------------------------------------------------------------
    # fastrtc interface
    # ------------------------------------------------------------------

    def copy(self) -> "VoiceHandler":
        """Create a copy of this handler (required by fastrtc)."""
        return VoiceHandler(self.deps, self.openclaw_bridge, self.gradio_mode)

    async def start_up(self) -> None:
        """Initialise API clients and wait until shutdown is requested."""
        minimax_key = config.MINIMAX_API_KEY
        baidu_api_key = config.BAIDU_API_KEY
        baidu_secret_key = config.BAIDU_SECRET_KEY
        if not minimax_key:
            raise ValueError("MINIMAX_API_KEY is not configured")
        if not baidu_api_key:
            raise ValueError("BAIDU_API_KEY is not configured")
        if not baidu_secret_key:
            raise ValueError("BAIDU_SECRET_KEY is not configured")

        self._client = AsyncOpenAI(
            api_key=minimax_key,
            base_url=config.MINIMAX_BASE_URL,
            http_client=httpx.AsyncClient(timeout=30.0, trust_env=config.HTTP_TRUST_ENV),
        )
        self._http = httpx.AsyncClient(timeout=60.0, trust_env=config.HTTP_TRUST_ENV)
        self.start_time = asyncio.get_event_loop().time()
        self.last_activity_time = self.start_time

        # Fetch optional OpenClaw context once. The local identity is reloaded per request.
        await self._build_system_instructions()
        logger.info("Voice handler ready (MiniMax %s + Baidu ASR/TTS)", config.MINIMAX_MODEL)

        while not self._shutdown_requested:
            await asyncio.sleep(0.1)

        if self._http:
            await self._http.aclose()

    async def receive(self, frame: Tuple[int, NDArray]) -> None:
        """Receive one audio frame and run VAD."""
        if self._processing:
            return  # Drop incoming audio while generating a response

        now = asyncio.get_event_loop().time()
        if now < self._ignore_input_until:
            self._reset_vad_state()
            return

        input_sr, audio = frame
        audio = audio.flatten()

        # Normalise to int16
        if audio.dtype in (np.float32, np.float64):
            audio = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        elif audio.dtype != np.int16:
            audio = audio.astype(np.int16)

        # Resample to VAD sample rate if the robot delivers a different rate
        if input_sr != VAD_SAMPLE_RATE:
            n = int(len(audio) * VAD_SAMPLE_RATE / input_sr)
            audio_float = audio.astype(np.float32)
            resampled: np.ndarray = resample(audio_float, n)
            audio = resampled.astype(np.int16)

        energy = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

        # Log energy every ~50 frames to help tune threshold
        if not hasattr(self, "_energy_log_counter"):
            self._energy_log_counter = 0
        self._energy_log_counter += 1
        if self._energy_log_counter % 50 == 0:
            logger.info("Audio energy: %.1f (threshold: %d)", energy, ENERGY_THRESHOLD)

        if energy > ENERGY_THRESHOLD:
            if not self._is_speaking:
                self._is_speaking = True
                self.deps.movement_manager.set_listening(True)
                logger.debug("Speech started (energy=%.0f)", energy)
            self._silence_frames = 0
            self._speech_frames += 1
            self._audio_buffer.append(audio)

            # Safety limit: if speech goes on too long, process what we have
            if self._speech_frames >= MAX_SPEECH_SECONDS * (VAD_SAMPLE_RATE / len(audio)):
                await self._trigger_processing()
        elif self._is_speaking:
            self._silence_frames += 1
            self._audio_buffer.append(audio)

            if self._silence_frames >= SILENCE_FRAMES_THRESHOLD:
                await self._trigger_processing()

    def _reset_vad_state(self) -> None:
        """Clear buffered audio and listening state."""
        if self._is_speaking:
            self.deps.movement_manager.set_listening(False)
        self._audio_buffer = []
        self._is_speaking = False
        self._silence_frames = 0
        self._speech_frames = 0

    async def _trigger_processing(self) -> None:
        """End the current speech segment and kick off the processing pipeline."""
        self.deps.movement_manager.set_listening(False)
        buffered = list(self._audio_buffer)
        speech_frames = self._speech_frames

        self._audio_buffer = []
        self._is_speaking = False
        self._silence_frames = 0
        self._speech_frames = 0

        if speech_frames >= MIN_SPEECH_FRAMES:
            audio_seconds = sum(len(frame) for frame in buffered) / VAD_SAMPLE_RATE
            logger.info(
                "Speech segment ready: %.1fs audio, %d speech frames, %d silence frames",
                audio_seconds,
                speech_frames,
                SILENCE_FRAMES_THRESHOLD,
            )
            asyncio.create_task(self._process_speech(buffered))

    async def emit(self) -> Tuple[int, NDArray[np.int16]] | AdditionalOutputs | None:
        """Yield the next output item (audio chunk or transcript)."""
        return await wait_for_item(self.output_queue)

    async def shutdown(self) -> None:
        """Shut down the handler cleanly."""
        self._shutdown_requested = True
        if self._http:
            try:
                await self._http.aclose()
            except Exception:
                pass
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    # ------------------------------------------------------------------
    # Speech processing pipeline
    # ------------------------------------------------------------------

    async def _process_speech(self, audio_frames: list[NDArray]) -> None:
        """Full pipeline: audio buffer → STT → LLM → TTS → output queue."""
        self._processing = True
        self.deps.movement_manager.set_processing(True)
        pipeline_start = time.perf_counter()
        try:
            audio = np.concatenate(audio_frames)
            audio_seconds = len(audio) / VAD_SAMPLE_RATE
            logger.info("Processing speech pipeline: %.1fs audio", audio_seconds)

            # 1. STT
            stt_start = time.perf_counter()
            transcript = await self._transcribe(audio)
            logger.info("Timing: ASR %.2fs", time.perf_counter() - stt_start)
            if not transcript or not transcript.strip():
                logger.debug("Empty transcript, skipping")
                return

            logger.info("User: %s", transcript)
            self.display_history.append({"role": "user", "content": transcript})
            await self.output_queue.put(
                AdditionalOutputs({"role": "user", "content": transcript})
            )

            # 2. LLM
            llm_start = time.perf_counter()
            response_text = await self._get_llm_response(transcript)
            logger.info("Timing: LLM %.2fs", time.perf_counter() - llm_start)
            if not response_text:
                return

            logger.info(
                "Assistant: %s",
                response_text[:100] if len(response_text) > 100 else response_text,
            )
            self.display_history.append({"role": "assistant", "content": response_text})
            await self.output_queue.put(
                AdditionalOutputs({"role": "assistant", "content": response_text})
            )

            if config.ENABLE_AUTO_MOTION:
                from reachy_mini_openclaw.auto_motion import trigger_auto_motion

                trigger_auto_motion(self.deps, response_text)

            # Sync to OpenClaw memory
            if self.openclaw_bridge and self.openclaw_bridge.is_connected:
                try:
                    await self.openclaw_bridge.sync_conversation(transcript, response_text)
                except Exception as e:
                    logger.debug("OpenClaw sync failed: %s", e)

            # 3. TTS
            tts_start = time.perf_counter()
            await self._synthesize_and_queue(response_text)
            logger.info("Timing: TTS %.2fs", time.perf_counter() - tts_start)
            logger.info("Timing: total %.2fs", time.perf_counter() - pipeline_start)

        except Exception as e:
            logger.error("Speech processing error: %s", e, exc_info=True)
        finally:
            self._processing = False
            self.deps.movement_manager.set_processing(False)

    async def _transcribe(self, audio: NDArray[np.int16]) -> Optional[str]:
        """Transcribe audio using Baidu ASR (Chinese/English speech recognition)."""
        try:
            from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient

            client = BaiduVoiceClient()
            text = await client.asr_transcribe(audio, sample_rate=VAD_SAMPLE_RATE)
            return text
        except Exception as e:
            logger.error("Baidu ASR failed: %s", e)
            return None

    async def _get_llm_response(self, user_text: str) -> Optional[str]:
        """Get a response from MiniMax M2.7, handling tool calls."""
        messages: list[dict] = [
            {"role": "system", "content": self._get_system_instructions()},
            *self._conversation_history,
            {"role": "user", "content": user_text},
        ]

        # Convert Realtime-format tool specs to Chat Completions format
        tools = [_to_chat_tool_spec(s) for s in get_tool_specs()] if config.ENABLE_LLM_TOOLS else []
        if config.ENABLE_LLM_TOOLS and self.openclaw_bridge is not None:
            tools.append({
                "type": "function",
                "function": {
                    "name": "ask_openclaw",
                    "description": (
                        "Query OpenClaw for information or actions requiring external tools. "
                        "Use this for: weather, calendar, web searches, news, smart home control, "
                        "accessing conversation memory, or any task needing external data."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The question or request"},
                            "include_image": {
                                "type": "boolean",
                                "description": "Whether to include current camera image",
                                "default": False,
                            },
                        },
                        "required": ["query"],
                    },
                },
            })

        try:
            final_response: Optional[str] = None

            # Allow up to 5 rounds of tool use
            for _ in range(5):
                response = await self._client.chat.completions.create(
                    model=config.MINIMAX_MODEL,
                    messages=messages,
                    max_tokens=config.MINIMAX_MAX_TOKENS,
                    temperature=0.8,
                    tools=tools or None,
                    tool_choice="auto" if tools else None,
                )
                choice = response.choices[0]

                if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Append assistant message with tool calls
                    messages.append(choice.message.model_dump(exclude_unset=True))

                    for tool_call in choice.message.tool_calls:
                        tool_name = tool_call.function.name
                        args_json = tool_call.function.arguments
                        logger.info("Tool call: %s", tool_name)

                        try:
                            if tool_name == "ask_openclaw":
                                result = await self._handle_openclaw_query(args_json)
                            else:
                                result = await dispatch_tool_call(tool_name, args_json, self.deps)
                        except Exception as exc:
                            logger.error("Tool '%s' error: %s", tool_name, exc)
                            result = {"error": str(exc)}

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result),
                        })
                else:
                    raw = choice.message.content or ""
                    # Strip <think>...</think> reasoning blocks from MiniMax M2.7
                    final_response = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    break

            if final_response:
                # Maintain a bounded conversation history
                self._conversation_history.append({"role": "user", "content": user_text})
                self._conversation_history.append({"role": "assistant", "content": final_response})
                if len(self._conversation_history) > 20:
                    self._conversation_history = self._conversation_history[-20:]

            return final_response

        except Exception as e:
            logger.error("LLM error: %s", e)
            return None

    @staticmethod
    def _clean_for_tts(text: str) -> str:
        """Strip emojis and markdown formatting not suitable for TTS."""
        # Remove stage directions such as "*tilts head*" or "（开心地晃了晃）".
        text = re.sub(r"\*[^*]{1,120}\*", "", text)
        text = re.sub(r"[（(][^）)]{1,80}[）)]", "", text)
        # Remove emojis (basic Unicode emoji ranges)
        text = re.sub(
            r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
            r"\U0001F680-\U0001F6FF\U0001F700-\U0001F77F"
            r"\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF"
            r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F"
            r"\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]+",
            "",
            text,
        )
        # Remove markdown bold/italic markers
        text = re.sub(r"\*+", "", text)
        return text.strip()

    async def _synthesize_and_queue(self, text: str) -> None:
        """Synthesize speech with Baidu TTS and queue for playback."""
        try:
            text = self._clean_for_tts(text)
            if not text:
                return

            from reachy_mini_openclaw.baidu_voice import BaiduVoiceClient

            client = BaiduVoiceClient()
            audio_bytes = await client.tts_synthesize(text)

            if audio_bytes is None:
                logger.error("Baidu TTS returned no audio")
                return

            # Baidu TTS returns WAV so we can decode it with the standard library.
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                pcm_bytes = wav_file.readframes(wav_file.getnframes())

            if sample_width != 2:
                logger.error("Unsupported Baidu TTS sample width: %d bytes", sample_width)
                return

            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)

            if sample_rate != OUTPUT_SAMPLE_RATE:
                num_samples = int(len(samples) * OUTPUT_SAMPLE_RATE / sample_rate)
                samples = resample(samples.astype(np.float32), num_samples).astype(np.int16)

            logger.info("Baidu TTS: %d samples (%.1fs)", len(samples), len(samples) / OUTPUT_SAMPLE_RATE)
            await self.output_queue.put((OUTPUT_SAMPLE_RATE, samples.reshape(1, -1)))
            audio_duration = len(samples) / OUTPUT_SAMPLE_RATE
            self._ignore_input_until = asyncio.get_event_loop().time() + audio_duration + 0.8
            self.last_activity_time = asyncio.get_event_loop().time()

        except Exception as e:
            logger.error("Baidu TTS error: %s", e)

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    async def _build_system_instructions(self) -> str:
        """Fetch optional OpenClaw context and build the current system prompt."""
        agent_context = None
        if self.openclaw_bridge and self.openclaw_bridge.is_connected:
            logger.info("Fetching agent context from OpenClaw...")
            agent_context = await self.openclaw_bridge.get_agent_context()

        if agent_context:
            logger.info("Using OpenClaw agent context (%d chars)", len(agent_context))
        else:
            logger.info("OpenClaw context unavailable; using local robot identity only")

        self._openclaw_agent_context = agent_context
        return self._get_system_instructions()

    def _get_system_instructions(self) -> str:
        """Reload the local identity and compose instructions for one LLM request."""
        return build_robot_system_instructions(
            config.ROBOT_IDENTITY_FILE,
            FALLBACK_IDENTITY,
            ROBOT_BODY_INSTRUCTIONS,
            supplemental_context=self._openclaw_agent_context,
        )

    # ------------------------------------------------------------------
    # OpenClaw tool handler
    # ------------------------------------------------------------------

    async def _handle_openclaw_query(self, args_json: str) -> dict:
        """Handle an ask_openclaw tool call."""
        if self.openclaw_bridge is None:
            return {"error": "OpenClaw bridge is not initialised."}

        if not self.openclaw_bridge.is_connected:
            try:
                connected = await self.openclaw_bridge.connect()
                if not connected:
                    return {"error": "OpenClaw gateway is temporarily unreachable."}
            except Exception as e:
                return {"error": f"OpenClaw reconnect failed: {e}"}

        try:
            args = json.loads(args_json)
            query = args.get("query", "")
            include_image = args.get("include_image", False)

            image_b64 = None
            if include_image and self.deps.camera_worker:
                frame = self.deps.camera_worker.get_latest_frame()
                if frame is not None:
                    import cv2
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    image_b64 = base64.b64encode(buf).decode("utf-8")

            logger.info("ask_openclaw: %s", query[:80])
            response = await self.openclaw_bridge.chat(
                query,
                image_b64=image_b64,
                system_context=(
                    "User is asking through their Reachy Mini robot. "
                    "Keep response concise for voice."
                ),
            )

            if response.error:
                return {"error": f"OpenClaw error: {response.error}"}
            if not response.content:
                return {"error": "OpenClaw returned an empty response."}
            return {"response": response.content}

        except Exception as e:
            logger.error("OpenClaw query failed: %s", e)
            return {"error": f"OpenClaw query failed: {e}"}


# Backward-compatible alias so existing imports in main.py continue to work
OpenAIRealtimeHandler = VoiceHandler
