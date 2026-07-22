import asyncio
import subprocess
import sys
from collections.abc import Callable, Coroutine
from functools import wraps
from io import StringIO
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from reachy_mini_openclaw.host_bridge.log_store import LogStore
from reachy_mini_openclaw.host_bridge.manager import DaemonManager
from reachy_mini_openclaw.host_bridge.models import (
    DeviceAction,
    DevicePhase,
    DeviceStatus,
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
        terminate_error: Exception | None = None,
        kill_error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.pid = pid
        self.stdout = stdout
        self.returncode: int | None = None
        self.wait_error = wait_error
        self.wait_returncode = wait_returncode
        self.terminate_error = terminate_error
        self.kill_error = kill_error
        self.events = events
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self.events is not None:
            self.events.append("terminate")
        if self.terminate_error is not None:
            raise self.terminate_error

    def kill(self) -> None:
        self.kill_calls += 1
        if self.kill_error is not None:
            raise self.kill_error
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_error is not None:
            error = self.wait_error
            self.wait_error = None
            raise error
        self.returncode = self.wait_returncode if self.returncode is None else self.returncode
        return self.returncode


def daemon_snapshot(
    *,
    state: str = "running",
    version: str = "1.8.0",
    motor_mode: str = "enabled",
    media: MediaStatus | None = None,
) -> dict[str, object]:
    return {
        "daemon_status": {"state": state, "version": version},
        "motor_mode": motor_mode,
        "media": media or MediaStatus(camera="ready", microphone="ready", speaker="ready"),
        "app_status": None,
    }


def daemon_client_ready() -> AsyncMock:
    client = AsyncMock()
    client.status.return_value = {"state": "running", "version": "1.8.0"}
    client.wait_until_ready.return_value = {"state": "running", "version": "1.8.0"}
    client.snapshot.return_value = daemon_snapshot()
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
    if daemon_client is None:

        async def status_after_process_start() -> dict[str, str]:
            if manager._process is None:
                raise ConnectionError("daemon is not listening")
            return {"state": "running", "version": "1.8.0"}

        client.status.side_effect = status_after_process_start
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
async def test_default_discovery_uses_reachy_lite_usb_vid_and_pid():
    find_serial_port = Mock(return_value=["COM7"])
    reachy_module = ModuleType("reachy_mini")
    daemon_module = ModuleType("reachy_mini.daemon")
    utils_module = ModuleType("reachy_mini.daemon.utils")
    utils_module.find_serial_port = find_serial_port

    with patch.dict(
        sys.modules,
        {
            "reachy_mini": reachy_module,
            "reachy_mini.daemon": daemon_module,
            "reachy_mini.daemon.utils": utils_module,
        },
    ):
        manager = DaemonManager(
            process_factory=Mock(),
            daemon_client=daemon_client_ready(),
            logs=LogStore(),
            clawbody_health_url="",
        )
        devices = await manager.discover()

    assert [device.port for device in devices] == ["COM7"]
    find_serial_port.assert_called_once_with(wireless_version=False, vid="1a86", pid="55d3")


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
        if manager._process is None:
            raise ConnectionError("daemon is not listening")
        observed_phases.append((await manager.status()).phase)
        return {"state": "starting"}

    async def record_healthcheck_phase(*, timeout: float) -> dict[str, str]:
        assert timeout == 45.0
        observed_phases.append((await manager.status()).phase)
        return {"state": "running", "version": "1.8.0"}

    async def record_loading_phase() -> dict[str, object]:
        if manager._status.phase == DevicePhase.LOADING_APPS:
            observed_phases.append(manager._status.phase)
        return daemon_snapshot(media=MediaStatus())

    client = daemon_client_ready()
    client.status.side_effect = record_status_phase
    client.wait_until_ready.side_effect = record_healthcheck_phase
    client.snapshot.side_effect = record_loading_phase
    manager, process_factory, _, child = make_manager(daemon_client=client)
    wait_for_listening = AsyncMock(wraps=manager._wait_for_daemon_listening)
    manager._wait_for_daemon_listening = wait_for_listening

    result = await manager.start(StartRequest(serial_port="COM5"))
    await wait_for_phase(manager, DevicePhase.READY)

    assert result.phase == DevicePhase.STARTING
    command = process_factory.call_args.args[0]
    kwargs = process_factory.call_args.kwargs
    assert command[0] == sys.executable
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
    wait_for_listening.assert_awaited_once_with(child, timeout=45.0)
    assert observed_phases == [DevicePhase.CONNECTING, DevicePhase.HEALTHCHECKING, DevicePhase.LOADING_APPS]
    final_status = await manager.status()
    assert final_status.daemon_owned is True
    assert final_status.daemon_pid == child.pid
    assert final_status.serial_port == "COM5"


@async_test
async def test_daemon_listen_timeout_reports_configured_duration():
    daemon_client = daemon_client_ready()
    daemon_client.status.side_effect = ConnectionError("daemon is not listening")
    manager, _, _, child = make_manager(daemon_client=daemon_client)

    with pytest.raises(TimeoutError, match=r"within 0\.01 seconds"):
        await manager._wait_for_daemon_listening(child, timeout=0.01)


@async_test
async def test_multiple_ports_require_explicit_selection():
    manager, process_factory, _, _ = make_manager(ports=["COM5", "COM8"])

    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.ERROR)
    status = await manager.status()

    assert status.phase == DevicePhase.ERROR
    assert status.error is not None
    assert status.error.code == "multiple_serial_ports"
    process_factory.assert_not_called()


