# Task 3 — USB discovery and Reachy daemon lifecycle manager

## Scope

Implemented only Task 3: Windows Reachy Mini Lite USB discovery, a single-owned-process
lifecycle state machine, typed daemon delegation, bounded health probing, and redacted
stdout collection. The manager builds the daemon command internally, never accepts an
executable path, never performs broad process discovery or killing, and does not access
an application catalog.

## TDD evidence

- **Initial RED:** `python -m pytest tests/test_host_bridge_manager.py -q` failed at
  collection with `ModuleNotFoundError` for
  `reachy_mini_openclaw.host_bridge.manager`.
- **Initial GREEN:** after the minimal manager implementation and adapting tests to the
  repository's `asyncio.run` pattern (the environment lacks `pytest-asyncio`), the focused
  suite passed: `10 passed`.
- **Race RED/GREEN:** a child-exit-during-startup regression test failed because the
  startup error overwrote `daemon_exited`; process identity checks at each awaited phase
  made the regression and focused suite pass.
- **Status RED/GREEN:** an exited owned PID remained `READY`; status-side reconciliation
  now reports `ERROR/daemon_exited` and clears ownership.
- **External ownership RED/GREEN:** starting after detecting a running external daemon
  spawned a competing child; start now reuses that status without spawning or claiming
  ownership.
- Final focused result: `13 passed in 0.35s`.

## Files

- `src/reachy_mini_openclaw/host_bridge/manager.py`
- `tests/test_host_bridge_manager.py`

## Verification

- `python -m pytest tests/test_host_bridge_models.py tests/test_host_bridge_daemon_client.py tests/test_host_bridge_manager.py -q` — `28 passed in 0.39s`
- `python -m pytest tests -q` — `41 passed in 1.54s`
- `python -m ruff check src/reachy_mini_openclaw/host_bridge tests/test_host_bridge_models.py tests/test_host_bridge_daemon_client.py tests/test_host_bridge_manager.py` — passed
- `git diff --cached --check` — passed before commit
- `mypy` was not run because this virtual environment does not have the `mypy` module installed.

## Commit

`68fa17a feat: manage the Reachy daemon lifecycle`

## Self-review

- Discovery calls `find_serial_port(wireless_version=False, vid="1a86", pid="55d3")` and
  accepts a requested COM port only when it exactly matches current discovery.
- One `asyncio.Lock` and one operation task make concurrent starts idempotent; phase
  transitions are covered through `STARTING`, `CONNECTING`, `HEALTHCHECKING`,
  `LOADING_APPS`, and `READY`.
- Only the recorded process object with its matching recorded PID can receive
  `terminate()` or `kill()`; an external daemon returns `daemon_not_owned` on stop.
- Stop requests the fixed sleep action, uses bounded waits, and escalates to `kill()` only
  for that same recorded process after termination times out.
- Stdout severity mapping feeds the existing redacting `LogStore`; unexpected exits are
  reconciled both from the reader thread and status polling.
- The ClawBody health probe is bounded to five seconds and remains non-fatal to hardware
  readiness.

## Review follow-up — `0f5f8e9`

### RED/GREEN evidence

- **Direct external reuse:** RED showed `start()` spawned a child unless `status()` had
  already populated the cache. GREEN probes the daemon inside the serialized fresh-start
  path and reuses a running external daemon without calling the process factory.
- **External reconciliation:** RED preserved stale `READY/running` after unreachable and
  stopped responses. GREEN transitions an unowned external daemon to truthful `OFFLINE`,
  clears stale metadata, and permits a later owned start.
- **Startup cancellation:** RED left the connecting child owned and unterminated. GREEN
  shields recorded-process cleanup, clears confirmed ownership, and reports
  `startup_cancelled`; failed cleanup retains ownership with `startup_cancel_failed`.
- **Stop failures:** RED allowed terminate, wait, and kill exceptions to escape. GREEN
  returns `ERROR/daemon_stop_failed` and retains the recorded PID whenever exit cannot be
  confirmed; no process search or broad kill is used.
- **Health deadline:** RED proved async client context setup was outside the bound. GREEN
  wraps the entire client/request coroutine in an asyncio five-second wall-clock deadline;
  timeout remains nonfatal.
- Added exact assertions for `find_serial_port(wireless_version=False, vid="1a86",
  pid="55d3")` and `command[0] == sys.executable`.

### Verification

