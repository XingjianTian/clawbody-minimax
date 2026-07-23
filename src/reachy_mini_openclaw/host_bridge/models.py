"""Typed contracts exposed by the Reachy host bridge."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class ChoreographyKind(StrEnum):
    EMOTION = "emotion"
    DANCE = "dance"
    MUSIC = "music"


CHOREOGRAPHY_MOVES: dict[ChoreographyKind, frozenset[str]] = {
    ChoreographyKind.EMOTION: frozenset({
        "fear1", "exhausted1", "loving1", "dance3", "boredom2", "relief1", "anxiety1",
        "disgusted1", "welcoming1", "impatient1", "sad1", "helpful2", "resigned1", "amazed1",
        "thoughtful2", "lost1", "surprised1", "serenity1", "displeased1", "incomprehensible2",
        "irritated2", "yes_sad1", "dance2", "understanding1", "contempt1", "inquiring1", "rage1",
        "attentive2", "no1", "oops1", "proud3", "reprimand3", "reprimand2", "scared1",
        "no_excited1", "come1", "proud2", "success1", "enthusiastic2", "laughing1", "dying1",
        "success2", "enthusiastic1", "curious1", "laughing2", "tired1", "reprimand1", "proud1",
        "grateful1", "frustrated1", "calming1", "attentive1", "furious1", "oops2", "irritated1",
        "yes1", "confused1", "understanding2", "dance1", "shy1", "inquiring2", "uncertain1",
        "thoughtful1", "surprised2", "displeased2", "impatient2", "welcoming2", "indifferent1",
        "sad2", "helpful1", "lonely1", "cheerful1", "inquiring3", "downcast1", "sleep1",
        "boredom1", "uncomfortable1", "go_away1", "electric1", "relief2", "no_sad1",
    }),
    ChoreographyKind.DANCE: frozenset({
        "stumble_and_recover", "chin_lead", "head_tilt_roll", "jackson_square", "pendulum_swing",
        "side_glance_flick", "grid_snap", "simple_nod", "side_to_side_sway", "polyrhythm_combo",
        "interwoven_spirals", "uh_huh_tilt", "chicken_peck", "yeah_nod", "headbanger_combo",
        "side_peekaboo", "dizzy_spin", "neck_recoil", "groovy_sway_and_roll", "sharp_side_tilt",
    }),
    ChoreographyKind.MUSIC: frozenset({
        "beyonce-single-ladies", "demon-hunters-1", "eagles-hotel-california", "eminem-lose-yourself",
        "feel-the-magic-in-the-air", "katy-perry-fireworks", "las-ketchup", "michael-jackson-thriller",
        "paint-it-black", "pharrell-williams-happy", "queen-we-will-rock-you", "spice-girls",
        "the-fratellis-whistle-for-the-choir", "the-white-stripes-seven-nation-army",
    }),
}


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


class ChoreographyRequest(BaseModel):
    kind: ChoreographyKind
    move: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_known_move(self) -> "ChoreographyRequest":
        if self.move not in CHOREOGRAPHY_MOVES[self.kind]:
            raise ValueError("unsupported choreography move")
        return self


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