@async_test
async def test_requested_port_must_exactly_match_discovery():
    manager, process_factory, _, _ = make_manager(ports=["COM5"])

    await manager.start(StartRequest(serial_port="COM8"))
    await wait_for_phase(manager, DevicePhase.ERROR)
    status = await manager.status()

    assert status.phase == DevicePhase.ERROR
    assert status.error is not None
    assert status.error.code == "serial_port_not_found"
    process_factory.assert_not_called()


@async_test
async def test_stop_never_terminates_reused_external_daemon():
    manager, process_factory, daemon_client, _ = make_manager()
    daemon_client.status.side_effect = None
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}

    external = await manager.status()
    result = await manager.stop()

    assert external.daemon_owned is False
    assert external.daemon_state == "running"
    assert result.error is not None
    assert result.error.code == "daemon_not_owned"
    process_factory.assert_not_called()


@async_test
async def test_stop_during_external_readiness_reports_not_owned_without_cancelling():
    readiness_started = asyncio.Event()
    release_readiness = asyncio.Event()
    daemon_client = daemon_client_ready()
    daemon_client.status.return_value = {"state": "starting", "version": "1.8.0"}

    async def wait_for_external_ready(*, timeout: float) -> dict[str, str]:
        readiness_started.set()
        await release_readiness.wait()
        return {"state": "running", "version": "1.8.0"}

    daemon_client.wait_until_ready.side_effect = wait_for_external_ready
    manager, process_factory, _, _ = make_manager(daemon_client=daemon_client)

    started = await manager.start(StartRequest())
    await readiness_started.wait()
    operation_task = manager._operation_task
    assert operation_task is not None

    stopped = await manager.stop()

    assert stopped.operation_id == started.operation_id
    assert stopped.phase == DevicePhase.ERROR
    assert stopped.error is not None
    assert stopped.error.code == "daemon_not_owned"
    assert operation_task.done() is False
    process_factory.assert_not_called()
    daemon_client.perform.assert_not_awaited()

    release_readiness.set()
    await operation_task
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}
    ready = await manager.status()
    assert ready.phase == DevicePhase.READY
    assert ready.daemon_owned is False


