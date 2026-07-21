"""Typed client for the local Reachy Mini daemon REST API."""

from __future__ import annotations

import asyncio
import json
import math
import time
from typing import Any, Self, cast

import httpx

from .log_store import REDACTIONS
from .models import DeviceAction, MediaStatus, PoseRequest, VolumeRequest

ACTION_PATHS = {
    DeviceAction.WAKE_UP: "/api/move/play/wake_up",
    DeviceAction.GOTO_SLEEP: "/api/move/play/goto_sleep",
    DeviceAction.TEST_SOUND: "/api/volume/test-sound",
}


class DaemonRequestError(RuntimeError):
    """A non-success response returned by the Reachy daemon."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = _redact_detail(detail)
        super().__init__(f"Reachy daemon request failed ({status_code}): {self.detail}")


class ReachyDaemonClient:
    """Call the fixed Reachy daemon API surface used by the host bridge."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 5.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the single HTTP client owned by this daemon client."""
        await self._client.aclose()

    async def status(self) -> dict[str, Any]:
        """Return the Reachy daemon status payload."""
        return await self._get_object("/api/daemon/status")

    async def wait_until_ready(
        self,
        timeout: float = 45.0,
        poll_interval: float = 0.5,
    ) -> dict[str, Any]:
        """Wait until the daemon reports a running or ready state."""
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None

        while True:
            try:
                daemon_status = await self.status()
                state = str(daemon_status.get("state", "")).lower()
                if state in {"running", "ready"}:
                    return daemon_status
            except (DaemonRequestError, httpx.HTTPError) as error:
                last_error = error

            if time.monotonic() >= deadline:
                message = "Reachy daemon did not become ready before the timeout"
                if last_error is not None:
                    raise TimeoutError(message) from last_error
                raise TimeoutError(message)
            await asyncio.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    async def snapshot(self) -> dict[str, Any]:
        """Return daemon, motor, app, and best-effort media state."""
        daemon_status = await self.status()
        motor_status = await self._get_object("/api/motors/status")
        media_status = await self._optional_object("/api/media/status")
        camera_specs = await self._optional_object("/api/camera/specs")
        speaker_volume = await self._optional_object("/api/volume/current")
        microphone_volume = await self._optional_object("/api/volume/microphone/current")
        app_status = await self._optional_value("/api/apps/current-app-status")

        media_available = media_status.get("available") if media_status is not None else None
        media = MediaStatus(
            camera=self._media_component_state(media_available, camera_specs),
            speaker=self._media_component_state(media_available, speaker_volume),
            microphone=self._media_component_state(media_available, microphone_volume),
            output_volume=self._volume_value(speaker_volume),
            input_volume=self._volume_value(microphone_volume),
        )
        return {
            "daemon_status": daemon_status,
            "motor_mode": motor_status.get("mode"),
            "media": media,
            "app_status": app_status,
        }

    async def perform(self, action: DeviceAction) -> dict[str, Any] | None:
        """Perform one supported robot action."""
        if action in ACTION_PATHS:
            return await self._post_object(ACTION_PATHS[action])
        if action is DeviceAction.CENTER:
            return await self.set_pose(PoseRequest(duration=1.0))
        if action is DeviceAction.ANTENNA_TEST:
            await self._post_object(
                "/api/move/goto",
                json={"antennas": [0.7, -0.7], "duration": 0.4, "interpolation": "minjerk"},
            )
            await asyncio.sleep(0.4)
            return await self._post_object(
                "/api/move/goto",
                json={"antennas": [0.0, 0.0], "duration": 0.4, "interpolation": "minjerk"},
            )
        raise ValueError(f"Unsupported device action: {action}")

    async def set_pose(self, pose: PoseRequest) -> dict[str, Any]:
        """Move to a pose expressed by the host bridge's typed degree fields."""
        return await self._post_object("/api/move/goto", json=self._pose_payload(pose))

    async def set_volume(self, request: VolumeRequest) -> dict[str, Any]:
        """Set the validated speaker or microphone volume."""
        path = "/api/volume/set" if request.target == "speaker" else "/api/volume/microphone/set"
        return await self._post_object(path, json={"volume": request.volume})

    async def _get_object(self, path: str) -> dict[str, Any]:
        value = await self._get_value(path)
        if not isinstance(value, dict):
            raise ValueError(f"Reachy daemon returned a non-object payload for {path}")
        return value

    async def _post_object(self, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        value = await self._request_value("POST", path, json=json)
        if not isinstance(value, dict):
            raise ValueError(f"Reachy daemon returned a non-object payload for {path}")
        return value

    async def _get_value(self, path: str) -> Any:
        return await self._request_value("GET", path)

    async def _optional_object(self, path: str) -> dict[str, Any] | None:
        value = await self._optional_value(path)
        return value if isinstance(value, dict) else None

    async def _optional_value(self, path: str) -> Any | None:
        try:
            return await self._get_value(path)
        except (DaemonRequestError, httpx.HTTPError):
            return None

    async def _request_value(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self._client.request(method, path, **kwargs)
        if not response.is_success:
            raise DaemonRequestError(response.status_code, _response_detail(response))
        return cast(Any, response.json())

    @staticmethod
    def _media_component_state(
        media_available: Any,
        component_response: dict[str, Any] | None,
    ) -> str:
        if media_available is False:
            return "unavailable"
        if component_response is None:
            return "unavailable" if media_available is True else "unknown"
        return "ready" if media_available is True else "unknown"

    @staticmethod
    def _volume_value(response: dict[str, Any] | None) -> int | None:
        volume = response.get("volume") if response is not None else None
        return volume if isinstance(volume, int) else None

    @staticmethod
    def _pose_payload(pose: PoseRequest) -> dict[str, Any]:
        return {
            "head_pose": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "roll": math.radians(pose.head_roll),
                "pitch": math.radians(pose.head_pitch),
                "yaw": math.radians(pose.head_yaw),
            },
            "antennas": [pose.right_antenna, pose.left_antenna],
            "body_yaw": math.radians(pose.body_yaw),
            "duration": pose.duration,
            "interpolation": "minjerk",
        }


def _response_detail(response: httpx.Response) -> str:
    """Extract the daemon detail field without passing credentials through."""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    return response.text


def _redact_detail(detail: str) -> str:
    for pattern in REDACTIONS:
        detail = pattern.sub(r"\1[REDACTED]", detail)
    return detail
