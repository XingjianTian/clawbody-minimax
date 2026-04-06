"""Configuration management for Reachy Mini OpenClaw.

Handles environment variables and configuration settings for the application.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # MiniMax Configuration
    MINIMAX_API_KEY: str = field(default_factory=lambda: os.getenv("MINIMAX_API_KEY", ""))
    MINIMAX_MODEL: str = field(default_factory=lambda: os.getenv("MINIMAX_MODEL", "MiniMax-M2.7"))
    MINIMAX_BASE_URL: str = field(default_factory=lambda: os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.chat/v1/"))

    # ElevenLabs Configuration
    ELEVENLABS_API_KEY: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    ELEVENLABS_VOICE_ID: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"))
    
    # OpenClaw Gateway Configuration
    OPENCLAW_GATEWAY_URL: str = field(default_factory=lambda: os.getenv("OPENCLAW_GATEWAY_URL", "ws://localhost:18789"))
    OPENCLAW_TOKEN: Optional[str] = field(default_factory=lambda: os.getenv("OPENCLAW_TOKEN"))
    OPENCLAW_AGENT_ID: str = field(default_factory=lambda: os.getenv("OPENCLAW_AGENT_ID", "main"))
    # Session key for OpenClaw - uses "main" to share context with WhatsApp and other channels
    # Format: agent:<agent_id>:<session_key>, but we only need the session key part here
    OPENCLAW_SESSION_KEY: str = field(default_factory=lambda: os.getenv("OPENCLAW_SESSION_KEY", "main"))
    
    # Robot Connection
    ROBOT_NAME: Optional[str] = field(default_factory=lambda: os.getenv("ROBOT_NAME"))
    ROBOT_HOST: str = field(default_factory=lambda: os.getenv("ROBOT_HOST", "reachy-mini.local"))
    ROBOT_PORT: int = field(default_factory=lambda: int(os.getenv("ROBOT_PORT", "8000")))
    
    # Feature Flags
    ENABLE_OPENCLAW_TOOLS: bool = field(default_factory=lambda: os.getenv("ENABLE_OPENCLAW_TOOLS", "true").lower() == "true")
    ENABLE_CAMERA: bool = field(default_factory=lambda: os.getenv("ENABLE_CAMERA", "true").lower() == "true")
    ENABLE_FACE_TRACKING: bool = field(default_factory=lambda: os.getenv("ENABLE_FACE_TRACKING", "true").lower() == "true")
    
    # Face Tracking Configuration
    # Options: "yolo", "mediapipe", or None for auto-detect
    HEAD_TRACKER_TYPE: Optional[str] = field(default_factory=lambda: os.getenv("HEAD_TRACKER_TYPE", "yolo"))
    
    # Local Vision Processing
    ENABLE_LOCAL_VISION: bool = field(default_factory=lambda: os.getenv("ENABLE_LOCAL_VISION", "false").lower() == "true")
    LOCAL_VISION_MODEL: str = field(default_factory=lambda: os.getenv("LOCAL_VISION_MODEL", "HuggingFaceTB/SmolVLM2-256M-Video-Instruct"))
    VISION_DEVICE: str = field(default_factory=lambda: os.getenv("VISION_DEVICE", "auto"))  # "auto", "cuda", "mps", "cpu"
    HF_HOME: str = field(default_factory=lambda: os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface")))
    
    # Custom Profile (for personality customization)
    CUSTOM_PROFILE: Optional[str] = field(default_factory=lambda: os.getenv("REACHY_MINI_CUSTOM_PROFILE"))
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        if not self.MINIMAX_API_KEY:
            errors.append("MINIMAX_API_KEY is required")
        if not self.ELEVENLABS_API_KEY:
            errors.append("ELEVENLABS_API_KEY is required")
        return errors


# Global configuration instance
config = Config()


def set_custom_profile(profile: Optional[str]) -> None:
    """Update the custom profile at runtime."""
    global config
    config.CUSTOM_PROFILE = profile
    os.environ["REACHY_MINI_CUSTOM_PROFILE"] = profile or ""


def set_face_tracking_enabled(enabled: bool) -> None:
    """Enable or disable face tracking at runtime."""
    global config
    config.ENABLE_FACE_TRACKING = enabled


def set_local_vision_enabled(enabled: bool) -> None:
    """Enable or disable local vision processing at runtime."""
    global config
    config.ENABLE_LOCAL_VISION = enabled
