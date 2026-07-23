from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from reachy_mini_openclaw.host_bridge import api as host_bridge_api
from reachy_mini_openclaw.host_bridge.daemon_client import DaemonRequestError, ReachyDaemonClient
from reachy_mini_openclaw.host_bridge.manager import DaemonManager
from reachy_mini_openclaw.host_bridge.models import (
    ChoreographyKind,
    ChoreographyRequest,
    DeviceAction,
    DeviceError,
    DevicePhase,
    DeviceStatus,
    PoseRequest,
    SerialDevice,
    StartRequest,
    VolumeRequest,
)

API_KEY = "test-host-bridge-key-with-sufficient-entropy"
AUTH_HEADERS = {"X-Host-Bridge-Key": API_KEY}


class FakeManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.failure: Exception | None = None
        self.cleanup_failure: Exception | None = None
        self.return_status = DeviceStatus(phase=DevicePhase.READY)

    async def discover(self) -> list[SerialDevice]:
        self.calls.append(("discover", None))
        return [SerialDevice(port="COM5", label="Reachy Mini Lite (COM5)")]

    async def status(self) -> DeviceStatus:
        self.calls.append(("status", None))
        return self.return_status

    async def start(self, request: StartRequest) -> DeviceStatus:
        self.calls.append(("start", request))
        return DeviceStatus(phase=DevicePhase.STARTING, serial_port=request.serial_port)

    async def stop(self) -> DeviceStatus:
        self.calls.append(("stop", None))
        return DeviceStatus()

    async def aclose(self) -> None:
        self.calls.append(("aclose", None))
        if self.cleanup_failure is not None:
            raise self.cleanup_failure

    async def restart(self, request: StartRequest) -> DeviceStatus:
        self.calls.append(("restart", request))
        return DeviceStatus(phase=DevicePhase.STARTING, serial_port=request.serial_port)

    async def perform(self, action: DeviceAction) -> DeviceStatus:
        self.calls.append(("perform", action))
        if self.failure is not None:
            raise self.failure
        return DeviceStatus(phase=DevicePhase.READY)

    async def play_choreography(self, request: ChoreographyRequest) -> DeviceStatus:
        self.calls.append(("play_choreography", request))
        return DeviceStatus(phase=DevicePhase.READY)

    async def set_pose(self, request: PoseRequest) -> DeviceStatus:
        self.calls.append(("set_pose", request))
        return DeviceStatus(phase=DevicePhase.READY)

    async def set_volume(self, request: VolumeRequest) -> DeviceStatus:
        self.calls.append(("set_volume", request))
        return DeviceStatus(phase=DevicePhase.READY)

    def logs_after(self, cursor: int) -> dict[str, int | list[dict[str, object]]]:
        self.calls.append(("logs_after", cursor))
        return {"cursor": cursor + 1, "items": []}


@pytest.fixture
def manager() -> FakeManager:
    return FakeManager()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, manager: FakeManager):
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    with TestClient(host_bridge_api.create_app(manager)) as test_client:
        yield test_client


def test_health_is_public(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/v1/device/discover", None),
        ("GET", "/v1/device/status", None),
        ("POST", "/v1/device/start", {}),
        ("POST", "/v1/device/stop", None),
        ("POST", "/v1/device/restart", {}),
        ("POST", "/v1/device/action", {"action": "wake_up"}),
        ("POST", "/v1/device/choreography", {"kind": "emotion", "move": "loving1"}),
        ("POST", "/v1/device/pose", {}),
        ("POST", "/v1/device/volume", {"target": "speaker", "volume": 50}),
        ("GET", "/v1/device/logs?after=0", None),
    ],
)
def test_v1_routes_reject_missing_and_invalid_keys(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, object] | None,
):
    missing = client.request(method, path, json=body)
    invalid = client.request(method, path, headers={"X-Host-Bridge-Key": "wrong-key"}, json=body)
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json() == invalid.json() == {"detail": "invalid host bridge key"}