@async_test
async def test_external_stop_rejection_preserves_readiness_failure_classification():
    readiness_started = asyncio.Event()
    release_readiness = asyncio.Event()
    daemon_client = daemon_client_ready()
    daemon_client.status.return_value = {"state": "starting", "version": "1.8.0"}

    async def fail_external_readiness(*, timeout: float) -> dict[str, str]:
        readiness_started.set()
        await release_readiness.wait()
        raise RuntimeError("external readiness failed")

    daemon_client.wait_until_ready.side_effect = fail_external_readiness
    manager, process_factory, _, _ = make_manager(daemon_client=daemon_client)

    await manager.start(StartRequest())
    await readiness_started.wait()
    operation_task = manager._operation_task
    assert operation_task is not None

    stopped = await manager.stop()

    assert stopped.phase == DevicePhase.ERROR
    assert stopped.error is not None
    assert stopped.error.code == "daemon_not_owned"
    assert manager._status.phase == DevicePhase.HEALTHCHECKING
    assert manager._status.error is None
    assert operation_task.done() is False
    process_factory.assert_not_called()
    daemon_client.perform.assert_not_awaited()

    release_readiness.set()
    await operation_task
    failed = await manager.status()
    assert failed.phase == DevicePhase.ERROR
    assert failed.error is not None
    assert failed.error.code == "daemon_healthcheck_failed"
    assert "external readiness failed" in (failed.error.detail or "")


@async_test
async def test_start_probes_and_reuses_an_external_daemon_without_spawning():
    manager, process_factory, daemon_client, _ = make_manager()
    daemon_client.status.side_effect = None
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}

    started = await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    result = await manager.status()

    assert started.operation_id is not None
    assert result.phase == DevicePhase.READY
    assert result.daemon_owned is False
    assert result.daemon_state == "running"
    process_factory.assert_not_called()


@async_test
async def test_starting_external_daemon_never_spawns_owned_process():
    release_ready = asyncio.Event()
    daemon_client = daemon_client_ready()
    daemon_client.status.return_value = {"state": "starting", "version": "1.8.0"}

    async def wait_for_external_ready(*, timeout: float) -> dict[str, str]:
        await release_ready.wait()
        return {"state": "running", "version": "1.8.0"}

    daemon_client.wait_until_ready.side_effect = wait_for_external_ready
    manager, process_factory, _, _ = make_manager(daemon_client=daemon_client)

    started = await manager.start(StartRequest())
    await asyncio.sleep(0)
    try:
        assert started.operation_id is not None
        process_factory.assert_not_called()
    finally:
        release_ready.set()


@async_test
async def test_external_start_returns_operation_id_without_waiting_for_probe():
    probe_started = asyncio.Event()
    release_probe = asyncio.Event()
    daemon_client = daemon_client_ready()

    async def delayed_external_status() -> dict[str, str]:
        probe_started.set()
        await release_probe.wait()
        return {"state": "running", "version": "1.8.0"}

    daemon_client.status.side_effect = delayed_external_status
    manager, process_factory, _, _ = make_manager(daemon_client=daemon_client)

    started = await asyncio.wait_for(manager.start(StartRequest()), timeout=0.05)

    assert started.operation_id is not None
    await probe_started.wait()
    process_factory.assert_not_called()
    release_probe.set()
    await wait_for_phase(manager, DevicePhase.READY)


@async_test
async def test_owned_start_returns_operation_id_without_waiting_for_probe():
    probe_started = asyncio.Event()
    release_probe = asyncio.Event()
    daemon_client = daemon_client_ready()
    probe_calls = 0

    async def delayed_offline_status() -> dict[str, str]:
        nonlocal probe_calls
        probe_calls += 1
        if probe_calls == 1:
            probe_started.set()
            await release_probe.wait()
            raise ConnectionError("daemon offline")
        return {"state": "running", "version": "1.8.0"}

    daemon_client.status.side_effect = delayed_offline_status
    manager, process_factory, _, _ = make_manager(daemon_client=daemon_client)

    started = await asyncio.wait_for(manager.start(StartRequest()), timeout=0.05)

    assert started.operation_id is not None
    await probe_started.wait()
    process_factory.assert_not_called()
    release_probe.set()
    await wait_for_phase(manager, DevicePhase.READY)
    assert process_factory.call_count == 1


@async_test
async def test_unreachable_external_daemon_clears_stale_ready_and_allows_start():
    manager, process_factory, daemon_client, _ = make_manager()
    daemon_client.status.side_effect = None
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}
    assert (await manager.status()).phase == DevicePhase.READY

    daemon_client.status.side_effect = [
        ConnectionError("external daemon exited"),
        ConnectionError("daemon still offline"),
        {"state": "running", "version": "1.8.0"},
    ]
    unreachable = await manager.status()
    started = await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    assert unreachable.phase == DevicePhase.OFFLINE
    assert unreachable.daemon_state is None
    assert unreachable.daemon_version is None
    assert started.phase == DevicePhase.STARTING
    assert process_factory.call_count == 1


