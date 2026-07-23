# Task 6: Host Bridge configuration and operator documentation

## Scope

- Updated `.env.example` with the five non-secret Host Bridge settings.
- Added Windows installation, current-user login task operation, safe health/discovery checks, daily Sentinel workflow, Docker daemon routing, secret handling, offline device-start guarantees, and troubleshooting to `README.md` and `DOCKER_SETUP.md`.
- Did not modify backend code, dependency declarations, or entry points in this task.
- Did not create, run, restart, or uninstall a Windows scheduled task and did not start the Reachy hardware daemon.

## Exact configuration

```dotenv
HOST_BRIDGE_HOST=127.0.0.1
HOST_BRIDGE_PORT=7861
HOST_BRIDGE_API_KEY=replace-with-a-long-random-value
HOST_BRIDGE_DAEMON_URL=http://127.0.0.1:8000
HOST_BRIDGE_CLAWBODY_HEALTH_URL=http://127.0.0.1:7860/health
```

Replace `HOST_BRIDGE_API_KEY` with a long random value. Sentinel must use `HOST_BRIDGE_URL=http://127.0.0.1:7861` and the identical server-only `HOST_BRIDGE_API_KEY`. Never commit `.env`, place the key in `NEXT_PUBLIC_*`, a URL, browser code, an Issue, or chat.

## Exact install and operator usage

One-time Windows setup from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "reachy-mini==1.8.0"
python -m pip install -e ".[dev,mediapipe_vision]"
Copy-Item .env.example .env
clawbody-host install
clawbody-host status
clawbody-host restart
```

Administration commands and meanings:

```powershell
.\.venv\Scripts\Activate.ps1
clawbody-host install          # create/update the fixed current-user login task
clawbody-host status           # query the fixed task
clawbody-host restart          # end and run the fixed task
clawbody-host uninstall --yes  # remove only that task; use only when intentional
```

Daily operation: close Reachy Mini Control, start Docker, open Sentinel, select **心宠调试**, and click **启动设备**. The Host Bridge owns the daemon at `127.0.0.1:8000`; Docker reaches it at `host.docker.internal:8000`. Device startup needs no VPN and no Hugging Face, GitHub, OpenAI, or application-catalog request. Alibaba Cloud/Baidu conversation still needs normal network access.

## Verification evidence

- Focused Host Bridge tests: `101 passed in 5.45s`.
- Full `tests` suite: `114 passed in 6.50s`.
- Ruff Host Bridge/test scope: `All checks passed!`.
- Packaging/import verification: both `clawbody-host-bridge` and `clawbody-host` console entry points match `pyproject.toml` and import successfully.
- Installed runtime verification: `reachy-mini 1.8.0`, `pyserial 3.5`.
- Safe smoke: manually ran only the Host Bridge, `/health` returned `ok`, authenticated `/v1/device/discover` returned Reachy Mini Lite `COM5`, and no start/action endpoint was called. The smoke process stopped and port `7861` no longer listened afterward.
- `git diff --check`: exit 0.

## Remaining verification blocker

`.\.venv\Scripts\python.exe -m mypy src/reachy_mini_openclaw/host_bridge` exited 1 with 16 pre-existing errors outside Task 6's allowed file boundary:

- `daemon_client.py:109-111`: three `MediaStatus` literal argument type errors.
- `manager.py:144,168`: two optional `_operation_task.cancel()` narrowing errors.
- `manager.py:374,392,394,396,397,399`: process factory / optional managed-process type errors.
- `manager.py:465-466`: two optional process PID errors.
- `manager.py:470`: duplicate `cleanup_error` definition.
- `manager.py:596`: log level `str` versus literal type.
- `manager.py:721`: `Any` returned from a typed discovery function.

Per the Task 6 boundary, no backend source was changed to hide or repair these errors. A separate type-correction task is required before claiming the plan's mypy command passes.

## Documentation review follow-up

- Changed the early `DOCKER_SETUP.md` key-generation command to `py -3.11 -c ...`, so it no longer invokes `.venv` before the virtual environment creation section. Python 3.11 is already an explicit prerequisite. The current workstation's Python launcher does not have a separately registered 3.11 runtime, so this exact clean-machine command could not be executed locally; the existing `.venv` uses a different Python registration.
- Corrected `README.md` to state that Sentinel reaches the published ClawBody service at `http://127.0.0.1:7860`, while the container reaches the daemon at `host.docker.internal:8000`.
- Replaced the legacy audio instructions with Sentinel, Host Bridge, daemon media/volume endpoints, and ClawBody container logs; all instructions keep Reachy Mini Control closed.
- Verified both documented daemon endpoints exist in `daemon_client.py`, stale/conflicting phrases are absent from the edited locations, and `git diff --check -- README.md DOCKER_SETUP.md` exits 0.

## Physical USB diagnostics follow-up

- Replaced the README physical-robot instructions that started a desktop app or direct USB ClawBody process with a Host Bridge-only read-only diagnostic path.
- The documented commands now query only `clawbody-host status`, Host Bridge `/health`, authenticated `/v1/device/discover`, and daemon `/api/daemon/status`; none starts the daemon or moves the robot.
- The section directs all physical start/stop/control through Sentinel **心宠调试**, keeps Reachy Mini Control closed, and forbids a separate daemon alongside Host Bridge.
- Full modified-doc search found zero `Start the desktop app`, `app must be running`, `control software`, or `心宠控制软件` phrases. All 12 remaining `Reachy Mini Control` mentions in `README.md` and `DOCKER_SETUP.md` require it to be closed. `git diff --check -- README.md` exits 0.