def test_key_verification_uses_constant_time_comparison(
    monkeypatch: pytest.MonkeyPatch,
    manager: FakeManager,
):
    comparisons: list[tuple[bytes, bytes]] = []

    def compare_digest(provided: bytes, expected: bytes) -> bool:
        comparisons.append((provided, expected))
        return False

    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    monkeypatch.setattr(host_bridge_api.hmac, "compare_digest", compare_digest)
    with TestClient(host_bridge_api.create_app(manager)) as test_client:
        response = test_client.get(
            "/v1/device/status",
            headers={"X-Host-Bridge-Key": "wrong-key"},
        )

    assert response.status_code == 401
    assert comparisons == [(b"wrong-key", API_KEY.encode())]


def test_non_ascii_key_is_rejected_as_unauthorized(client: TestClient):
    response = client.get(
        "/v1/device/status",
        headers=[(b"x-host-bridge-key", b"\xff")],
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid host bridge key"}


def test_routes_forward_only_typed_requests(client: TestClient, manager: FakeManager):
    assert client.get("/v1/device/discover", headers=AUTH_HEADERS).status_code == 200
    assert client.get("/v1/device/status", headers=AUTH_HEADERS).status_code == 200
    assert client.post(
        "/v1/device/start",
        headers=AUTH_HEADERS,
        json={"serial_port": "COM5"},
    ).status_code == 200
    assert client.post("/v1/device/stop", headers=AUTH_HEADERS).status_code == 200
    assert client.post(
        "/v1/device/restart",
        headers=AUTH_HEADERS,
        json={"serial_port": "COM8"},
    ).status_code == 200
    assert client.post(
        "/v1/device/action",
        headers=AUTH_HEADERS,
        json={"action": "center"},
    ).status_code == 200
    assert client.post(
        "/v1/device/choreography",
        headers=AUTH_HEADERS,
        json={"kind": "emotion", "move": "loving1"},
    ).status_code == 200
    assert client.post(
        "/v1/device/pose",
        headers=AUTH_HEADERS,
        json={"head_yaw": 12, "duration": 1.5},
    ).status_code == 200
    assert client.post(
        "/v1/device/volume",
        headers=AUTH_HEADERS,
        json={"target": "microphone", "volume": 65},
    ).status_code == 200

    calls = dict(manager.calls)
    assert isinstance(calls["start"], StartRequest)
    assert calls["start"].serial_port == "COM5"
    assert isinstance(calls["restart"], StartRequest)
    assert calls["restart"].serial_port == "COM8"
    assert calls["perform"] is DeviceAction.CENTER
    assert isinstance(calls["play_choreography"], ChoreographyRequest)
    assert calls["play_choreography"].kind is ChoreographyKind.EMOTION
    assert calls["play_choreography"].move == "loving1"
    assert isinstance(calls["set_pose"], PoseRequest)
    assert calls["set_pose"].head_yaw == 12
    assert isinstance(calls["set_volume"], VolumeRequest)
    assert calls["set_volume"].target == "microphone"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/v1/device/start", {"serial_port": "C:/robot.exe"}),
        ("/v1/device/action", {"action": "run_command"}),
        ("/v1/device/choreography", {"kind": "emotion", "move": "../../wake_up"}),
        ("/v1/device/choreography", {"kind": "music", "move": "loving1"}),
        ("/v1/device/pose", {"head_yaw": 66}),
        ("/v1/device/volume", {"target": "speaker", "volume": 101}),
    ],
)
def test_typed_request_validation_rejects_invalid_values(
    client: TestClient,
    path: str,
    body: dict[str, object],
):
    response = client.post(path, headers=AUTH_HEADERS, json=body)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/v1/device/start", {"serial_port": "COM5", "executable_path": "C:/robot.exe"}),
        ("/v1/device/stop", {"command": "taskkill /f"}),
        ("/v1/device/restart", {"shell": "powershell.exe"}),
        ("/v1/device/action", {"action": "wake_up", "command": "whoami"}),
        ("/v1/device/choreography", {"kind": "emotion", "move": "loving1", "path": "C:/robot.exe"}),
        ("/v1/device/pose", {"head_yaw": 0, "path": "C:/robot.exe"}),
        ("/v1/device/volume", {"target": "speaker", "volume": 50, "shell": "cmd.exe"}),
    ],
)
def test_request_bodies_reject_extra_shell_and_path_fields(
    client: TestClient,
    path: str,
    body: dict[str, object],
):
    response = client.post(path, headers=AUTH_HEADERS, json=body)
    assert response.status_code == 422