- `python -m pytest tests/test_host_bridge_manager.py -q` — `23 passed in 0.37s`
- `python -m pytest tests/test_host_bridge_models.py tests/test_host_bridge_daemon_client.py tests/test_host_bridge_manager.py -q` — `38 passed in 0.42s`
- `python -m pytest tests -q` — `51 passed in 1.43s`
- Ruff over Host Bridge source and tests — passed
- `git diff --cached --check` — passed before commit

### Commit

`0f5f8e9 fix: harden Reachy daemon lifecycle ownership`

## Second review follow-up — `1b2ca8d`

### RED/GREEN evidence

- **Reachable external states:** RED showed an external daemon reporting `starting`
  still caused `Popen`. GREEN treats every successful daemon status response as proof
  of an existing daemon, waits on that daemon, and never creates an owned child.
- **Immediate operation receipt:** RED timed out while `start()` awaited its status probe.
  GREEN creates one serialized background operation and immediately returns a non-null
  operation ID for both external-reuse and owned-start paths.
- **Stop ordering:** RED recorded `terminate` without a sleep request during connecting.
  GREEN distinguishes stop-triggered cancellation from independent cancellation and
  records the required `GOTO_SLEEP` then `terminate` ordering.
- **Startup cleanup failure:** RED leaked `PermissionError` from readiness-failure cleanup.
  GREEN contains terminate/kill/wait errors, preserves the live recorded PID, and reports
  the readiness and cleanup failures together in diagnostic `ERROR` state.
- **Status race:** RED allowed a stale external status response to replace a newer owned
  operation's `CONNECTING` phase with `READY`. GREEN snapshots and revalidates operation,
  process, PID, and phase before applying an async status result.

### Verification

- `python -m pytest tests/test_host_bridge_manager.py -q` — `29 passed in 0.35s`
- `python -m pytest tests/test_host_bridge_models.py tests/test_host_bridge_daemon_client.py tests/test_host_bridge_manager.py -q` — `44 passed in 0.45s`
- `python -m pytest tests -q` — `57 passed in 1.54s`
- Ruff over Host Bridge source and tests — passed
- `git diff --cached --check` — passed before commit

### Commit

`1b2ca8d fix: serialize Reachy daemon startup state`

## Final review follow-up — `3cfb31e`

### RED/GREEN evidence

- **RED:** while an existing external daemon reported `starting` and the background
  operation waited for readiness, `stop()` canceled that task and returned `OFFLINE`.
- **GREEN:** the manager records the active external-reuse operation ID. During that
  operation, `stop()` returns `ERROR/daemon_not_owned` with the same operation ID,
  does not cancel readiness, does not request sleep, and never signals a process.
- The external readiness operation remains live and can transition to `READY`; its
  tracking marker is cleared in the operation's `finally` block.

### Verification

- `python -m pytest tests/test_host_bridge_manager.py -q` — `30 passed in 0.32s`
- `python -m pytest tests/test_host_bridge_models.py tests/test_host_bridge_daemon_client.py tests/test_host_bridge_manager.py -q` — `45 passed in 0.41s`
- `python -m pytest tests -q` — `58 passed in 1.45s`
- Ruff over Host Bridge source and tests — passed
- `git diff --cached --check` — passed before commit

### Commit

`3cfb31e fix: protect active external daemon reuse`

## Classification follow-up — `1942c89`

### RED/GREEN evidence

- **RED:** rejecting `stop()` during active external readiness called `_set_error`,
  mutating the background phase from `HEALTHCHECKING` to `ERROR`. A subsequent readiness
  exception was therefore misclassified as `daemon_start_failed`.
- **GREEN:** stop now returns a detached `ERROR/daemon_not_owned` status copy while the
  manager retains the operation's phase and empty error. The readiness task remains live,
  performs no sleep or process signal, and a later readiness exception is correctly
  reported as `daemon_healthcheck_failed`.

### Verification

- `python -m pytest tests/test_host_bridge_manager.py -q` — `31 passed in 0.30s`
- `python -m pytest tests/test_host_bridge_models.py tests/test_host_bridge_daemon_client.py tests/test_host_bridge_manager.py -q` — `46 passed in 0.44s`
- `python -m pytest tests -q` — `59 passed in 1.40s`
- Ruff over Host Bridge source and tests — passed
- `git diff --cached --check` — passed before commit

### Commit

`1942c89 fix: preserve external readiness classification`
