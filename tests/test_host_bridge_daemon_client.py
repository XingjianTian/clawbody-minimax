import asyncio
import json
import math

import httpx

from reachy_mini_openclaw.host_bridge.daemon_client import DaemonRequestError, ReachyDaemonClient
from reachy_mini_openclaw.host_bridge.models import DeviceAction, PoseRequest, VolumeRequest


def test_wake_up_uses_reachy_move_endpoint():
    requests = []

    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.method, request.url.path))
            return httpx.Response(200, json={"uuid": "00000000-0000-0000-0000-000000000001"})

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            await client.perform(DeviceAction.WAKE_UP)
        finally:
            await client.aclose()

    asyncio.run(run())
    assert requests == [("POST", "/api/move/play/wake_up")]


def test_snapshot_degrades_camera_without_losing_motor_state():
    async def run():
        async def handler(request: httpx.Request) -> httpx.Response:
            responses = {
                "/api/daemon/status": {"state": "running", "version": "1.8.0"},
                "/api/motors/status": {"mode": "enabled"},
                "/api/media/status": {"available": True, "released": False, "no_media": False},
                "/api/volume/current": {"volume": 42},
                "/api/volume/microphone/current": {"volume": 24},
                "/api/apps/current-app-status": None,
            }
            if request.url.path == "/api/camera/specs":
                return httpx.Response(503, json={"detail": "camera unavailable"})
            response = responses[request.url.path]
            if response is None:
                return httpx.Response(200, content=b"null")
            return httpx.Response(200, json=response)

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            return await client.snapshot()
        finally:
            await client.aclose()

    snapshot = asyncio.run(run())

    assert snapshot["motor_mode"] == "enabled"
    assert snapshot["media"].camera == "unavailable"
    assert snapshot["media"].speaker == "ready"
    assert snapshot["media"].microphone == "ready"
    assert snapshot["media"].output_volume == 42
    assert snapshot["media"].input_volume == 24


def test_set_pose_posts_radians_and_daemon_antenna_order():
    payloads = []

    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"uuid": "00000000-0000-0000-0000-000000000001"})

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        pose = PoseRequest(
            head_pitch=30,
            head_roll=-20,
            head_yaw=45,
            body_yaw=90,
            left_antenna=0.25,
            right_antenna=-0.5,
            duration=1.5,
        )
        try:
            await client.set_pose(pose)
        finally:
            await client.aclose()

    asyncio.run(run())
    assert payloads == [
        {
            "head_pose": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "roll": math.radians(-20),
                "pitch": math.radians(30),
                "yaw": math.radians(45),
            },
            "antennas": [-0.5, 0.25],
            "body_yaw": math.radians(90),
            "duration": 1.5,
            "interpolation": "minjerk",
        }
    ]


def test_center_posts_a_zero_pose_with_a_one_second_duration():
    payloads = []

    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            payloads.append((request.method, request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"uuid": "00000000-0000-0000-0000-000000000001"})

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            await client.perform(DeviceAction.CENTER)
        finally:
            await client.aclose()

    asyncio.run(run())
    assert payloads == [
        (
            "POST",
            "/api/move/goto",
            {
                "head_pose": {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
                "antennas": [0.0, 0.0],
                "body_yaw": 0.0,
                "duration": 1.0,
                "interpolation": "minjerk",
            },
        )
    ]


def test_set_volume_uses_only_the_predefined_target_endpoint():
    requests = []

    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.method, request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"volume": 70})

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            await client.set_volume(VolumeRequest(target="speaker", volume=70))
            await client.set_volume(VolumeRequest(target="microphone", volume=35))
        finally:
            await client.aclose()

    asyncio.run(run())
    assert requests == [
        ("POST", "/api/volume/set", {"volume": 70}),
        ("POST", "/api/volume/microphone/set", {"volume": 35}),
    ]


def test_non_success_response_preserves_redacted_daemon_detail():
    async def run() -> DaemonRequestError:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "Authorization: Bearer secret-token is invalid"})

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            try:
                await client.status()
            except DaemonRequestError as error:
                return error
        finally:
            await client.aclose()
        raise AssertionError("status() did not raise DaemonRequestError")

    error = asyncio.run(run())
    assert error.status_code == 503
    assert error.detail == "Authorization: Bearer [REDACTED] is invalid"
