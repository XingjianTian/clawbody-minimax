# Host Bridge Task 4 Report

## Result

- Implemented the authenticated localhost-only FastAPI Host Bridge surface in `src/reachy_mini_openclaw/host_bridge/api.py`.
- Added the planned `clawbody-host-bridge` and `clawbody-host` entry points in `pyproject.toml`.
- Added API contract and security coverage in `tests/test_host_bridge_api.py`.
- Commit: `8969757 feat: expose the Reachy host bridge API`.
- No push was performed.

## TDD evidence

1. Initial RED: `python -m pytest tests/test_host_bridge_api.py -q` failed during collection because `reachy_mini_openclaw.host_bridge.api` did not exist.
2. Initial GREEN attempt: 28 tests passed and one failed because an arbitrary manager exception escaped Starlette's test transport; route-boundary error mapping was added.
3. GREEN: 29 API tests passed.
4. Security self-review reproduced a non-ASCII API-key header returning 500. A regression test was added first and observed failing with `TypeError` from string `hmac.compare_digest`.
5. Regression GREEN: comparison was changed to UTF-8 bytes; 30 API tests passed.

## Verification

- Focused API: `30 passed in 2.35s`.
- Host Bridge Tasks 1-4: `76 passed in 2.59s`.
- Full `tests/` suite: `89 passed in 3.53s`.
- Ruff: `All checks passed!` for the Host Bridge package and Host Bridge tests.
- `git diff --check`: exit 0.
- Optional mypy check was not available because mypy is not installed in `.venv`; Task 4 did not require it.

## Security and lifecycle review

- `/health` is public; every `/v1/device/*` route uses the same API-key dependency.
- Missing, invalid, and non-ASCII keys return the same 401 response; verification uses `hmac.compare_digest` on bytes.
- Empty and placeholder keys prevent application startup.
- `main()` accepts only `127.0.0.1` and validates the configured port range.
- HTTP request models reject unknown fields, including shell, command, executable-path, and path inputs.
- Only typed manager methods are exposed; no route accepts an executable or arbitrary command.
- Daemon, transport, timeout, and unexpected exceptions map to fixed redacted responses.
- Application shutdown delegates cleanup to `DaemonManager.aclose()`, which preserves Task 3's owned-PID safety rules and closes the daemon HTTP client.

## Usage and configuration

Set `HOST_BRIDGE_API_KEY` to a long random value, then run `clawbody-host-bridge`. Optional settings are `HOST_BRIDGE_HOST=127.0.0.1`, `HOST_BRIDGE_PORT=7861`, `HOST_BRIDGE_DAEMON_URL`, and `HOST_BRIDGE_CLAWBODY_HEALTH_URL`. Call protected routes with the `X-Host-Bridge-Key` header. The `clawbody-host` administration entry point is registered now and will become usable when Task 5 adds `autostart.py`.

## Review fixes

- Commit: `899222f fix: harden host bridge API cleanup`.
- API responses now deep-copy and redact `DeviceStatus.error.detail` for every status-returning route without mutating the manager's internal status.
- Added `DaemonManager.aclose()` to stop owned process state, always close the daemon HTTP client, log redacted cleanup failures, preserve cancellation, and raise only a generic cleanup error.
- FastAPI lifespan now calls the manager close operation and reports a generic failure instead of silently swallowing it.
- Added explicit missing/empty API-key and invalid/out-of-range port tests.

### Review-fix TDD evidence

1. Returned-status regression failed with `password=top-secret` instead of `password=[REDACTED]`, then passed after external-status copying/redaction.
2. Four lifecycle regressions failed because lifespan still called `stop()` and `DaemonManager.aclose()` did not exist, then passed after deterministic manager cleanup was added.
3. Cancellation regression failed because client close was never awaited after `CancelledError`, then passed after deferred cancellation propagation.
4. Configuration tests passed immediately because the required validation behavior already existed.

### Review-fix verification

- Focused API: `38 passed in 2.37s`.
- Host Bridge Tasks 1-4: `88 passed in 2.68s`.
- Full `tests/` suite: `101 passed in 3.61s`.
- Ruff: `All checks passed!`.
- `git diff --check`: exit 0.
- No push was performed.

## Final shutdown cancellation fix

- Commit: `5b0d665 fix: shield host bridge shutdown cleanup`.
- `DaemonManager.aclose()` now runs `stop()` in a separate task and awaits it through `asyncio.shield`, including after outer-task cancellation.
- Daemon HTTP client closure starts only after process cleanup finishes and is itself shielded; the original cancellation is re-raised after both cleanup phases.
- External daemon safety remains delegated to `stop()`, which never terminates an unowned PID.
- Added a real owned-process regression that cancels shutdown during `goto_sleep` and verifies sleep, terminate, wait, ownership clearing, client close ordering, and cancellation propagation.

### Final-fix TDD evidence

1. RED: cancellation during the blocked sleep produced only `sleep, close_client`; terminate/wait never ran and ownership remained.
2. GREEN: all five `aclose` tests passed after shielded stop/client tasks were introduced.

### Final-fix verification

- Manager and API: `74 passed in 2.61s`.
- Host Bridge Tasks 1-4: `89 passed in 2.61s`.
- Full `tests/` suite: `102 passed in 3.53s`.
- Ruff: `All checks passed!`.
- `git diff --check`: exit 0.
- No push was performed.
