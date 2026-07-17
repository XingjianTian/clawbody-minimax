"""Configuration management for Reachy Mini OpenClaw.

Handles environment variables and configuration settings for the application.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
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
    MINIMAX_BASE_URL: str = field(default_factory=lambda: os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1/"))
    MINIMAX_MAX_TOKENS: int = field(default_factory=lambda: int(os.getenv("MINIMAX_MAX_TOKENS", "80")))
    HTTP_TRUST_ENV: bool = field(default_factory=lambda: os.getenv("HTTP_TRUST_ENV", "false").lower() == "true")

    # Baidu ASR/TTS Configuration (replaces ElevenLabs)
    BAIDU_APP_ID: str = field(default_factory=lambda: os.getenv("BAIDU_APP_ID", ""))
    BAIDU_API_KEY: str = field(default_factory=lambda: os.getenv("BAIDU_API_KEY", ""))
    BAIDU_SECRET_KEY: str = field(default_factory=lambda: os.getenv("BAIDU_SECRET_KEY", ""))
    # Baidu TTS voice options: 0=female, 1=male, 3=duxiaomei, 4=duxiaoyao, 5=duyaya, 111=duboxiong
    BAIDU_TTS_PER: int = field(default_factory=lambda: int(os.getenv("BAIDU_TTS_PER", "111")))
    BAIDU_TTS_SPD: int = field(default_factory=lambda: int(os.getenv("BAIDU_TTS_SPD", "5")))  # speed 0-15
    BAIDU_TTS_PIT: int = field(default_factory=lambda: int(os.getenv("BAIDU_TTS_PIT", "5")))  # pitch 0-15
    BAIDU_TTS_VOL: int = field(default_factory=lambda: int(os.getenv("BAIDU_TTS_VOL", "12")))  # volume 0-15
    # Baidu ASR language: zh-CN, en-US, etc.
    BAIDU_ASR_LANGUAGE: str = field(default_factory=lambda: os.getenv("BAIDU_ASR_LANGUAGE", "zh-CN"))

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
    ROBOT_IDENTITY_FILE: str = field(
        default_factory=lambda: os.getenv("ROBOT_IDENTITY_FILE", "robot_identity/AGENTS.md")
    )

    # Feature Flags
    ENABLE_OPENCLAW_TOOLS: bool = field(default_factory=lambda: os.getenv("ENABLE_OPENCLAW_TOOLS", "true").lower() == "true")
    ENABLE_LLM_TOOLS: bool = field(default_factory=lambda: os.getenv("ENABLE_LLM_TOOLS", "false").lower() == "true")
    ENABLE_AUTO_MOTION: bool = field(default_factory=lambda: os.getenv("ENABLE_AUTO_MOTION", "true").lower() == "true")
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
        if not self.BAIDU_API_KEY:
            errors.append("BAIDU_API_KEY is required")
        if not self.BAIDU_SECRET_KEY:
            errors.append("BAIDU_SECRET_KEY is required")
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
