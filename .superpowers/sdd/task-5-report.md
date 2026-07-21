# Task 5: Windows login autostart management

## Scope and files

- `src/reachy_mini_openclaw/host_bridge/autostart.py`
- `tests/test_host_bridge_autostart.py`

The implementation manages only the exact Task Scheduler name `PsyTwin ClawBody Host Bridge`.

## Evidence

- RED: `python -m pytest tests/test_host_bridge_autostart.py -q` failed at collection because `autostart` did not exist.
- GREEN: the same focused test command passed: `6 passed`.
- Host Bridge suite: `95 passed`.
- Full repository test suite: `108 passed`.
- Ruff: `ruff check src/reachy_mini_openclaw/host_bridge/autostart.py tests/test_host_bridge_autostart.py` passed.
- `git diff --check` passed.

## Safety self-review

- Every `schtasks.exe` command has a hard-coded task name; no CLI input can choose a task, executable, command, module, or arguments.
- XML uses a `LogonTrigger` for the current SID, `LeastPrivilege`, `Hidden=true`, the `pythonw.exe` adjacent to `sys.executable`, fixed `-m reachy_mini_openclaw.host_bridge.api` arguments, and the repository-root working directory captured at install time.
- Commands are passed as argument lists with `shell=False`; XML encoding handles paths without shell quoting.
- Install uses `/F` to update the one fixed task idempotently. Restart executes `/End` then `/Run`, and uninstall requires `--yes` before the one exact `/Delete` command.
- Scheduler output is not echoed when a command fails, preventing accidental output disclosure.

## Commit

`feat: add Host Bridge login task management` (the commit that includes this report)