@async_test
async def test_start_ignores_stale_external_ready_after_preflight_failure():
    manager, process_factory, daemon_client, _ = make_manager()
    daemon_client.status.side_effect = None
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}
    assert (await manager.status()).phase == DevicePhase.READY

    daemon_client.status.side_effect = [
        ConnectionError("external daemon exited"),
        {"state": "running", "version": "1.8.0"},
    ]
    started = await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    assert started.phase == DevicePhase.STARTING
    assert process_factory.call_count == 1


@async_test
async def test_start_preflight_failure_clears_stale_external_metadata_on_discovery_error():
    manager, process_factory, daemon_client, _ = make_manager(ports=[])
    daemon_client.status.side_effect = None
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}
    assert (await manager.status()).phase == DevicePhase.READY

    daemon_client.status.side_effect = ConnectionError("external daemon exited")
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.ERROR)
    result = await manager.status()

    assert result.phase == DevicePhase.ERROR
    assert result.daemon_state is None
    assert result.daemon_version is None
    process_factory.assert_not_called()


@async_test
async def test_non_running_external_response_clears_stale_ready():
    manager, _, daemon_client, _ = make_manager()
    daemon_client.status.side_effect = None
    daemon_client.status.return_value = {"state": "running", "version": "1.8.0"}
    assert (await manager.status()).phase == DevicePhase.READY

    daemon_client.status.return_value = {"state": "stopped", "version": "1.8.0"}
    stopped = await manager.status()

    assert stopped.phase == DevicePhase.OFFLINE
    assert stopped.daemon_state == "stopped"
    assert stopped.daemon_version == "1.8.0"


@async_test
async def test_stop_sleeps_then_terminates_only_the_recorded_process():
    manager, _, daemon_client, child = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    result = await manager.stop()

    daemon_client.perform.assert_awaited_with(DeviceAction.GOTO_SLEEP)
    daemon_client.wait_until_move_finished.assert_awaited_once_with(
        "00000000-0000-0000-0000-000000000001",
        timeout=8.0,
    )
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
async def test_stop_preserves_ownership_when_terminate_fails():
    child = FakeProcess(terminate_error=OSError("access denied"))
    manager, _, _, child = make_manager(process=child)
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    result = await manager.stop()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_stop_failed"
    assert result.daemon_owned is True
    assert result.daemon_pid == child.pid
    assert child.terminate_calls == 1
    assert child.kill_calls == 0


@async_test
async def test_stop_preserves_ownership_when_wait_fails():
    child = FakeProcess(wait_error=OSError("wait failed"))
    manager, _, _, child = make_manager(process=child)
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    result = await manager.stop()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_stop_failed"
    assert result.daemon_owned is True
    assert result.daemon_pid == child.pid
    assert child.terminate_calls == 1
    assert child.kill_calls == 0


@async_test
async def test_stop_preserves_ownership_when_kill_fails():
    child = FakeProcess(
        wait_error=subprocess.TimeoutExpired(cmd="reachy-daemon", timeout=5),
        kill_error=OSError("kill failed"),
    )
    manager, _, _, child = make_manager(process=child)
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    result = await manager.stop()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_stop_failed"
    assert result.daemon_owned is True
    assert result.daemon_pid == child.pid
    assert child.terminate_calls == 1
    assert child.kill_calls == 1


@async_test
async def test_connecting_stage_cancellation_terminates_owned_process():
    connecting = asyncio.Event()
    never_ready = asyncio.Event()
    status_calls = 0
    daemon_client = daemon_client_ready()

    async def block_while_connecting() -> dict[str, str]:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 1:
            raise ConnectionError("daemon is not listening")
        connecting.set()
        await never_ready.wait()
        return {"state": "running"}

    daemon_client.status.side_effect = block_while_connecting
    manager, _, _, child = make_manager(daemon_client=daemon_client)

    await manager.start(StartRequest())
    await connecting.wait()
    operation_task = manager._operation_task
    assert operation_task is not None
    operation_task.cancel()
    try:
        await operation_task
    except asyncio.CancelledError:
        pass

    daemon_client.status.side_effect = ConnectionError("daemon stopped")
    result = await manager.status()

    assert child.terminate_calls == 1
    assert child.kill_calls == 0
    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "startup_cancelled"
    assert result.daemon_owned is False
    assert result.daemon_pid is None


