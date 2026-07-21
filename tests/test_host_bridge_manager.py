import asyncio
import subprocess
from collections.abc import Callable, Coroutine
from functools import wraps
from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, Mock

from reachy_mini_openclaw.host_bridge.log_store import LogStore
from reachy_mini_openclaw.host_bridge.manager import DaemonManager
from reachy_mini_openclaw.host_bridge.models import (
    DeviceAction,
    DevicePhase,
    MediaStatus,
    PoseRequest,
    StartRequest,
    VolumeRequest,
)


def async_test(function: Callable[[], Coroutine[Any, Any, None]]) -> Callable[[], None]:
    @wraps(function)
    def run() -> None:
        asyncio.run(function())

    return run


class FakeProcess:
    def __init__(
        self,
        pid: int = 4321,
        *,
        stdout: StringIO | None = None,
        wait_error: Exception | None = None,
        wait_returncode: int = 0,
    ) -> None:
        self.pid = pid
        self.stdout = stdout
        self.returncode: int | None = None
        self.wait_error = wait_error
        self.wait_returncode = wait_returncode
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.wait_error is not None:
            error = self.wait_error
            self.wait_error = None
            raise error
        self.returncode = self.wait_returncode if self.returncode is None else self.returncode
        return self.returncode


def daemon_client_ready() -> AsyncMock:
    client = AsyncMock()
    client.status.return_value = {"state": "running", "version": "1.8.0"}
    client.wait_until_ready.return_value = {"state": "running", "version": "1.8.0"}
    client.snapshot.return_value = {
        "daemon_status": {"state": "running", "version": "1.8.0"},
        "motor_mode": "enabled",
        "media": MediaStatus(camera="ready", microphone="ready", speaker="ready"),
        "app_status": None,
    }
    client.perform.return_value = {"uuid": "00000000-0000-0000-0000-000000000001"}
    client.set_pose.return_value = {"uuid": "00000000-0000-0000-0000-000000000001"}
    client.set_volume.return_value = {"volume": 50}
    return client


def make_manager(
    *,
    ports: list[str] | None = None,
    process: FakeProcess | None = None,
    daemon_client: AsyncMock | None = None,
) -> tuple[DaemonManager, Mock, AsyncMock, FakeProcess]:
    child = process or FakeProcess()
    process_factory = Mock(return_value=child)
    client = daemon_client or daemon_client_ready()
    manager = DaemonManager(
        discover_ports=Mock(return_value=ports if ports is not None else ["COM5"]),
        process_factory=process_factory,
        daemon_client=client,
        logs=LogStore(),
        clawbody_health_url="",
    )
    return manager, process_factory, client, child


async def wait_for_phase(manager: DaemonManager, phase: DevicePhase) -> None:
    for _ in range(100):
        if (await manager.status()).phase == phase:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"manager did not reach {phase}")


@async_test
async def test_discover_returns_only_reachy_serial_devices():
    discover_ports = Mock(return_value=["COM5", "COM8"])
    manager = DaemonManager(
        discover_ports=discover_ports,
        process_factory=Mock(),
        daemon_client=daemon_client_ready(),
        logs=LogStore(),
        clawbody_health_url="",
    )

    devices = await manager.discover()

    assert [device.model_dump() for device in devices] == [
        {"port": "COM5", "label": "Reachy Mini Lite (COM5)", "vid": "1A86", "pid": "55D3"},
        {"port": "COM8", "label": "Reachy Mini Lite (COM8)", "vid": "1A86", "pid": "55D3"},
    ]
    discover_ports.assert_called_once_with()


@async_test
async def test_two_concurrent_starts_create_one_process():
    manager, process_factory, _, _ = make_manager()

    results = await asyncio.gather(manager.start(StartRequest()), manager.start(StartRequest()))

    assert process_factory.call_count == 1
    assert results[0].operation_id == results[1].operation_id
    await wait_for_phase(manager, DevicePhase.READY)


