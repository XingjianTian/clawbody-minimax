"""ClawBody - Give your OpenClaw AI agent a physical robot body.

This module provides the main application that connects:
- OpenAI Realtime API for voice I/O (speech recognition + TTS)
- OpenClaw Gateway for AI intelligence (Clawson's brain)
- Reachy Mini robot for physical embodiment

Usage:
    # Console mode (direct audio)
    clawbody

    # With Gradio UI
    clawbody --gradio

    # With debug logging
    clawbody --debug
"""

import os
import sys
import time
import asyncio
import logging
import argparse
import threading
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# Load environment from project root (override=True ensures .env takes precedence)
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env", override=True)

logger = logging.getLogger(__name__)


def _patch_remote_media_signalling_host(host: str) -> None:
    """Make Reachy's WebRTC client use the reachable daemon host.

    The daemon status may leave ``wlan_ip`` empty when it runs over USB. In a
    Docker network client that makes the SDK fall back to the container's own
    localhost, even though the SDK websocket is reachable through the host.
    """
    from reachy_mini.reachy_mini import WSClient

    if getattr(WSClient, "_clawbody_signalling_patch", False):
        return

    original_get_status = WSClient.get_status

    def get_status_with_host(self: Any, *args: Any, **kwargs: Any) -> Any:
        status = original_get_status(self, *args, **kwargs)
        if getattr(status, "wlan_ip", None):
            return status
        return status.model_copy(update={"wlan_ip": host})

    WSClient.get_status = get_status_with_host
    WSClient._clawbody_signalling_patch = True


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application.
    
    Args:
        debug: Enable debug level logging
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    
    # Keep debug useful without flooding the terminal with websocket/audio internals.
    noisy_loggers = (
        "httpcore",
        "httpx",
        "websockets",
        "openai",
        "PIL",
        "multipart",
    )
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="ClawBody - Give your OpenClaw AI agent a physical robot body",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run in console mode
    clawbody

    # Run with Gradio web UI
    clawbody --gradio

    # Connect to specific robot
    clawbody --robot-name my-reachy

    # Use different OpenClaw gateway
    clawbody --gateway-url http://192.168.1.100:18790
        """
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--gradio",
        action="store_true",
        help="Launch Gradio web UI instead of console mode"
    )
    parser.add_argument(
        "--robot-name",
        type=str,
        help="Robot logical name (default: reachy_mini)"
    )
    parser.add_argument(
        "--robot-host",
        type=str,
        default=os.getenv("ROBOT_HOST"),
        help="Robot hostname or IP address (e.g. localhost, 192.168.1.50)"
    )
    parser.add_argument(
        "--robot-port",
        type=int,
        default=int(os.getenv("ROBOT_PORT", "8000")),
        help="Robot daemon port (default: 8000)"
    )
    parser.add_argument(
        "--gateway-url",
        type=str,
        default=os.getenv("OPENCLAW_GATEWAY_URL", "ws://localhost:18789"),
        help="OpenClaw gateway URL (from OPENCLAW_GATEWAY_URL env or default)"
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="Disable camera functionality"
    )
    parser.add_argument(
        "--no-openclaw",
        action="store_true",
        help="Disable OpenClaw integration"
    )
    parser.add_argument(
        "--no-face-tracking",
        action="store_true",
        help="Disable face tracking"
    )
    parser.add_argument(
        "--local-vision",
        action="store_true",
        help="Enable local vision processing with SmolVLM2"
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Custom personality profile to use"
    )
    parser.add_argument(
        "--usb",
        action="store_true",
        help="Use USB connection for Reachy Mini Lite (default constructor)"
    )
    
    return parser.parse_args()


class ClawBodyCore:
    """ClawBody core application controller.
    
    This class orchestrates all components:
    - Reachy Mini robot connection and movement control
    - OpenAI Realtime API for voice I/O
    - OpenClaw gateway bridge for AI intelligence
    - Audio input/output loops
    """
    
    def __init__(
        self,
        gateway_url: str = "ws://localhost:18789",
        robot_name: Optional[str] = None,
        robot_host: Optional[str] = None,
        robot_port: Optional[int] = None,
        enable_camera: bool = True,
        enable_openclaw: bool = True,
        robot: Optional["ReachyMini"] = None,
        external_stop_event: Optional[threading.Event] = None,
        use_usb: bool = False,
    ):
        """Initialize the application.

        Args:
            gateway_url: OpenClaw gateway URL
            robot_name: Optional robot logical name
            robot_host: Robot hostname or IP (overrides ROBOT_HOST env var)
            robot_port: Robot daemon port (overrides ROBOT_PORT env var)
            enable_camera: Whether to enable camera functionality
            enable_openclaw: Whether to enable OpenClaw integration
            robot: Optional pre-initialized robot (for app framework)
            external_stop_event: Optional external stop event
            use_usb: If True, use default ReachyMini() for USB-connected Lite
        """
        from reachy_mini import ReachyMini
        from reachy_mini_openclaw.config import config
        from reachy_mini_openclaw.moves import MovementManager
        from reachy_mini_openclaw.audio.head_wobbler import HeadWobbler
        from reachy_mini_openclaw.openclaw_bridge import OpenClawBridge
        from reachy_mini_openclaw.tools.core_tools import ToolDependencies
        from reachy_mini_openclaw.openai_realtime import OpenAIRealtimeHandler

        self.gateway_url = gateway_url
        self._external_stop_event = external_stop_event
        self._owns_robot = robot is None
        self._use_robot_audio_input = False

        # Validate configuration
        errors = config.validate()
        if errors:
            for error in errors:
                logger.error("Config error: %s", error)
            raise RuntimeError("Configuration errors: " + "; ".join(errors))

        # Connect to robot
        if robot is not None:
            self.robot = robot
            self._use_robot_audio_input = getattr(robot, "connection_mode", None) == "network"
            logger.info("Using provided Reachy Mini instance")
        elif use_usb:
            # USB-connected Reachy Mini Lite (default constructor)
            logger.info("Connecting to Reachy Mini via USB...")
            try:
                self.robot = ReachyMini()
            except Exception as e:
                logger.error("USB connection failed: %s", e)
                raise RuntimeError(
                    f"Robot USB connection failed: {e}. "
                    "Make sure the robot is powered on and USB is connected."
                ) from e
            logger.info("Connected to robot: %s", self.robot.client.get_status())
        else:
            # Network/simulator connection
            host = robot_host or config.ROBOT_HOST
            port = robot_port or config.ROBOT_PORT

            # Choose connection mode based on host
            if host in ("localhost", "127.0.0.1"):
                connection_mode = "localhost_only"
            else:
                connection_mode = "network"

            logger.info(
                "Connecting to Reachy Mini at %s:%d (mode=%s)...",
                host, port, connection_mode,
            )
            robot_kwargs: dict = {
                "host": host,
                "port": port,
                "connection_mode": connection_mode,
            }
            if robot_name:
                robot_kwargs["robot_name"] = robot_name
            if connection_mode == "network":
                _patch_remote_media_signalling_host(host)

            try:
                self.robot = ReachyMini(**robot_kwargs)
            except TimeoutError as e:
                logger.error("Connection timeout: %s", e)
                raise RuntimeError(
                    "Robot connection timed out. Is the robot powered on and reachable? "
                    "For simulation, run: reachy-mini-daemon --sim"
                ) from e
            except Exception as e:
                logger.error("Robot connection failed: %s", e)
                raise RuntimeError(
                    f"Robot connection failed: {e}. "
                    "For simulation, run: reachy-mini-daemon --sim"
                ) from e

            logger.info("Connected to robot: %s", self.robot.client.get_status())
            self._use_robot_audio_input = connection_mode == "network"
        
        # Initialize movement system
        logger.info("Initializing movement system...")
        self.movement_manager = MovementManager(current_robot=self.robot)
        self.head_wobbler = HeadWobbler(
            set_speech_offsets=self.movement_manager.set_speech_offsets
        )
        
        # Initialize OpenClaw bridge
        self.openclaw_bridge = None
        if enable_openclaw:
            logger.info("Initializing OpenClaw bridge...")
            self.openclaw_bridge = OpenClawBridge(
                gateway_url=gateway_url,
                gateway_token=config.OPENCLAW_TOKEN,
            )
        
        # Camera worker for video streaming and frame capture
        self.camera_worker = None
        self.head_tracker = None
        self.vision_manager = None
        
        if enable_camera:
            logger.info("Initializing camera worker...")
            from reachy_mini_openclaw.camera_worker import CameraWorker
            
            # Initialize head tracker for local face tracking
            if config.ENABLE_FACE_TRACKING:
                self.head_tracker = self._initialize_head_tracker(config.HEAD_TRACKER_TYPE)
            
            # Initialize camera worker with head tracker
            self.camera_worker = CameraWorker(
                reachy_mini=self.robot,
                head_tracker=self.head_tracker,
            )
            
            # Enable/disable head tracking based on whether we have a tracker
            self.camera_worker.set_head_tracking_enabled(self.head_tracker is not None)
            
            # Initialize local vision processor if enabled
            if config.ENABLE_LOCAL_VISION:
                self.vision_manager = self._initialize_vision_manager()
        
        # Create tool dependencies
        self.deps = ToolDependencies(
            movement_manager=self.movement_manager,
            head_wobbler=self.head_wobbler,
            robot=self.robot,
            camera_worker=self.camera_worker,
            openclaw_bridge=self.openclaw_bridge,
            vision_manager=self.vision_manager,
        )
        
        # Initialize OpenAI Realtime handler with OpenClaw bridge
        self.handler = OpenAIRealtimeHandler(
            deps=self.deps,
            openclaw_bridge=self.openclaw_bridge,
        )
        
        # State
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        
    def _initialize_vision_manager(self) -> Optional[Any]:
        """Initialize local vision processor (SmolVLM2).
        
        Returns:
            VisionManager instance or None if initialization fails
        """
        if self.camera_worker is None:
            logger.warning("Cannot initialize vision manager without camera worker")
            return None
        
        try:
            from reachy_mini_openclaw.vision.processors import (
                VisionConfig, 
                initialize_vision_manager,
            )
            from reachy_mini_openclaw.config import config
            
            vision_config = VisionConfig(
                model_path=config.LOCAL_VISION_MODEL,
                device_preference=config.VISION_DEVICE,
                hf_home=config.HF_HOME,
            )
            
            logger.info("Initializing local vision processor (SmolVLM2)...")
            vision_manager = initialize_vision_manager(self.camera_worker, vision_config)
            
            if vision_manager is not None:
                logger.info("Local vision processor initialized")
            else:
                logger.warning("Local vision processor failed to initialize")
            
            return vision_manager
            
        except ImportError as e:
            logger.warning(f"Local vision not available: {e}")
            logger.warning("Install with: pip install torch transformers")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize vision manager: {e}")
            return None
    
    def _initialize_head_tracker(self, tracker_type: Optional[str] = None) -> Optional[Any]:
        """Initialize head tracker for local face tracking.
        
        Args:
            tracker_type: Type of tracker ("yolo", "mediapipe", or None for auto)
            
        Returns:
            Initialized head tracker or None if initialization fails
        """
        # Default to YOLO if not specified
        if tracker_type is None:
            tracker_type = "yolo"
        
        if tracker_type == "yolo":
            try:
                from reachy_mini_openclaw.vision.yolo_head_tracker import HeadTracker
                logger.info("Initializing YOLO face tracker...")
                tracker = HeadTracker(device="cpu")  # CPU is fast enough for face detection
                logger.info("YOLO face tracker initialized")
                return tracker
            except ImportError as e:
                logger.warning(f"YOLO tracker not available: {e}")
                logger.warning("Install with: pip install ultralytics supervision")
            except Exception as e:
                logger.error(f"Failed to initialize YOLO tracker: {e}")
        
        elif tracker_type == "mediapipe":
            try:
                from reachy_mini_openclaw.vision.mediapipe_tracker import HeadTracker
                logger.info("Initializing MediaPipe face tracker...")
                tracker = HeadTracker()
                logger.info("MediaPipe face tracker initialized")
                return tracker
            except ImportError as e:
                logger.warning(f"MediaPipe tracker not available: {e}")
            except Exception as e:
                logger.error(f"Failed to initialize MediaPipe tracker: {e}")
        
        logger.warning("No face tracker available - face tracking disabled")
        return None
        
    def _should_stop(self) -> bool:
        """Check if we should stop."""
        if self._stop_event.is_set():
            return True
        if self._external_stop_event is not None and self._external_stop_event.is_set():
            return True
        return False
        
    async def _record_robot_media_loop(self) -> None:
        """Read Reachy's WebRTC microphone and emit 100 ms mono chunks."""
        import numpy as np

        sample_rate = self.robot.media.get_input_audio_samplerate()
        if not sample_rate or sample_rate <= 0:
            raise RuntimeError("Reachy WebRTC microphone has no valid sample rate")

        chunk_frames = max(1, int(sample_rate * 0.1))
        pending = np.empty((0, 1), dtype=np.float32)
        logger.info("Recording from Reachy WebRTC microphone at %d Hz", sample_rate)

        while not self._should_stop():
            sample = self.robot.media.get_audio_sample()
            if sample is None:
                await asyncio.sleep(0.01)
                continue

            audio = np.asarray(sample, dtype=np.float32)
            if audio.ndim == 1:
                audio = audio.reshape(-1, 1)
            elif audio.ndim == 2:
                if audio.shape[0] <= 2 < audio.shape[1]:
                    audio = audio.T
                audio = audio.mean(axis=1, keepdims=True)
            else:
                logger.warning("Ignoring unexpected Reachy audio shape: %s", audio.shape)
                continue

            if audio.size == 0:
                continue
            pending = np.concatenate((pending, audio), axis=0)

            while len(pending) >= chunk_frames and not self._should_stop():
                chunk = pending[:chunk_frames]
                pending = pending[chunk_frames:]
                await self.handler.receive((sample_rate, chunk))

            await asyncio.sleep(0)

    async def record_loop(self) -> None:
        """Read microphone audio and send it to the voice handler."""
        if self._use_robot_audio_input:
            await self._record_robot_media_loop()
            return

        import sounddevice as sd
        import queue as _queue
        import numpy as np

        SAMPLE_RATE = 16000
        CHUNK = 1600  # 100ms per chunk

        def _pick_device() -> tuple[int, int]:
            """Return (device_index, channels) for the best available input."""
            devices = sd.query_devices()

            # Try Reachy Mini Audio first — but verify it gives non-zero audio
            for i, d in enumerate(devices):
                if "Reachy Mini" in d["name"] and d["max_input_channels"] > 0:
                    channels = min(d["max_input_channels"], 2)
                    # Quick sanity check: capture 0.5s and see if any signal
                    test_frames: list = []
                    def _tcb(indata, f, t, s):
                        test_frames.append(indata.copy())
                    try:
                        with sd.InputStream(device=i, channels=channels, samplerate=SAMPLE_RATE,
                                            blocksize=CHUNK, dtype="float32", callback=_tcb):
                            import time as _time
                            _time.sleep(0.5)
                        if test_frames:
                            arr = np.concatenate(test_frames)
                            if np.max(np.abs(arr)) > 1e-6:
                                logger.info("Reachy Mini Audio (device %d) verified working", i)
                                return i, channels
                            else:
                                logger.warning("Reachy Mini Audio (device %d) gives silence, skipping", i)
                    except Exception as e:
                        logger.warning("Could not test Reachy Mini Audio: %s", e)
                    break

            # Fall back to system default input
            default_in = sd.default.device[0]
            if default_in is not None and default_in >= 0:
                d = devices[default_in]
                channels = min(d["max_input_channels"], 1) or 1
                logger.info("Using default input device %d (%s)", default_in, d["name"])
                return default_in, channels

            # Last resort: first available input device
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    logger.info("Using input device %d (%s)", i, d["name"])
                    return i, min(d["max_input_channels"], 1)

            raise RuntimeError("No input audio device found")

        device_index, channels = _pick_device()
        device_name = sd.query_devices(device_index)["name"]
        logger.info("Recording from '%s' (device %d, %dch) at %d Hz",
                    device_name, device_index, channels, SAMPLE_RATE)

        audio_queue: _queue.Queue = _queue.Queue()

        def _callback(indata, frames, time_info, status):
            if status:
                logger.debug("Sounddevice status: %s", status)
            # Mix to mono if stereo
            if indata.shape[1] > 1:
                mono = indata.mean(axis=1, keepdims=True)
            else:
                mono = indata
            audio_queue.put(mono.copy())

        with sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK,
            dtype="float32",
            callback=_callback,
        ):
            logger.info("Microphone stream open, listening...")
            while not self._should_stop():
                try:
                    chunk = audio_queue.get(timeout=0.1)
                    await self.handler.receive((SAMPLE_RATE, chunk))
                except _queue.Empty:
                    pass
                await asyncio.sleep(0)
            
    async def _push_audio_realtime(self, audio_data: Any, sample_rate: int) -> None:
        """Stream audio in small chunks so WebRTC can timestamp and encode it."""
        chunk_frames = max(1, int(sample_rate * 0.02))
        for start in range(0, len(audio_data), chunk_frames):
            if self._should_stop():
                break
            self.robot.media.push_audio_sample(audio_data[start : start + chunk_frames])
            await asyncio.sleep(0.01)

    async def _play_audio_via_daemon(self, audio_data: Any, sample_rate: int) -> None:
        """Upload a temporary WAV and let Reachy Control play it locally."""
        import tempfile
        import wave

        import numpy as np

        pcm = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
        path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                path = temp_file.name
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm.tobytes())

            await asyncio.to_thread(self.robot.media.play_sound, path)
            await asyncio.sleep(len(pcm) / sample_rate)
        finally:
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

    async def play_loop(self) -> None:
        """Play audio from handler through robot speakers."""
        output_sr = self.robot.media.get_output_audio_samplerate()
        logger.info("Playing at %d Hz", output_sr)
        
        while not self._should_stop():
            output = await self.handler.emit()
            if output is not None:
                if isinstance(output, tuple):
                    input_sr, audio_data = output
                    
                    # Convert to float32 and normalize (OpenAI sends int16)
                    audio_data = audio_data.flatten().astype("float32") / 32768.0
                    
                    # Local realtime playback needs extra headroom. Network
                    # mode uses Reachy Control's volume and clipping protection.
                    if not self._use_robot_audio_input:
                        audio_data = audio_data * 0.5
                    
                    # Resample if needed
                    if input_sr != output_sr:
                        from scipy.signal import resample
                        num_samples = int(len(audio_data) * output_sr / input_sr)
                        audio_data = resample(audio_data, num_samples).astype("float32")
                        
                    logger.info("Playing TTS audio: %d samples at %d Hz (%.1fs)",
                                len(audio_data), output_sr, len(audio_data) / output_sr)
                    if self._use_robot_audio_input:
                        await self._play_audio_via_daemon(audio_data, output_sr)
                    else:
                        await self._push_audio_realtime(audio_data, output_sr)
                # else: it's an AdditionalOutputs (transcript) - handle in UI mode
                
            await asyncio.sleep(0.01)
            
    async def run(self) -> None:
        """Run the main application loop."""
        # Test OpenClaw connection
        if self.openclaw_bridge is not None:
            connected = await self.openclaw_bridge.connect()
            if connected:
                logger.info("OpenClaw gateway connected")
            else:
                logger.warning("OpenClaw gateway not available - some features disabled")
        
        # Enable motors and move to neutral pose
        logger.info("Enabling motors and moving to neutral position...")
        try:
            self.robot.enable_motors()
            from reachy_mini.utils import create_head_pose
            neutral = create_head_pose(0, 0, 0, 0, 0, 0, degrees=True)
            self.robot.goto_target(
                head=neutral,
                antennas=[0.0, 0.0],
                duration=2.0,
                body_yaw=0.0,
            )
            time.sleep(2)  # Wait for goto to complete
            logger.info("Robot at neutral position with motors enabled")
        except Exception as e:
            logger.error("Failed to initialize robot pose: %s", e)
        
        # Wire up camera worker to movement manager for face tracking
        if self.camera_worker is not None:
            self.movement_manager.camera_worker = self.camera_worker
            logger.info("Face tracking connected to movement system")
        
        # Start movement system
        logger.info("Starting movement system...")
        self.movement_manager.start()
        self.head_wobbler.start()
        
        # Start camera worker for video streaming
        if self.camera_worker is not None:
            logger.info("Starting camera worker...")
            self.camera_worker.start()
        
        # Start local vision processor if available
        if self.vision_manager is not None:
            logger.info("Starting local vision processor...")
            self.vision_manager.start()
        
        # Start audio
        logger.info("Starting audio...")
        self.robot.media.start_recording()
        self.robot.media.start_playing()
        time.sleep(1)  # Let pipelines initialize
        
        logger.info("Ready! Speak to me...")
        
        # Start voice handler in background
        handler_task = asyncio.create_task(self.handler.start_up(), name="voice-handler")
        
        # Start audio loops
        self._tasks = [
            handler_task,
            asyncio.create_task(self.record_loop(), name="record-loop"),
            asyncio.create_task(self.play_loop(), name="play-loop"),
        ]
        
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
            
    def stop(self) -> None:
        """Stop everything."""
        logger.info("Stopping...")
        self._stop_event.set()
        
        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                
        # Stop movement system
        self.head_wobbler.stop()
        self.movement_manager.stop()
        
        # Stop vision manager
        if self.vision_manager is not None:
            self.vision_manager.stop()
        
        # Stop camera worker
        if self.camera_worker is not None:
            self.camera_worker.stop()
        
        # Disconnect OpenClaw bridge
        if self.openclaw_bridge is not None:
            try:
                asyncio.get_event_loop().run_until_complete(
                    self.openclaw_bridge.disconnect()
                )
            except Exception as e:
                logger.debug("OpenClaw disconnect: %s", e)
        
        # Close resources if we own them
        if self._owns_robot:
            try:
                self.robot.media.close()
            except Exception as e:
                logger.debug("Media close: %s", e)
            self.robot.client.disconnect()
            
        logger.info("Stopped")


