"""Authenticated localhost-only API for the Reachy Mini Host Bridge."""

from __future__ import annotations

import hmac
import os
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, TypeVar

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .daemon_client import DaemonRequestError, ReachyDaemonClient
from .log_store import REDACTIONS
from .manager import DaemonManager
from .models import (
    ActionRequest,
    DeviceStatus,
    PoseRequest,
    SerialDevice,
    StartRequest,
    VolumeRequest,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7861
PLACEHOLDER_API_KEY = "replace-with-a-long-random-value"
T = TypeVar("T")


class _StrictStartRequest(StartRequest):
    model_config = ConfigDict(extra="forbid")


class _StrictActionRequest(ActionRequest):
    model_config = ConfigDict(extra="forbid")


class _StrictPoseRequest(PoseRequest):
    model_config = ConfigDict(extra="forbid")


class _StrictVolumeRequest(VolumeRequest):
    model_config = ConfigDict(extra="forbid")


class _EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _api_key() -> str:
    return os.getenv("HOST_BRIDGE_API_KEY", "").strip()


def _load_working_directory_env() -> None:
    """Load the login task working directory's .env without overriding real environment values."""
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)


def _validate_api_key_configuration() -> None:
    if _api_key() in {"", PLACEHOLDER_API_KEY}:
        raise RuntimeError("HOST_BRIDGE_API_KEY must be set to a long random value")


def _require_api_key(
    provided_key: Annotated[str | None, Header(alias="X-Host-Bridge-Key")] = None,
) -> None:
    expected_key = _api_key()
    matches = hmac.compare_digest(
        (provided_key or "").encode(),
        expected_key.encode(),
    )
    if not matches or expected_key in {"", PLACEHOLDER_API_KEY}:
        raise HTTPException(status_code=401, detail="invalid host bridge key")


def _operation_error(error: Exception) -> HTTPException:
    if isinstance(error, DaemonRequestError):
        return HTTPException(status_code=502, detail="Reachy daemon request failed")
    if isinstance(error, (httpx.HTTPError, TimeoutError)):
        return HTTPException(status_code=503, detail="Reachy daemon is unavailable")
    return HTTPException(status_code=500, detail="Host Bridge operation failed")


async def _run_operation(operation: Awaitable[T]) -> T:
    try:
        return await operation
    except Exception as error:
        raise _operation_error(error) from error


def _external_status(status: DeviceStatus) -> DeviceStatus:
    result = status.model_copy(deep=True)
    if result.error is not None and result.error.detail is not None:
        detail = result.error.detail
        for pattern in REDACTIONS:
            detail = pattern.sub(r"\1[REDACTED]", detail)
        result.error.detail = detail
    return result


async def _run_status_operation(operation: Awaitable[DeviceStatus]) -> DeviceStatus:
    return _external_status(await _run_operation(operation))


def create_app(manager: DaemonManager) -> FastAPI:
    """Create the fixed Host Bridge route surface for a manager instance."""

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        _validate_api_key_configuration()
        try:
            yield
        finally:
            try:
                await manager.aclose()
            except Exception:
                raise RuntimeError("Host Bridge shutdown cleanup failed") from None

    application = FastAPI(
        title="PsyTwin ClawBody Host Bridge",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    router = APIRouter(prefix="/v1/device", dependencies=[Depends(_require_api_key)])

    @application.exception_handler(DaemonRequestError)
    async def daemon_request_error(_request: Request, _error: DaemonRequestError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": "Reachy daemon request failed"})

    @application.exception_handler(httpx.HTTPError)
    async def daemon_transport_error(_request: Request, _error: httpx.HTTPError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Reachy daemon is unavailable"})

    @application.exception_handler(Exception)
    async def unexpected_error(_request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "Host Bridge operation failed"})

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/discover", response_model=list[SerialDevice])
    async def discover() -> list[SerialDevice]:
        return await _run_operation(manager.discover())

    @router.get("/status", response_model=DeviceStatus)
    async def status() -> DeviceStatus:
        return await _run_status_operation(manager.status())

    @router.post("/start", response_model=DeviceStatus)
    async def start(request: _StrictStartRequest) -> DeviceStatus:
        return await _run_status_operation(manager.start(request))

    @router.post("/stop", response_model=DeviceStatus)
    async def stop(
        _request: Annotated[_EmptyRequest | None, Body()] = None,
    ) -> DeviceStatus:
        return await _run_status_operation(manager.stop())

    @router.post("/restart", response_model=DeviceStatus)
    async def restart(request: _StrictStartRequest) -> DeviceStatus:
        return await _run_status_operation(manager.restart(request))

    @router.post("/action", response_model=DeviceStatus)
    async def action(request: _StrictActionRequest) -> DeviceStatus:
        return await _run_status_operation(manager.perform(request.action))

    @router.post("/pose", response_model=DeviceStatus)
    async def pose(request: _StrictPoseRequest) -> DeviceStatus:
        return await _run_status_operation(manager.set_pose(request))

    @router.post("/volume", response_model=DeviceStatus)
    async def volume(request: _StrictVolumeRequest) -> DeviceStatus:
        return await _run_status_operation(manager.set_volume(request))

    @router.get("/logs")
    async def logs(after: Annotated[int, Query(ge=0)] = 0) -> dict[str, int | list[dict[str, object]]]:
        try:
            return manager.logs_after(after)
        except Exception as error:
            raise _operation_error(error) from error

    application.include_router(router)
    return application


def _default_manager() -> DaemonManager:
    daemon_client = ReachyDaemonClient(
        base_url=os.getenv("HOST_BRIDGE_DAEMON_URL", "http://127.0.0.1:8000"),
    )
    return DaemonManager(
        daemon_client=daemon_client,
        clawbody_health_url=os.getenv(
            "HOST_BRIDGE_CLAWBODY_HEALTH_URL",
            "http://127.0.0.1:7860/health",
        ),
    )


app = create_app(_default_manager())


def main() -> None:
    """Run the Host Bridge on its loopback-only interface."""
    _load_working_directory_env()
    _validate_api_key_configuration()
    host = os.getenv("HOST_BRIDGE_HOST", DEFAULT_HOST).strip()
    if host != DEFAULT_HOST:
        raise RuntimeError("HOST_BRIDGE_HOST must be 127.0.0.1")
    try:
        port = int(os.getenv("HOST_BRIDGE_PORT", str(DEFAULT_PORT)))
    except ValueError as error:
        raise RuntimeError("HOST_BRIDGE_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("HOST_BRIDGE_PORT must be between 1 and 65535")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