@async_test
async def test_start_uses_internal_command_and_reports_each_phase():
    observed_phases: list[DevicePhase] = []
    manager: DaemonManager

    async def record_status_phase() -> dict[str, str]:
        observed_phases.append((await manager.status()).phase)
        return {"state": "starting"}

    async def record_healthcheck_phase(*, timeout: float) -> dict[str, str]:
        assert timeout == 45.0
        observed_phases.append((await manager.status()).phase)
        return {"state": "running", "version": "1.8.0"}

    async def record_loading_phase() -> dict[str, object]:
        observed_phases.append((await manager.status()).phase)
        return {
            "daemon_status": {"state": "running", "version": "1.8.0"},
            "motor_mode": "enabled",
            "media": MediaStatus(),
            "app_status": None,
        }

    client = daemon_client_ready()
    client.status.side_effect = record_status_phase
    client.wait_until_ready.side_effect = record_healthcheck_phase
    client.snapshot.side_effect = record_loading_phase
    manager, process_factory, _, child = make_manager(daemon_client=client)

    result = await manager.start(StartRequest(serial_port="COM5"))
    await wait_for_phase(manager, DevicePhase.READY)

    assert result.phase == DevicePhase.STARTING
    command = process_factory.call_args.args[0]
    kwargs = process_factory.call_args.kwargs
    assert command[1:] == [
        "-m",
        "reachy_mini.daemon.app.main",
        "--serialport",
        "COM5",
        "--localhost-only",
        "--log-level",
        "INFO",
    ]
    assert kwargs["stdout"] is subprocess.PIPE
    assert kwargs["stderr"] is subprocess.STDOUT
    assert kwargs["creationflags"] == (
        getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    assert observed_phases == [DevicePhase.CONNECTING, DevicePhase.HEALTHCHECKING, DevicePhase.LOADING_APPS]
    final_status = await manager.status()
    assert final_status.daemon_owned is True
    assert final_status.daemon_pid == child.pid
    assert final_status.serial_port == "COM5"


@async_test
async def test_multiple_ports_require_explicit_selection():
    manager, process_factory, _, _ = make_manager(ports=["COM5", "COM8"])

    status = await manager.start(StartRequest())

    assert status.phase == DevicePhase.ERROR
    assert status.error is not None
    assert status.error.code == "multiple_serial_ports"
    process_factory.assert_not_called()


@async_test
async def test_requested_port_must_exactly_match_discovery():
    manager, process_factory, _, _ = make_manager(ports=["COM5"])

    status = await manager.start(StartRequest(serial_port="COM8"))

    assert status.phase == DevicePhase.ERROR
    assert status.error is not None
    assert status.error.code == "serial_port_not_found"
    process_factory.assert_not_called()


@async_test
async def test_stop_never_terminates_reused_external_daemon():
    manager, process_factory, daemon_client, _ = make_manager()
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}

    external = await manager.status()
    result = await manager.stop()

    assert external.daemon_owned is False
    assert external.daemon_state == "running"
    assert result.error is not None
    assert result.error.code == "daemon_not_owned"
    process_factory.assert_not_called()


@async_test
async def test_start_reuses_a_detected_external_daemon_without_spawning():
    manager, process_factory, daemon_client, _ = make_manager()
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}
    await manager.status()

    result = await manager.start(StartRequest())

    assert result.phase == DevicePhase.READY
    assert result.daemon_owned is False
    assert result.daemon_state == "running"
    process_factory.assert_not_called()


@async_test
async def test_stop_sleeps_then_terminates_only_the_recorded_process():
    manager, _, daemon_client, child = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    result = await manager.stop()

    daemon_client.perform.assert_awaited_with(DeviceAction.GOTO_SLEEP)
    assert child.terminate_calls == 1
    assert child.kill_calls == 0
    assert result.phase == DevicePhase.OFFLINE
    assert result.daemon_owned is False
    assert result.daemon_pid is None


@async_test
async def test_stop_kills_only_owned_process_when_terminate_times_out():
    child = FakeProcess(wait_error=subprocess.TimeoutExpired(cmd="reachy-daemon", timeout=5))
    manager, _, _, child = make_manager(process=child)
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    result = await manager.stop()

    assert child.terminate_calls == 1
    assert child.kill_calls == 1
    assert result.phase == DevicePhase.OFFLINE


@async_test
async def test_restart_and_typed_controls_delegate_to_daemon_client():
    manager, process_factory, daemon_client, first_child = make_manager()
    second_child = FakeProcess(pid=4322)
    process_factory.side_effect = [first_child, second_child]
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    pose = PoseRequest(head_yaw=10)
    volume = VolumeRequest(target="speaker", volume=50)

    await manager.perform(DeviceAction.CENTER)
    await manager.set_pose(pose)
    await manager.set_volume(volume)
    restarted = await manager.restart(StartRequest())

    daemon_client.perform.assert_any_await(DeviceAction.CENTER)
    daemon_client.set_pose.assert_awaited_once_with(pose)
    daemon_client.set_volume.assert_awaited_once_with(volume)
    assert process_factory.call_count == 2
    assert restarted.operation_id is not None
    await wait_for_phase(manager, DevicePhase.READY)
    await manager.stop()


@async_test
async def test_process_output_is_classified_and_redacted():
    manager, _, _, _ = make_manager()
    lines = [
        "daemon started\n",
        "WARNING token=secret-token\n",
        "ERROR Authorization: Bearer private-token\n",
    ]

    manager._stream_process_output(lines, process=None, pid=None)
    result = manager.logs_after(0)

    assert [item["level"] for item in result["items"]] == ["info", "warning", "error"]
    assert "secret-token" not in str(result)
    assert "private-token" not in str(result)


@async_test
async def test_child_exit_during_startup_cannot_be_overwritten_by_ready():
    child = FakeProcess(stdout=StringIO("ERROR daemon crashed\n"), wait_returncode=7)
    daemon_client = daemon_client_ready()

    async def delayed_status() -> dict[str, str]:
        await asyncio.sleep(0.01)
        return {"state": "starting"}

    daemon_client.status.side_effect = delayed_status
    manager, _, _, _ = make_manager(process=child, daemon_client=daemon_client)

    await manager.start(StartRequest())
    await asyncio.sleep(0.03)
    result = await manager.status()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_exited"
    assert result.daemon_owned is False
    assert result.daemon_pid is None


@async_test
async def test_status_reconciles_an_owned_process_that_has_exited():
    manager, _, _, child = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    child.returncode = 9
    result = await manager.status()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_exited"
    assert result.daemon_owned is False
    assert result.daemon_pid is None