class ClawBodyApp:
    """ClawBody - Reachy Mini Apps entry point.
    
    This class allows ClawBody to be installed and run from
    the Reachy Mini dashboard as a Reachy Mini App.
    """
    
    # No custom settings UI
    custom_app_url: Optional[str] = None
    
    def run(self, reachy_mini, stop_event: threading.Event) -> None:
        """Run ClawBody as a Reachy Mini App.
        
        Args:
            reachy_mini: Pre-initialized ReachyMini instance
            stop_event: Threading event to signal stop
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        gateway_url = os.getenv("OPENCLAW_GATEWAY_URL", "ws://localhost:18789")
        
        app = ClawBodyCore(
            gateway_url=gateway_url,
            robot=reachy_mini,
            external_stop_event=stop_event,
        )
        
        try:
            loop.run_until_complete(app.run())
        except Exception as e:
            logger.error("Error running app: %s", e)
        finally:
            app.stop()
            loop.close()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.debug)
    
    # Set custom profile if specified
    if args.profile:
        from reachy_mini_openclaw.config import set_custom_profile
        set_custom_profile(args.profile)
    
    # Configure face tracking and local vision from args
    from reachy_mini_openclaw.config import (
        set_face_tracking_enabled, 
        set_local_vision_enabled,
    )
    if args.no_face_tracking:
        set_face_tracking_enabled(False)
    if args.local_vision:
        set_local_vision_enabled(True)
    
    if args.gradio:
        # Launch Gradio UI
        logger.info("Starting Gradio UI...")
        from reachy_mini_openclaw.gradio_app import launch_gradio
        launch_gradio(
            gateway_url=args.gateway_url,
            robot_name=args.robot_name,
            robot_host=args.robot_host,
            robot_port=args.robot_port,
            enable_camera=not args.no_camera,
            enable_openclaw=not args.no_openclaw,
        )
    else:
        # Console mode
        app = ClawBodyCore(
            gateway_url=args.gateway_url,
            robot_name=args.robot_name,
            robot_host=args.robot_host,
            robot_port=args.robot_port,
            enable_camera=not args.no_camera,
            enable_openclaw=not args.no_openclaw,
            use_usb=args.usb,
        )
        
        try:
            asyncio.run(app.run())
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            app.stop()


if __name__ == "__main__":
    main()
