# Owned daemon live-status refresh report

## Scope

- Fixed `DaemonManager.status()` so an alive Host Bridge-owned daemon is queried for a current snapshot instead of returning the startup cache.
- Reconciles the existing daemon state/version, motor mode, media availability, and input/output volume fields while retaining the manager-owned PID, serial port, operation ID, lifecycle errors, and logs.
- Serializes owned snapshot refreshes and revalidates operation/process/PID/phase after each await, so an older response cannot overwrite a newer motor mode or race an external-daemon/start/stop transition.
- A failed live query reports `ERROR/daemon_status_failed` while retaining truthful ownership. A later successful refresh clears only that transient error; unrelated lifecycle errors remain intact.
- `perform`, `set_pose`, and `set_volume` keep their existing acceptance semantics, but their returned status is now live. No new public model fields or control guards were added.
- No hardware, daemon, scheduled task, external process, or remote branch was mutated.

## TDD evidence

- RED: eight focused regressions failed against the cached implementation for sleep/disabled, wake/enabled, current pose/volume/media state, live-query failure ownership, transient recovery, unrelated error preservation, and concurrent stale-response ordering.
- GREEN: `tests/test_host_bridge_manager.py` passed all 44 tests after the manager-only implementation.
- Full Host Bridge suite: 109 passed.
- Full project suite: 122 passed.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests -q` — 122 passed.
- `.\.venv\Scripts\python.exe -m mypy src/reachy_mini_openclaw/host_bridge` — success, 7 source files.
- Scoped Host Bridge `ruff check` — passed.
- `ruff format --check` for the two changed files — passed.
- `git diff --check` — passed before commit.
- Repository-wide mypy remains blocked by 27 pre-existing errors in 10 non-Host-Bridge files.
- Repository-wide Ruff remains blocked by 479 pre-existing findings outside this change.

## Commit

`a082a41 fix: refresh owned daemon status`

## Use and configuration

No new configuration is required. After updating the branch, restart the existing Host Bridge process (`clawbody-host restart`, or restart a foreground `clawbody-host-bridge` instance). Sentinel's normal status polling and action responses will then observe current motor/media state; a sleep response reports disabled motors and a wake response reports enabled motors when the daemon snapshot does.
