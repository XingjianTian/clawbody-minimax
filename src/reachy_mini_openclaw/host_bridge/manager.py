"""USB discovery and owned Reachy daemon lifecycle management."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable
from typing import Any, Protocol, cast
from uuid import uuid4

import httpx

from .daemon_client import ReachyDaemonClient
from .log_store import LogLevel, LogStore
from .models import (
    DeviceAction,
    DeviceError,
    DevicePhase,
    DeviceStatus,
    MediaStatus,
    PoseRequest,
    SerialDevice,
    StartRequest,
    VolumeRequest,
)

DAEMON_COMMAND = (
    "-m",
    "reachy_mini.daemon.app.main",
    "--serialport",
    "{serial_port}",
    "--localhost-only",
    "--log-level",
    "INFO",
)
ACTIVE_PHASES = {
    DevicePhase.STARTING,
    DevicePhase.CONNECTING,
    DevicePhase.HEALTHCHECKING,
    DevicePhase.LOADING_APPS,
    DevicePhase.STOPPING,
}


class ManagedProcess(Protocol):
    """The subprocess surface required by the lifecycle manager."""

    @property
    def pid(self) -> int: ...

    @property
    def stdout(self) -> Iterable[str] | None: ...

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


ProcessFactory = Callable[..., ManagedProcess]
PortDiscovery = Callable[[], Iterable[str] | str | None]


class _SerialPortFinder(Protocol):
    """Typed boundary for Reachy's serial-port helper."""

    def __call__(self, *, wireless_version: bool, vid: str, pid: str) -> Iterable[str] | str | None: ...


class _DaemonExitedError(RuntimeError):
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        super().__init__(f"Reachy daemon exited with code {returncode}")


