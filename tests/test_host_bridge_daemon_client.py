import asyncio
import json
import math
import time

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


def test_structured_daemon_error_redacts_nested_credentials():
    async def run() -> DaemonRequestError:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={
                    "detail": {
                        "token": "secret-token",
                        "nested": {
                            "api_key": "sk-private",
                            "authorization": "Bearer other-secret",
                            "safe": "retained",
                        },
                    }
                },
            )

        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            try:
                await client.status()
            except DaemonRequestError as error:
                return error
        finally:
            await client.aclose()
        raise AssertionError("status() did not raise DaemonRequestError")

    detail = asyncio.run(run()).detail
    assert "secret-token" not in detail
    assert "sk-private" not in detail
    assert "other-secret" not in detail
    assert detail.count("[REDACTED]") == 3
    assert "retained" in detail


def test_wait_until_ready_validates_inputs_and_honors_the_overall_deadline():
    async def slow_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.1)
        return httpx.Response(200, json={"state": "running"})

    async def run() -> float:
        client = ReachyDaemonClient(transport=httpx.MockTransport(slow_handler))
        try:
            try:
                await client.wait_until_ready(timeout=0.02, poll_interval=0.001)
            except TimeoutError:
                return time.monotonic()
        finally:
            await client.aclose()
        raise AssertionError("wait_until_ready() did not time out")

    started = time.monotonic()
    finished = asyncio.run(run())
    assert finished - started < 0.08

    async def validate_inputs() -> None:
        client = ReachyDaemonClient(transport=httpx.MockTransport(slow_handler))
        try:
            for timeout, poll_interval in ((0.0, 0.1), (1.0, 0.0), (-1.0, 0.1), (1.0, -0.1)):
                try:
                    await client.wait_until_ready(timeout=timeout, poll_interval=poll_interval)
                except ValueError:
                    continue
                raise AssertionError("wait_until_ready() accepted an invalid timeout or poll interval")
        finally:
            await client.aclose()

    asyncio.run(validate_inputs())


def test_wait_until_ready_retries_non_ready_and_error_responses():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(503, json={"detail": "starting"})
        if len(calls) == 2:
            return httpx.Response(200, json={"state": "starting"})
        return httpx.Response(200, json={"state": "running"})

    async def run() -> dict[str, object]:
        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            return await client.wait_until_ready(timeout=0.1, poll_interval=0.001)
        finally:
            await client.aclose()

    assert asyncio.run(run()) == {"state": "running"}
    assert calls == ["/api/daemon/status", "/api/daemon/status", "/api/daemon/status"]


def test_snapshot_degrades_malformed_optional_media_and_app_payloads():
    async def handler(request: httpx.Request) -> httpx.Response:
        responses = {
            "/api/daemon/status": {"state": "running"},
            "/api/motors/status": {"mode": "enabled"},
            "/api/media/status": {"available": True},
            "/api/volume/current": {"volume": 25},
            "/api/volume/microphone/current": {"volume": 50},
        }
        if request.url.path in {"/api/camera/specs", "/api/apps/current-app-status"}:
            return httpx.Response(200, content=b"this is not json")
        return httpx.Response(200, json=responses[request.url.path])

    async def run() -> dict[str, object]:
        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            return await client.snapshot()
        finally:
            await client.aclose()

    snapshot = asyncio.run(run())
    assert snapshot["motor_mode"] == "enabled"
    assert snapshot["media"].camera == "unavailable"
    assert snapshot["app_status"] is None


def test_fixed_actions_use_only_their_daemon_endpoints():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        return httpx.Response(200, json={"uuid": "00000000-0000-0000-0000-000000000001"})

    async def run() -> None:
        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            await client.perform(DeviceAction.GOTO_SLEEP)
            await client.perform(DeviceAction.TEST_SOUND)
        finally:
            await client.aclose()

    asyncio.run(run())
    assert requests == [
        ("POST", "/api/move/play/goto_sleep"),
        ("POST", "/api/volume/test-sound"),
    ]


def test_wait_until_move_finished_polls_until_uuid_is_absent():
    move_uuid = "00000000-0000-0000-0000-000000000001"
    responses = [
        [{"uuid": move_uuid}],
        [{"uuid": move_uuid}],
        [],
    ]
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json=responses.pop(0))

    async def run() -> None:
        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        try:
            await client.wait_until_move_finished(move_uuid, timeout=1.0, poll_interval=0.001)
        finally:
            await client.aclose()

    asyncio.run(run())
    assert requests == ["/api/move/running", "/api/move/running", "/api/move/running"]


def test_antenna_test_centers_antennas_after_cancellation():
    payloads = []
    started_sleep = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            started_sleep.set()
        return httpx.Response(200, json={"uuid": "00000000-0000-0000-0000-000000000001"})

    async def run() -> None:
        client = ReachyDaemonClient(transport=httpx.MockTransport(handler))
        task = asyncio.create_task(client.perform(DeviceAction.ANTENNA_TEST))
        try:
            await started_sleep.wait()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("ANTENNA_TEST did not propagate cancellation")
        finally:
            await client.aclose()

    asyncio.run(run())
    assert payloads == [
        {"antennas": [0.7, -0.7], "duration": 0.4, "interpolation": "minjerk"},
        {"antennas": [0.0, 0.0], "duration": 0.4, "interpolation": "minjerk"},
    ]