@async_test
async def test_stop_during_connecting_requests_sleep_before_terminate():
    events: list[str] = []
    child = FakeProcess(events=events)
    connecting = asyncio.Event()
    never_ready = asyncio.Event()
    status_calls = 0
    daemon_client = daemon_client_ready()

    async def block_while_connecting() -> dict[str, str]:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 1:
            raise ConnectionError("daemon offline")
        connecting.set()
        await never_ready.wait()
        return {"state": "running"}

    async def record_action(action: DeviceAction) -> dict[str, str]:
        assert action == DeviceAction.GOTO_SLEEP
        events.append("sleep")
        return {"uuid": "00000000-0000-0000-0000-000000000001"}

    async def wait_for_sleep(move_uuid: str, *, timeout: float) -> None:
        assert move_uuid == "00000000-0000-0000-0000-000000000001"
        assert timeout == 8.0
        events.append("wait_sleep")

    daemon_client.status.side_effect = block_while_connecting
    daemon_client.perform.side_effect = record_action
    daemon_client.wait_until_move_finished.side_effect = wait_for_sleep
    manager, _, _, _ = make_manager(process=child, daemon_client=daemon_client)

    await manager.start(StartRequest())
    await connecting.wait()
    result = await manager.stop()

    assert events == ["sleep", "wait_sleep", "terminate"]
    assert result.phase == DevicePhase.OFFLINE
    assert result.daemon_owned is False


@async_test
async def test_readiness_failure_preserves_owned_process_when_cleanup_is_denied():
    child = FakeProcess(terminate_error=PermissionError("cannot terminate recorded PID"))
    daemon_client = daemon_client_ready()
    status_calls = 0

    async def offline_then_listening() -> dict[str, str]:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 1:
            raise ConnectionError("daemon offline")
        return {"state": "running", "version": "1.8.0"}

    daemon_client.status.side_effect = offline_then_listening
    daemon_client.wait_until_ready.side_effect = RuntimeError("readiness failed")
    manager, _, _, _ = make_manager(process=child, daemon_client=daemon_client)

    started = await manager.start(StartRequest())
    operation_task = manager._operation_task
    assert operation_task is not None
    task_result = (await asyncio.gather(operation_task, return_exceptions=True))[0]
    result = await manager.status()

    assert task_result is None
    assert result.operation_id == started.operation_id
    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_healthcheck_failed"
    assert "readiness failed" in (result.error.detail or "")
    assert "cannot terminate recorded PID" in (result.error.detail or "")
    assert result.daemon_owned is True
    assert result.daemon_pid == child.pid


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
    await wait_for_phase(manager, DevicePhase.READY)

    daemon_client.perform.assert_any_await(DeviceAction.CENTER)
    daemon_client.set_pose.assert_awaited_once_with(pose)
    daemon_client.set_volume.assert_awaited_once_with(volume)
    assert process_factory.call_count == 2
    assert restarted.operation_id is not None
    await wait_for_phase(manager, DevicePhase.READY)
    await manager.stop()


@async_test
async def test_sleep_returns_disabled_motor_mode_from_live_daemon():
    manager, _, daemon_client, _ = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    snapshot_count = daemon_client.snapshot.await_count

    async def sleep(action: DeviceAction) -> dict[str, str]:
        assert action is DeviceAction.GOTO_SLEEP
        daemon_client.snapshot.return_value = daemon_snapshot(motor_mode="disabled")
        return {"uuid": "00000000-0000-0000-0000-000000000001"}

    daemon_client.perform.side_effect = sleep

    result = await manager.perform(DeviceAction.GOTO_SLEEP)

    assert result.motor_mode == "disabled"
    assert daemon_client.snapshot.await_count == snapshot_count + 1