class DaemonManager:
    """Own one Reachy daemon process and expose its typed lifecycle."""

    def __init__(
        self,
        discover_ports: PortDiscovery | None = None,
        process_factory: ProcessFactory | None = None,
        daemon_client: ReachyDaemonClient | None = None,
        logs: LogStore | None = None,
        clawbody_health_url: str = "http://127.0.0.1:7860/health",
    ) -> None:
        self._discover_ports = discover_ports or _default_discover_ports
        self._process_factory = process_factory or _default_process_factory
        self._daemon_client = daemon_client or ReachyDaemonClient()
        self._logs = logs or LogStore()
        self._clawbody_health_url = clawbody_health_url
        self._lock = asyncio.Lock()
        self._operation_task: asyncio.Task[None] | None = None
        self._stop_requested_operation_id: str | None = None
        self._external_operation_id: str | None = None
        self._process: ManagedProcess | None = None
        self._owned_pid: int | None = None
        self._status = DeviceStatus()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def discover(self) -> list[SerialDevice]:
        """Return USB serial ports matching the Reachy Mini Lite VID/PID."""
        ports = _normalize_ports(self._discover_ports())
        return [SerialDevice(port=port, label=f"Reachy Mini Lite ({port})") for port in ports]

    async def start(self, request: StartRequest) -> DeviceStatus:
        """Begin startup once and return its operation identifier immediately."""
        async with self._lock:
            if self._operation_task is not None and not self._operation_task.done():
                return self._copy_status()
            if self._owns_live_process():
                return self._copy_status()
            operation_id = str(uuid4())
            self._status = DeviceStatus(
                phase=DevicePhase.STARTING,
                operation_id=operation_id,
            )
            started_status = self._copy_status()
            self._loop = asyncio.get_running_loop()
            self._operation_task = asyncio.create_task(self._run_start(operation_id, request.serial_port))

        return started_status

    async def stop(self) -> DeviceStatus:
        """Stop only the child process whose PID this manager recorded."""
        operation_task: asyncio.Task[None] | None
        process: ManagedProcess | None
        owned_pid: int | None
        async with self._lock:
            operation_task = self._operation_task
            operation_active = operation_task is not None and not operation_task.done()
            if operation_active and self._external_operation_id == self._status.operation_id:
                rejected = self._copy_status()
                rejected.phase = DevicePhase.ERROR
                rejected.error = DeviceError(
                    code="daemon_not_owned",
                    phase=DevicePhase.STOPPING,
                    message="The running Reachy daemon is not owned by this Host Bridge.",
                )
                return rejected
            if operation_active:
                self._stop_requested_operation_id = self._status.operation_id
            process = self._process
            owned_pid = self._owned_pid
            if process is None or owned_pid is None:
                if operation_task is not None and not operation_task.done():
                    operation_task.cancel()
                    self._status.phase = DevicePhase.STOPPING
                else:
                    self._set_error(
                        DeviceError(
                            code="daemon_not_owned",
                            phase=DevicePhase.STOPPING,
                            message="The running Reachy daemon is not owned by this Host Bridge.",
                        )
                    )
                    return self._copy_status()
            elif process.pid != owned_pid:
                self._set_error(
                    DeviceError(
                        code="daemon_ownership_lost",
                        phase=DevicePhase.STOPPING,
                        message="The recorded daemon PID no longer matches the owned process.",
                    )
                )
                return self._copy_status()
            else:
                self._status.phase = DevicePhase.STOPPING
                self._status.error = None
                if operation_task is not None and not operation_task.done():
                    operation_task.cancel()

        if operation_task is not None and not operation_task.done():
            try:
                await operation_task
            except asyncio.CancelledError:
                pass

        if process is not None and owned_pid is not None and await self._still_owns(process, owned_pid):
            await self._request_sleep()
            try:
                await self._terminate_recorded_process(process, owned_pid)
            except Exception as error:
                self._logs.append("error", f"Owned Reachy daemon PID {owned_pid} could not be stopped: {error}")
                async with self._lock:
                    self._operation_task = None
                    self._stop_requested_operation_id = None
                    if self._process is process and self._owned_pid == owned_pid:
                        self._set_error(
                            DeviceError(
                                code="daemon_stop_failed",
                                phase=DevicePhase.STOPPING,
                                message="The owned Reachy daemon could not be stopped.",
                                detail=str(error),
                            )
                        )
                        return self._copy_status()

        async with self._lock:
            self._process = None
            self._owned_pid = None
            self._operation_task = None
            self._stop_requested_operation_id = None
            self._status = DeviceStatus(phase=DevicePhase.OFFLINE)
            return self._copy_status()

    async def aclose(self) -> None:
        """Stop owned process state and always close the daemon HTTP client."""
        cleanup_failed = False
        cancelled: asyncio.CancelledError | None = None
        status: DeviceStatus | None = None
        stop_task = asyncio.create_task(self.stop())
        while True:
            try:
                status = await asyncio.shield(stop_task)
                break
            except asyncio.CancelledError as error:
                cancelled = cancelled or error
                if not stop_task.done():
                    continue
                try:
                    status = stop_task.result()
                except asyncio.CancelledError as stop_error:
                    cancelled = cancelled or stop_error
                except Exception as stop_error:
                    cleanup_failed = True
                    self._logs.append("error", f"Host Bridge process cleanup failed: {stop_error}")
                break
            except Exception as error:
                cleanup_failed = True
                self._logs.append("error", f"Host Bridge process cleanup failed: {error}")
                break

        if status is not None and status.error is not None and status.error.code != "daemon_not_owned":
            cleanup_failed = True
            detail = status.error.detail or status.error.message
            self._logs.append("error", f"Host Bridge process cleanup failed: {detail}")

        close_task = asyncio.create_task(self._daemon_client.aclose())
        while True:
            try:
                await asyncio.shield(close_task)
                break
            except asyncio.CancelledError as error:
                cancelled = cancelled or error
                if not close_task.done():
                    continue
                try:
                    close_task.result()
                except asyncio.CancelledError as close_error:
                    cancelled = cancelled or close_error
                except Exception as close_error:
                    cleanup_failed = True
                    self._logs.append("error", f"Host Bridge daemon client cleanup failed: {close_error}")
                break
            except Exception as error:
                cleanup_failed = True
                self._logs.append("error", f"Host Bridge daemon client cleanup failed: {error}")
                break

        if cancelled is not None:
            raise cancelled
        if cleanup_failed:
            raise RuntimeError("Host Bridge cleanup failed; see redacted logs")

    async def restart(self, request: StartRequest) -> DeviceStatus:
        """Stop the owned daemon, then begin a new owned operation."""
        stopped = await self.stop()
        if stopped.error is not None:
            return stopped
        return await self.start(request)

    async def perform(self, action: DeviceAction) -> DeviceStatus:
        """Forward a predefined action to the local Reachy daemon."""
        await self._daemon_client.perform(action)
        return await self.status()

    async def set_pose(self, pose: PoseRequest) -> DeviceStatus:
        """Forward a validated pose to the local Reachy daemon."""
        await self._daemon_client.set_pose(pose)
        return await self.status()

    async def set_volume(self, request: VolumeRequest) -> DeviceStatus:
        """Forward a validated volume change to the local Reachy daemon."""
        await self._daemon_client.set_volume(request)
        return await self.status()

    async def status(self) -> DeviceStatus:
        """Return owned state, or detect an already-running external daemon."""
        async with self._lock:
            if self._process is not None and self._owned_pid is not None:
                returncode = self._process.poll()
                if returncode is not None:
                    self._record_process_exit(
                        self._owned_pid,
                        returncode,
                        expected=self._status.phase == DevicePhase.STOPPING,
                    )
                return self._copy_status()
            if self._status.phase in ACTIVE_PHASES:
                return self._copy_status()
            observed_operation_id = self._status.operation_id
            observed_process = self._process
            observed_pid = self._owned_pid
            observed_phase = self._status.phase

        try:
            daemon_status = await self._daemon_client.status()
        except Exception:
            async with self._lock:
                if not self._status_probe_is_current(
                    observed_operation_id,
                    observed_process,
                    observed_pid,
                    observed_phase,
                ):
                    return self._copy_status()
                if self._is_unowned_external_ready():
                    self._status = DeviceStatus(phase=DevicePhase.OFFLINE)
                return self._copy_status()

        async with self._lock:
            if not self._status_probe_is_current(
                observed_operation_id,
                observed_process,
                observed_pid,
                observed_phase,
            ):
                return self._copy_status()
            state = _string_value(daemon_status.get("state"))
            version = _string_value(daemon_status.get("version"))
            if state is not None:
                self._status.daemon_state = state
                self._status.daemon_version = version
                if state.lower() in {"running", "ready"}:
                    self._status.phase = DevicePhase.READY
                    self._status.error = None
                elif self._is_unowned_external_ready():
                    self._status = DeviceStatus(
                        phase=DevicePhase.OFFLINE,
                        daemon_state=state,
                        daemon_version=version,
                    )
            return self._copy_status()

    def logs_after(self, cursor: int) -> dict[str, int | list[dict[str, object]]]:
        """Return redacted manager logs after a monotonic cursor."""
        return self._logs.after(cursor)

    async def _run_start(self, operation_id: str, requested_port: str | None) -> None:
        process: ManagedProcess | None = None
        try:
            try:
                listening_status = await asyncio.wait_for(self._daemon_client.status(), timeout=1.0)
            except Exception:
                listening_status = None

            if listening_status is None:
                async with self._lock:
                    if self._status.operation_id != operation_id:
                        return
                    self._status.phase = DevicePhase.DISCOVERING
                devices = await self.discover()
                serial_port, discovery_error = self._select_port(devices, requested_port)
                if discovery_error is not None:
                    async with self._lock:
                        if self._status.operation_id == operation_id:
                            self._set_error(discovery_error)
                    return
                async with self._lock:
                    if self._status.operation_id != operation_id:
                        return
                    self._status.phase = DevicePhase.STARTING
                    self._status.serial_port = serial_port

                command = [sys.executable, *(part.format(serial_port=serial_port) for part in DAEMON_COMMAND)]
                started_process = self._process_factory(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=(
                        getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    ),
                )
                process = started_process
                async with self._lock:
                    if self._status.operation_id != operation_id:
                        return
                    self._process = started_process
                    self._owned_pid = started_process.pid
                    self._status.daemon_owned = True
                    self._status.daemon_pid = started_process.pid
                    self._status.phase = DevicePhase.CONNECTING
                self._logs.append("info", f"Started owned Reachy daemon PID {started_process.pid} on {serial_port}")
                self._start_output_thread(started_process)

                listening_status = await self._wait_for_daemon_listening(started_process, timeout=15.0)
            else:
                async with self._lock:
                    if self._status.operation_id != operation_id:
                        return
                    self._external_operation_id = operation_id
                    self._apply_daemon_status(listening_status)
                    self._status.phase = DevicePhase.CONNECTING

            async with self._lock:
                if self._status.operation_id != operation_id:
                    return
                if process is not None and not self._startup_process_is_live(process):
                    return
                self._apply_daemon_status(listening_status)
                self._status.phase = DevicePhase.HEALTHCHECKING

            ready_status = await self._daemon_client.wait_until_ready(timeout=45.0)
            async with self._lock:
                if self._status.operation_id != operation_id:
                    return
                if process is not None and not self._startup_process_is_live(process):
                    return
                self._apply_daemon_status(ready_status)
                self._status.phase = DevicePhase.LOADING_APPS

            snapshot = await self._daemon_client.snapshot()
            clawbody_reachable = await self._probe_clawbody_health()
            async with self._lock:
                if self._status.operation_id != operation_id:
                    return
                if process is not None and not self._startup_process_is_live(process):
                    return
                self._apply_snapshot(snapshot)
                self._status.clawbody_reachable = clawbody_reachable
                self._status.phase = DevicePhase.READY
                self._status.error = None
            self._logs.append("info", "Reachy daemon is ready")
        except asyncio.CancelledError:
            if self._stop_requested_operation_id == operation_id:
                raise
            cancellation_phase = self._status.phase
            cancellation_cleanup_error: Exception | None = None
            if process is not None and await self._still_owns(process, process.pid):
                try:
                    await asyncio.shield(self._terminate_recorded_process(process, process.pid))
                except Exception as error:
                    cancellation_cleanup_error = error
            async with self._lock:
                if process is not None and self._process is process and process.poll() is not None:
                    self._record_process_exit(process.pid, process.poll() or 0, expected=True)
                self._set_error(
                    DeviceError(
                        code=(
                            "startup_cancel_failed" if cancellation_cleanup_error is not None else "startup_cancelled"
                        ),
                        phase=cancellation_phase,
                        message=(
                            "Startup was cancelled but the owned daemon could not be stopped."
                            if cancellation_cleanup_error is not None
                            else "Reachy daemon startup was cancelled."
                        ),
                        detail=str(cancellation_cleanup_error) if cancellation_cleanup_error is not None else None,
                    )
                )
            raise
        except _DaemonExitedError as error:
            async with self._lock:
                if process is not None and self._process is process and self._owned_pid == process.pid:
                    self._record_process_exit(process.pid, error.returncode, expected=False)
        except Exception as startup_error:
            phase = self._status.phase
            self._logs.append("error", f"Reachy daemon startup failed during {phase.value}: {startup_error}")
            failure_cleanup_error: Exception | None = None
            if process is not None and await self._still_owns(process, process.pid):
                try:
                    await self._terminate_recorded_process(process, process.pid)
                except Exception as cleanup_exception:
                    failure_cleanup_error = cleanup_exception
                    self._logs.append(
                        "error",
                        "Owned Reachy daemon PID "
                        f"{process.pid} could not be cleaned up after startup failure: {cleanup_exception}",
                    )
            async with self._lock:
                if process is not None and self._process is process and process.poll() is not None:
                    self._record_process_exit(process.pid, process.poll() or 0, expected=True)
                detail = str(startup_error)
                if failure_cleanup_error is not None:
                    detail = f"{detail}; cleanup failed: {failure_cleanup_error}"
                self._set_error(
                    DeviceError(
                        code=_startup_error_code(phase),
                        phase=phase,
                        message="The Reachy daemon could not be started.",
                        detail=detail,
                    )
                )
        finally:
            async with self._lock:
                if self._external_operation_id == operation_id:
                    self._external_operation_id = None

    async def _wait_for_daemon_listening(
        self,
        process: ManagedProcess,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            returncode = process.poll()
            if returncode is not None:
                raise _DaemonExitedError(returncode)
            remaining = deadline - time.monotonic()
            try:
                daemon_status = await asyncio.wait_for(self._daemon_client.status(), timeout=min(1.0, remaining))
                returncode = process.poll()
                if returncode is not None:
                    raise _DaemonExitedError(returncode)
                return daemon_status
            except asyncio.CancelledError:
                raise
            except _DaemonExitedError:
                raise
            except Exception as error:
                last_error = error
                await asyncio.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
        message = "Reachy daemon did not begin listening within 15 seconds"
        if last_error is not None:
            raise TimeoutError(message) from last_error
        raise TimeoutError(message)

    async def _probe_clawbody_health(self) -> bool:
        if not self._clawbody_health_url:
            return False
        try:
            response = await asyncio.wait_for(self._request_clawbody_health(), timeout=5.0)
            return response.is_success
        except (httpx.HTTPError, TimeoutError) as error:
            self._logs.append("warning", f"ClawBody health probe failed: {error}")
            return False

    async def _request_clawbody_health(self) -> httpx.Response:
        async with httpx.AsyncClient(timeout=5.0) as client:
            return await client.get(self._clawbody_health_url)

    async def _request_sleep(self) -> None:
        try:
            await asyncio.wait_for(self._daemon_client.perform(DeviceAction.GOTO_SLEEP), timeout=3.0)
        except Exception as error:
            self._logs.append("warning", f"Reachy sleep request failed before daemon stop: {error}")

    async def _terminate_recorded_process(self, process: ManagedProcess, pid: int) -> None:
        if not await self._still_owns(process, pid):
            return
        if process.poll() is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(asyncio.to_thread(process.wait, 5.0), timeout=5.5)
        except (TimeoutError, subprocess.TimeoutExpired):
            if await self._still_owns(process, pid) and process.poll() is None:
                process.kill()
                try:
                    await asyncio.wait_for(asyncio.to_thread(process.wait, 1.0), timeout=1.5)
                except (TimeoutError, subprocess.TimeoutExpired) as error:
                    raise TimeoutError(f"Owned Reachy daemon PID {pid} did not exit after kill") from error

    async def _still_owns(self, process: ManagedProcess, pid: int) -> bool:
        async with self._lock:
            return self._process is process and self._owned_pid == pid and process.pid == pid

    def _start_output_thread(self, process: ManagedProcess) -> None:
        if process.stdout is None:
            return
        thread = threading.Thread(
            target=self._stream_process_output,
            args=(process.stdout,),
            kwargs={"process": process, "pid": process.pid},
            name=f"reachy-daemon-{process.pid}-logs",
            daemon=True,
        )
        thread.start()

    def _stream_process_output(
        self,
        lines: Iterable[str],
        *,
        process: ManagedProcess | None,
        pid: int | None,
    ) -> None:
        for line in lines:
            message = line.rstrip("\r\n")
            if not message:
                continue
            upper = message.upper()
            level: LogLevel = "error" if "ERROR" in upper else "warning" if "WARNING" in upper else "info"
            self._logs.append(level, message)

        if process is None or pid is None:
            return
        returncode = process.wait()
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._schedule_exit_reconciliation, process, pid, returncode)

    def _schedule_exit_reconciliation(self, process: ManagedProcess, pid: int, returncode: int) -> None:
        asyncio.create_task(self._reconcile_process_exit(process, pid, returncode))

    async def _reconcile_process_exit(self, process: ManagedProcess, pid: int, returncode: int) -> None:
        async with self._lock:
            if self._process is not process or self._owned_pid != pid:
                return
            was_stopping = self._status.phase == DevicePhase.STOPPING
            self._record_process_exit(pid, returncode, expected=was_stopping)

    def _select_port(
        self,
        devices: list[SerialDevice],
        requested_port: str | None,
    ) -> tuple[str, DeviceError | None]:
        ports = [device.port for device in devices]
        if requested_port is not None:
            if requested_port in ports:
                return requested_port, None
            return "", DeviceError(
                code="serial_port_not_found",
                phase=DevicePhase.DISCOVERING,
                message="The selected serial port is not a discovered Reachy Mini Lite.",
                detail=requested_port,
            )
        if not ports:
            return "", DeviceError(
                code="serial_port_not_found",
                phase=DevicePhase.DISCOVERING,
                message="No Reachy Mini Lite USB serial port was found.",
            )
        if len(ports) > 1:
            return "", DeviceError(
                code="multiple_serial_ports",
                phase=DevicePhase.DISCOVERING,
                message="Multiple Reachy Mini Lite ports were found; select one explicitly.",
                detail=", ".join(ports),
            )
        return ports[0], None

    def _owns_live_process(self) -> bool:
        return (
            self._process is not None
            and self._owned_pid is not None
            and self._process.pid == self._owned_pid
            and self._process.poll() is None
        )

    def _is_unowned_external_ready(self) -> bool:
        return not self._status.daemon_owned and self._status.phase == DevicePhase.READY

    def _status_probe_is_current(
        self,
        operation_id: str | None,
        process: ManagedProcess | None,
        pid: int | None,
        phase: DevicePhase,
    ) -> bool:
        return (
            self._status.operation_id == operation_id
            and self._process is process
            and self._owned_pid == pid
            and self._status.phase == phase
        )

    def _startup_process_is_live(self, process: ManagedProcess) -> bool:
        """Reconcile a child exit observed between startup await points."""
        if self._process is not process or self._owned_pid != process.pid:
            return False
        returncode = process.poll()
        if returncode is None:
            return True
        self._record_process_exit(process.pid, returncode, expected=False)
        return False

    def _record_process_exit(self, pid: int, returncode: int, *, expected: bool) -> None:
        self._process = None
        self._owned_pid = None
        self._status.daemon_owned = False
        self._status.daemon_pid = None
        if not expected:
            self._set_error(
                DeviceError(
                    code="daemon_exited",
                    phase=self._status.phase,
                    message="The owned Reachy daemon exited unexpectedly.",
                    detail=f"PID {pid} exited with code {returncode}",
                )
            )

    def _apply_daemon_status(self, daemon_status: dict[str, Any]) -> None:
        self._status.daemon_state = _string_value(daemon_status.get("state"))
        self._status.daemon_version = _string_value(daemon_status.get("version"))

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        daemon_status = snapshot.get("daemon_status")
        if isinstance(daemon_status, dict):
            self._apply_daemon_status(daemon_status)
        self._status.motor_mode = _string_value(snapshot.get("motor_mode"))
        media = snapshot.get("media")
        if isinstance(media, MediaStatus):
            self._status.media = media.model_copy(deep=True)

    def _set_error(self, error: DeviceError) -> None:
        self._status.phase = DevicePhase.ERROR
        self._status.error = error
        self._status.daemon_owned = self._process is not None and self._owned_pid is not None
        self._status.daemon_pid = self._owned_pid

    def _copy_status(self) -> DeviceStatus:
        return self._status.model_copy(deep=True)


def _default_discover_ports() -> Iterable[str] | str | None:
    from reachy_mini.daemon.utils import find_serial_port

    typed_find_serial_port = cast(_SerialPortFinder, find_serial_port)
    return typed_find_serial_port(wireless_version=False, vid="1a86", pid="55d3")


def _default_process_factory(
    command: list[str],
    *,
    stdout: int,
    stderr: int,
    stdin: int,
    text: bool,
    encoding: str,
    errors: str,
    bufsize: int,
    creationflags: int,
) -> ManagedProcess:
    return subprocess.Popen(
        command,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        text=text,
        encoding=encoding,
        errors=errors,
        bufsize=bufsize,
        creationflags=creationflags,
    )


def _normalize_ports(value: Iterable[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(dict.fromkeys(value))


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _startup_error_code(phase: DevicePhase) -> str:
    return {
        DevicePhase.STARTING: "daemon_start_failed",
        DevicePhase.CONNECTING: "daemon_listen_timeout",
        DevicePhase.HEALTHCHECKING: "daemon_healthcheck_failed",
        DevicePhase.LOADING_APPS: "daemon_snapshot_failed",
    }.get(phase, "daemon_start_failed")
