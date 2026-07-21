"""Typed contracts exposed by the Reachy host bridge."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DevicePhase(StrEnum):
    OFFLINE = "offline"
    DISCOVERING = "discovering"
    STARTING = "starting"
    CONNECTING = "connecting"
    HEALTHCHECKING = "healthchecking"
    LOADING_APPS = "loading_apps"
    READY = "ready"
    STOPPING = "stopping"
    ERROR = "error"


class DeviceAction(StrEnum):
    WAKE_UP = "wake_up"
    GOTO_SLEEP = "goto_sleep"
    CENTER = "center"
    ANTENNA_TEST = "antenna_test"
    TEST_SOUND = "test_sound"


class DeviceError(BaseModel):
    code: str
    phase: DevicePhase
    message: str
    detail: str | None = None


class SerialDevice(BaseModel):
    port: str
    label: str
    vid: str = "1A86"
    pid: str = "55D3"


class MediaStatus(BaseModel):
    camera: Literal["ready", "unavailable", "unknown"] = "unknown"
    microphone: Literal["ready", "unavailable", "unknown"] = "unknown"
    speaker: Literal["ready", "unavailable", "unknown"] = "unknown"
    input_volume: int | None = None
    output_volume: int | None = None


class DeviceStatus(BaseModel):
    phase: DevicePhase = DevicePhase.OFFLINE
    operation_id: str | None = None
    serial_port: str | None = None
    daemon_owned: bool = False
    daemon_pid: int | None = None
    daemon_version: str | None = None
    daemon_state: str | None = None
    motor_mode: str | None = None
    media: MediaStatus = Field(default_factory=MediaStatus)
    clawbody_reachable: bool = False
    error: DeviceError | None = None


class StartRequest(BaseModel):
    serial_port: str | None = Field(default=None, pattern=r"^COM\d+$")


class ActionRequest(BaseModel):
    action: DeviceAction


class PoseRequest(BaseModel):
    head_pitch: float = Field(default=0, ge=-40, le=40)
    head_roll: float = Field(default=0, ge=-40, le=40)
    head_yaw: float = Field(default=0, ge=-65, le=65)
    body_yaw: float = Field(default=0, ge=-180, le=180)
    left_antenna: float = Field(default=0, ge=-3.1416, le=3.1416)
    right_antenna: float = Field(default=0, ge=-3.1416, le=3.1416)
    duration: float = Field(default=0.5, ge=0.1, le=5)


class VolumeRequest(BaseModel):
    target: Literal["speaker", "microphone"]
    volume: int = Field(ge=0, le=100)


class LogEntry(BaseModel):
    id: int
    level: Literal["debug", "info", "warning", "error"]
    message: str
    created_at: str