@async_test
async def test_wake_returns_enabled_motor_mode_from_live_daemon():
    manager, _, daemon_client, _ = make_manager()
    daemon_client.snapshot.return_value = daemon_snapshot(motor_mode="disabled")
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    snapshot_count = daemon_client.snapshot.await_count

    async def wake(action: DeviceAction) -> dict[str, str]:
        assert action is DeviceAction.WAKE_UP
        daemon_client.snapshot.return_value = daemon_snapshot(motor_mode="enabled")
        return {"uuid": "00000000-0000-0000-0000-000000000001"}

    daemon_client.perform.side_effect = wake

    result = await manager.perform(DeviceAction.WAKE_UP)

    assert result.motor_mode == "enabled"
    assert daemon_client.snapshot.await_count == snapshot_count + 1


@async_test
async def test_set_volume_returns_current_media_after_optional_camera_failure():
    manager, _, daemon_client, _ = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    snapshot_count = daemon_client.snapshot.await_count
    request = VolumeRequest(target="speaker", volume=64)

    async def set_volume(volume_request: VolumeRequest) -> dict[str, int]:
        assert volume_request == request
        daemon_client.snapshot.return_value = daemon_snapshot(
            media=MediaStatus(
                camera="unavailable",
                microphone="ready",
                speaker="ready",
                input_volume=35,
                output_volume=64,
            )
        )
        return {"volume": 64}

    daemon_client.set_volume.side_effect = set_volume

    result = await manager.set_volume(request)

    assert result.media == MediaStatus(
        camera="unavailable",
        microphone="ready",
        speaker="ready",
        input_volume=35,
        output_volume=64,
    )
    assert daemon_client.snapshot.await_count == snapshot_count + 1


@async_test
async def test_set_pose_returns_current_daemon_snapshot():
    manager, _, daemon_client, _ = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    snapshot_count = daemon_client.snapshot.await_count
    pose = PoseRequest(head_yaw=12)

    async def set_pose(pose_request: PoseRequest) -> dict[str, str]:
        assert pose_request == pose
        daemon_client.snapshot.return_value = daemon_snapshot(state="ready", version="1.8.1")
        return {"uuid": "00000000-0000-0000-0000-000000000001"}

    daemon_client.set_pose.side_effect = set_pose

    result = await manager.set_pose(pose)

    assert result.daemon_state == "ready"
    assert result.daemon_version == "1.8.1"
    assert daemon_client.snapshot.await_count == snapshot_count + 1


@async_test
async def test_live_snapshot_failure_preserves_owned_process_identity_and_reports_error():
    manager, _, daemon_client, child = make_manager()
    started = await manager.start(StartRequest(serial_port="COM5"))
    await wait_for_phase(manager, DevicePhase.READY)
    daemon_client.snapshot.side_effect = ConnectionError("daemon snapshot unavailable")

    result = await manager.status()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_status_failed"
    assert result.error.phase == DevicePhase.READY
    assert result.daemon_owned is True
    assert result.daemon_pid == child.pid
    assert result.serial_port == "COM5"
    assert result.operation_id == started.operation_id
    assert child.terminate_calls == 0
    assert child.kill_calls == 0


@async_test
async def test_live_snapshot_recovers_only_its_transient_error():
    manager, _, daemon_client, child = make_manager()
    started = await manager.start(StartRequest(serial_port="COM5"))
    await wait_for_phase(manager, DevicePhase.READY)
    daemon_client.snapshot.side_effect = ConnectionError("temporary daemon snapshot failure")
    failed = await manager.status()
    assert failed.error is not None
    assert failed.error.code == "daemon_status_failed"

    daemon_client.snapshot.side_effect = None
    daemon_client.snapshot.return_value = daemon_snapshot(
        motor_mode="disabled",
        media=MediaStatus(camera="unavailable", microphone="ready", speaker="ready"),
    )

    recovered = await manager.status()

    assert recovered.phase == DevicePhase.READY
    assert recovered.error is None
    assert recovered.motor_mode == "disabled"
    assert recovered.daemon_owned is True
    assert recovered.daemon_pid == child.pid
    assert recovered.serial_port == "COM5"
    assert recovered.operation_id == started.operation_id