def test_logs_require_nonnegative_cursor(client: TestClient, manager: FakeManager):
    invalid = client.get("/v1/device/logs?after=-1", headers=AUTH_HEADERS)
    valid = client.get("/v1/device/logs?after=7", headers=AUTH_HEADERS)
    assert invalid.status_code == 422
    assert valid.status_code == 200
    assert valid.json() == {"cursor": 8, "items": []}
    assert ("logs_after", 7) in manager.calls


@pytest.mark.parametrize(
    "failure",
    [
        DaemonRequestError(503, "Authorization: Bearer top-secret"),
        RuntimeError("password=top-secret"),
    ],
)
def test_operation_errors_are_mapped_without_leaking_details(
    client: TestClient,
    manager: FakeManager,
    failure: Exception,
):
    manager.failure = failure
    response = client.post(
        "/v1/device/action",
        headers=AUTH_HEADERS,
        json={"action": "wake_up"},
    )
    assert response.status_code in {500, 502}
    assert "top-secret" not in response.text


def test_returned_device_error_detail_is_redacted_without_mutating_manager_status(
    client: TestClient,
    manager: FakeManager,
):
    manager.return_status = DeviceStatus(
        phase=DevicePhase.ERROR,
        error=DeviceError(
            code="daemon_start_failed",
            phase=DevicePhase.STARTING,
            message="The Reachy daemon could not be started.",
            detail="password=top-secret",
        ),
    )

    response = client.get("/v1/device/status", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["error"]["detail"] == "password=[REDACTED]"
    assert manager.return_status.error is not None
    assert manager.return_status.error.detail == "password=top-secret"


def test_insecure_api_key_refuses_application_startup(
    monkeypatch: pytest.MonkeyPatch,
    manager: FakeManager,
):
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", "replace-with-a-long-random-value")
    with pytest.raises(RuntimeError, match="HOST_BRIDGE_API_KEY"):
        with TestClient(host_bridge_api.create_app(manager)):
            pass


@pytest.mark.parametrize("configured_key", [None, ""])
def test_missing_or_empty_api_key_refuses_application_startup(
    monkeypatch: pytest.MonkeyPatch,
    manager: FakeManager,
    configured_key: str | None,
):
    if configured_key is None:
        monkeypatch.delenv("HOST_BRIDGE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("HOST_BRIDGE_API_KEY", configured_key)

    with pytest.raises(RuntimeError, match="HOST_BRIDGE_API_KEY"):
        with TestClient(host_bridge_api.create_app(manager)):
            pass


def test_application_shutdown_closes_only_through_manager(
    monkeypatch: pytest.MonkeyPatch,
    manager: FakeManager,
):
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    with TestClient(host_bridge_api.create_app(manager)):
        pass
    assert manager.calls == [("aclose", None)]


def test_application_shutdown_reports_cleanup_failure_without_secret(
    monkeypatch: pytest.MonkeyPatch,
    manager: FakeManager,
):
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    manager.cleanup_failure = RuntimeError("password=top-secret")

    with pytest.raises(RuntimeError, match="Host Bridge shutdown cleanup failed") as raised:
        with TestClient(host_bridge_api.create_app(manager)):
            pass

    assert "top-secret" not in str(raised.value)
    assert manager.calls == [("aclose", None)]


def test_application_shutdown_closes_underlying_http_transport(monkeypatch: pytest.MonkeyPatch):
    class TrackingTransport(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self.closed = False

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        async def aclose(self) -> None:
            self.closed = True

    transport = TrackingTransport()
    daemon_client = ReachyDaemonClient(transport=transport)
    manager = DaemonManager(
        discover_ports=lambda: [],
        daemon_client=daemon_client,
        clawbody_health_url="",
    )
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)

    with TestClient(host_bridge_api.create_app(manager)):
        pass

    assert transport.closed is True


def test_main_rejects_non_loopback_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    monkeypatch.setenv("HOST_BRIDGE_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="127.0.0.1"):
        host_bridge_api.main()


@pytest.mark.parametrize(
    ("configured_port", "message"),
    [
        ("not-a-port", "must be an integer"),
        ("0", "must be between 1 and 65535"),
        ("65536", "must be between 1 and 65535"),
    ],
)
def test_main_rejects_invalid_or_out_of_range_port(
    monkeypatch: pytest.MonkeyPatch,
    configured_port: str,
    message: str,
):
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    monkeypatch.setenv("HOST_BRIDGE_HOST", "127.0.0.1")
    monkeypatch.setenv("HOST_BRIDGE_PORT", configured_port)

    with pytest.raises(RuntimeError, match=message):
        host_bridge_api.main()


def test_main_runs_uvicorn_on_configured_loopback_port(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[object, str, int, bool]] = []

    def run(application: object, *, host: str, port: int, use_colors: bool) -> None:
        calls.append((application, host, port, use_colors))

    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    monkeypatch.setenv("HOST_BRIDGE_HOST", "127.0.0.1")
    monkeypatch.setenv("HOST_BRIDGE_PORT", "8791")
    monkeypatch.setattr(host_bridge_api.uvicorn, "run", run)
    host_bridge_api.main()
    assert calls == [(host_bridge_api.app, "127.0.0.1", 8791, False)]


def test_main_loads_api_key_from_working_directory_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[tuple[object, str, int, bool]] = []
    (tmp_path / ".env").write_text("HOST_BRIDGE_API_KEY=dotenv-host-bridge-key\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HOST_BRIDGE_API_KEY", raising=False)
    monkeypatch.setattr(
        host_bridge_api.uvicorn,
        "run",
        lambda app, *, host, port, use_colors: calls.append((app, host, port, use_colors)),
    )

    host_bridge_api.main()

    assert calls == [(host_bridge_api.app, "127.0.0.1", 7861, False)]
    assert host_bridge_api.os.environ["HOST_BRIDGE_API_KEY"] == "dotenv-host-bridge-key"


def test_main_keeps_real_environment_api_key_over_working_directory_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    (tmp_path / ".env").write_text("HOST_BRIDGE_API_KEY=dotenv-host-bridge-key\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", API_KEY)
    monkeypatch.setattr(host_bridge_api.uvicorn, "run", lambda *_args, **_kwargs: None)

    host_bridge_api.main()

    assert host_bridge_api.os.environ["HOST_BRIDGE_API_KEY"] == API_KEY


def test_create_default_app_loads_daemon_and_clawbody_urls_from_working_directory_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    (tmp_path / ".env").write_text(
        "HOST_BRIDGE_DAEMON_URL=http://127.0.0.1:8100\n"
        "HOST_BRIDGE_CLAWBODY_HEALTH_URL=http://127.0.0.1:8790/health\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HOST_BRIDGE_DAEMON_URL", raising=False)
    monkeypatch.delenv("HOST_BRIDGE_CLAWBODY_HEALTH_URL", raising=False)
    managers: list[DaemonManager] = []
    sentinel = object()
    monkeypatch.setattr(host_bridge_api, "create_app", lambda manager: managers.append(manager) or sentinel)

    assert host_bridge_api._create_default_app() is sentinel
    manager = managers[0]
    try:
        assert str(manager._daemon_client._client.base_url) == "http://127.0.0.1:8100/"
        assert manager._clawbody_health_url == "http://127.0.0.1:8790/health"
    finally:
        asyncio.run(manager._daemon_client.aclose())


def test_create_default_app_keeps_environment_urls_over_working_directory_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    (tmp_path / ".env").write_text(
        "HOST_BRIDGE_DAEMON_URL=http://127.0.0.1:8100\n"
        "HOST_BRIDGE_CLAWBODY_HEALTH_URL=http://127.0.0.1:8790/health\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOST_BRIDGE_DAEMON_URL", "http://127.0.0.1:8200")
    monkeypatch.setenv("HOST_BRIDGE_CLAWBODY_HEALTH_URL", "http://127.0.0.1:8890/health")
    managers: list[DaemonManager] = []
    monkeypatch.setattr(host_bridge_api, "create_app", lambda manager: managers.append(manager) or object())

    host_bridge_api._create_default_app()
    manager = managers[0]
    try:
        assert str(manager._daemon_client._client.base_url) == "http://127.0.0.1:8200/"
        assert manager._clawbody_health_url == "http://127.0.0.1:8890/health"
    finally:
        asyncio.run(manager._daemon_client.aclose())
