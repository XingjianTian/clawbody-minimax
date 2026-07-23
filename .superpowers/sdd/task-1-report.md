# Host Bridge Task 1 Report

## Scope

Implemented the Host Bridge device contracts and bounded redacted log storage.

## RED evidence

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_host_bridge_models.py -q
```

Result: expected collection failure, `ModuleNotFoundError: No module named
'reachy_mini_openclaw.host_bridge'`.

## GREEN evidence

The same focused command passed with `2 passed in 0.11s` after implementation.

## Verification

- `pytest tests/test_host_bridge_models.py -q`: 2 passed.
- `pytest tests -q`: 15 passed.
- `ruff check src/reachy_mini_openclaw/host_bridge tests/test_host_bridge_models.py`: passed.
- `git diff --check`: passed.
- `mypy src/reachy_mini_openclaw/host_bridge`: not run successfully because the local virtual environment does not have mypy installed (`No module named mypy`).

## Files

- `src/reachy_mini_openclaw/host_bridge/__init__.py`
- `src/reachy_mini_openclaw/host_bridge/models.py`
- `src/reachy_mini_openclaw/host_bridge/log_store.py`
- `tests/test_host_bridge_models.py`

## Self-review

- `DevicePhase` and `DeviceAction` use stable string enum values; public request, status, media, error, serial, and log contracts match the planned fields and constraints.
- `LogStore` uses a `deque` with a configurable bounded history, a lock, and monotonic entry IDs. It redacts credentials before the 2,000-character truncation limit and serializes entries for cursor-based reads.
- No unrelated tracked files were changed; the pre-existing untracked `.superpowers/` state is not staged.

## Commit

`2cb2522 feat: add Reachy host bridge contracts`

## Follow-up: returned log entry isolation

### RED evidence

Added `test_log_store_append_return_cannot_mutate_stored_entry`. Before the
fix, the focused test run failed with the stored entry changing from ID `1` and
message `original message` to ID `999` and message `changed message` after the
caller mutated the value returned by `append()`.

### GREEN evidence

`LogStore.append()` now retains its newly created entry internally and returns
`entry.model_copy()`, preserving the `LogEntry` return type without exposing
the mutable deque object.

### Verification

- `pytest tests/test_host_bridge_models.py -q`: 3 passed.
- `pytest tests -q`: 16 passed.
- `ruff check src/reachy_mini_openclaw/host_bridge tests/test_host_bridge_models.py`: passed.
- `git diff --check`: passed.

### Self-review

The returned entry has only primitive fields, so a shallow Pydantic model copy
is sufficient to prevent callers from mutating the internally retained log
entry. `after()` continues to return serialized dictionaries, which are also
not aliases of the deque entries.

### Follow-up commit

`cf3ce72 fix: isolate returned host bridge log entries`