@async_test
async def test_live_snapshot_preserves_an_unrelated_owned_process_error():
    child = FakeProcess(terminate_error=OSError("access denied"))
    manager, _, daemon_client, _ = make_manager(process=child)
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    failed_stop = await manager.stop()
    assert failed_stop.error is not None
    assert failed_stop.error.code == "daemon_stop_failed"
    snapshot_count = daemon_client.snapshot.await_count

    result = await manager.status()

    assert result.phase == DevicePhase.ERROR
    assert result.error is not None
    assert result.error.code == "daemon_stop_failed"
    assert result.daemon_owned is True
    assert result.daemon_pid == child.pid
    assert daemon_client.snapshot.await_count == snapshot_count + 1


@async_test
async def test_concurrent_live_snapshots_cannot_restore_an_older_motor_mode():
    manager, _, daemon_client, _ = make_manager()
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)
    first_snapshot_started = asyncio.Event()
    release_first_snapshot = asyncio.Event()
    snapshot_calls = 0

    async def changing_snapshot() -> dict[str, object]:
        nonlocal snapshot_calls
        snapshot_calls += 1
        if snapshot_calls == 1:
            first_snapshot_started.set()
            await release_first_snapshot.wait()
            motor_mode = "disabled"
        else:
            motor_mode = "enabled"
        return daemon_snapshot(motor_mode=motor_mode)

    daemon_client.snapshot.side_effect = changing_snapshot
    first_status = asyncio.create_task(manager.status())
    await asyncio.sleep(0)
    assert first_snapshot_started.is_set()
    second_status = asyncio.create_task(manager.status())
    await asyncio.sleep(0)
    release_first_snapshot.set()

    first_result, second_result = await asyncio.gather(first_status, second_status)
    assert first_result.motor_mode == "disabled"
    assert second_result.motor_mode == "enabled"

    daemon_client.snapshot.side_effect = ConnectionError("daemon snapshot unavailable")
    failed_refresh = await manager.status()
    assert failed_refresh.motor_mode == "enabled"


@async_test
async def test_aclose_stops_before_closing_daemon_client():
    events: list[str] = []
    manager, _, daemon_client, _ = make_manager()

    async def stop() -> DeviceStatus:
        events.append("stop")
        return DeviceStatus()

    async def close_client() -> None:
        events.append("close_client")

    manager.stop = AsyncMock(side_effect=stop)
    daemon_client.aclose.side_effect = close_client

    await manager.aclose()

    assert events == ["stop", "close_client"]


@async_test
async def test_aclose_closes_client_and_redacts_log_when_stop_fails():
    manager, _, daemon_client, _ = make_manager()
    manager.stop = AsyncMock(side_effect=RuntimeError("password=top-secret"))

    with pytest.raises(RuntimeError, match="Host Bridge cleanup failed") as raised:
        await manager.aclose()

    daemon_client.aclose.assert_awaited_once_with()
    logs = manager.logs_after(0)
    assert "top-secret" not in str(logs)
    assert "[REDACTED]" in str(logs)
    assert "top-secret" not in str(raised.value)


@async_test
async def test_aclose_closes_client_before_propagating_stop_cancellation():
    manager, _, daemon_client, _ = make_manager()
    manager.stop = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await manager.aclose()

    daemon_client.aclose.assert_awaited_once_with()


@async_test
async def test_aclose_reports_redacted_daemon_client_close_failure():
    manager, _, daemon_client, _ = make_manager()
    manager.stop = AsyncMock(return_value=DeviceStatus())
    daemon_client.aclose.side_effect = RuntimeError("token=top-secret")

    with pytest.raises(RuntimeError, match="Host Bridge cleanup failed") as raised:
        await manager.aclose()

    logs = manager.logs_after(0)
    assert "top-secret" not in str(logs)
    assert "[REDACTED]" in str(logs)
    assert "top-secret" not in str(raised.value)


@async_test
async def test_aclose_cancellation_during_sleep_finishes_owned_process_cleanup():
    events: list[str] = []
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()
    child = FakeProcess(events=events)
    manager, _, daemon_client, _ = make_manager(process=child)
    await manager.start(StartRequest())
    await wait_for_phase(manager, DevicePhase.READY)

    async def blocked_sleep(action: DeviceAction) -> dict[str, str]:
        assert action is DeviceAction.GOTO_SLEEP
        events.append("sleep")
        sleep_started.set()
        await release_sleep.wait()
        return {"uuid": "00000000-0000-0000-0000-000000000001"}

    async def close_client() -> None:
        events.append("close_client")

    daemon_client.perform.side_effect = blocked_sleep
    daemon_client.aclose.side_effect = close_client
    shutdown = asyncio.create_task(manager.aclose())
    await sleep_started.wait()

    shutdown.cancel()
    await asyncio.sleep(0)
    release_sleep.set()

    with pytest.raises(asyncio.CancelledError):
        await shutdown

    assert events == ["sleep", "terminate", "close_client"]
    assert child.terminate_calls == 1
    assert child.wait_calls == 1
    assert child.returncode == 0
    assert manager._process is None
    assert manager._owned_pid is None
    assert manager._status.daemon_owned is False
    daemon_client.aclose.assert_awaited_once_with()


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
    status_calls = 0

    async def delayed_status() -> dict[str, str]:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 1:
            raise ConnectionError("daemon offline")
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


@async_test
async def test_stale_external_status_response_cannot_overwrite_new_owned_start():
    stale_probe_started = asyncio.Event()
    release_stale_probe = asyncio.Event()
    connecting = asyncio.Event()
    never_ready = asyncio.Event()
    status_calls = 0
    daemon_client = daemon_client_ready()

    async def race_status() -> dict[str, str]:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 1:
            stale_probe_started.set()
            await release_stale_probe.wait()
            return {"state": "running", "version": "external"}
        if status_calls == 2:
            raise ConnectionError("no external daemon")
        connecting.set()
        await never_ready.wait()
        return {"state": "running", "version": "owned"}

    daemon_client.status.side_effect = race_status
    manager, _, _, child = make_manager(daemon_client=daemon_client)

    stale_status_task = asyncio.create_task(manager.status())
    await stale_probe_started.wait()
    started = await manager.start(StartRequest())
    await connecting.wait()
    release_stale_probe.set()
    raced_status = await stale_status_task

    assert raced_status.operation_id == started.operation_id
    assert raced_status.phase == DevicePhase.CONNECTING
    assert raced_status.daemon_owned is True
    assert raced_status.daemon_pid == child.pid
    assert raced_status.daemon_version != "external"
    await manager.stop()


@async_test
async def test_clawbody_health_probe_has_five_second_wall_clock_deadline():
    manager, _, _, _ = make_manager()
    manager._clawbody_health_url = "http://127.0.0.1:7860/health"
    observed_timeouts: list[float] = []

    class FakeHealthClient:
        async def __aenter__(self):
            raise AssertionError("health client context was entered outside the wall-clock deadline")

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str):
            return Mock(is_success=True)

    async def expire_request(awaitable, *, timeout: float):
        observed_timeouts.append(timeout)
        awaitable.close()
        raise TimeoutError("wall-clock deadline")

    with (
        patch("reachy_mini_openclaw.host_bridge.manager.httpx.AsyncClient", return_value=FakeHealthClient()),
        patch("reachy_mini_openclaw.host_bridge.manager.asyncio.wait_for", side_effect=expire_request),
    ):
        reachable = await manager._probe_clawbody_health()

    assert reachable is False
    assert observed_timeouts == [5.0]


@pytest.mark.parametrize(
    ("health_url", "expected_trust_env"),
    [
        ("http://127.0.0.1:7860/health", False),
        ("http://localhost:7860/health", False),
        ("http://[::1]:7860/health", False),
        ("https://clawbody.example.com/health", True),
    ],
)
def test_clawbody_health_probe_bypasses_proxy_only_for_local_hosts(
    health_url: str,
    expected_trust_env: bool,
):
    async def run() -> None:
        manager, _, _, _ = make_manager()
        manager._clawbody_health_url = health_url

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = Mock(is_success=True)

        with patch("reachy_mini_openclaw.host_bridge.manager.httpx.AsyncClient", return_value=client) as client_factory:
            assert await manager._probe_clawbody_health() is True

        client_factory.assert_called_once_with(timeout=5.0, trust_env=expected_trust_env)
        client.get.assert_awaited_once_with(health_url)

    asyncio.run(run())
