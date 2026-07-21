"""Manage the fixed current-user Host Bridge login task on Windows."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from subprocess import CompletedProcess
from xml.etree import ElementTree as ET

TASK_NAME = "PsyTwin ClawBody Host Bridge"
TASK_SCHEDULER = "schtasks.exe"
HOST_BRIDGE_MODULE = "reachy_mini_openclaw.host_bridge.api"
TASK_XML_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Host Bridge login task management is available only on Windows")


def _pythonw_executable() -> Path:
    """Derive pythonw.exe from the Python interpreter running this CLI."""
    return Path(sys.executable).resolve().with_name("pythonw.exe")


def _repository_root() -> Path:
    """Capture the repository root as the scheduled task's working directory."""
    root = Path.cwd().resolve()
    if not (root / "pyproject.toml").is_file():
        raise RuntimeError("Run 'clawbody-host install' from the repository root containing pyproject.toml")
    return root


def _current_user_sid() -> str:
    """Return the invoking Windows user's SID using the fixed whoami command."""
    result = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        shell=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Could not determine the current Windows user SID")

    rows = list(csv.reader(result.stdout.splitlines()))
    if len(rows) != 1 or len(rows[0]) != 2 or not rows[0][1].startswith("S-"):
        raise RuntimeError("Could not determine the current Windows user SID")
    return rows[0][1]


def _task_xml(*, user_sid: str, executable: Path, working_directory: Path) -> ET.Element:
    ET.register_namespace("", TASK_XML_NAMESPACE)
    task = ET.Element(f"{{{TASK_XML_NAMESPACE}}}Task", {"version": "1.4"})
    registration = ET.SubElement(task, f"{{{TASK_XML_NAMESPACE}}}RegistrationInfo")
    ET.SubElement(registration, f"{{{TASK_XML_NAMESPACE}}}Description").text = (
        "Starts the PsyTwin ClawBody Host Bridge at current-user login."
    )

    triggers = ET.SubElement(task, f"{{{TASK_XML_NAMESPACE}}}Triggers")
    logon_trigger = ET.SubElement(triggers, f"{{{TASK_XML_NAMESPACE}}}LogonTrigger")
    ET.SubElement(logon_trigger, f"{{{TASK_XML_NAMESPACE}}}UserId").text = user_sid
    ET.SubElement(logon_trigger, f"{{{TASK_XML_NAMESPACE}}}Enabled").text = "true"

    principals = ET.SubElement(task, f"{{{TASK_XML_NAMESPACE}}}Principals")
    principal = ET.SubElement(principals, f"{{{TASK_XML_NAMESPACE}}}Principal", {"id": "Author"})
    ET.SubElement(principal, f"{{{TASK_XML_NAMESPACE}}}UserId").text = user_sid
    ET.SubElement(principal, f"{{{TASK_XML_NAMESPACE}}}RunLevel").text = "LeastPrivilege"

    settings = ET.SubElement(task, f"{{{TASK_XML_NAMESPACE}}}Settings")
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}MultipleInstancesPolicy").text = "IgnoreNew"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}DisallowStartIfOnBatteries").text = "false"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}StopIfGoingOnBatteries").text = "false"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}AllowHardTerminate").text = "true"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}StartWhenAvailable").text = "true"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}Hidden").text = "true"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}Enabled").text = "true"
    ET.SubElement(settings, f"{{{TASK_XML_NAMESPACE}}}ExecutionTimeLimit").text = "PT0S"

    actions = ET.SubElement(task, f"{{{TASK_XML_NAMESPACE}}}Actions", {"Context": "Author"})
    execution = ET.SubElement(actions, f"{{{TASK_XML_NAMESPACE}}}Exec")
    ET.SubElement(execution, f"{{{TASK_XML_NAMESPACE}}}Command").text = str(executable)
    ET.SubElement(execution, f"{{{TASK_XML_NAMESPACE}}}Arguments").text = f"-m {HOST_BRIDGE_MODULE}"
    ET.SubElement(execution, f"{{{TASK_XML_NAMESPACE}}}WorkingDirectory").text = str(working_directory)
    return task


def _run_schtasks(arguments: Sequence[str]) -> CompletedProcess[str]:
    """Run only a fixed schtasks.exe invocation without exposing a shell."""
    return subprocess.run(
        [TASK_SCHEDULER, *arguments],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        shell=False,
        text=True,
    )


def _install() -> int:
    user_sid = _current_user_sid()
    executable = _pythonw_executable()
    working_directory = _repository_root()
    task = _task_xml(user_sid=user_sid, executable=executable, working_directory=working_directory)

    with tempfile.TemporaryDirectory(prefix="psytwin-host-bridge-") as temporary_directory:
        xml_path = Path(temporary_directory) / "host-bridge-login-task.xml"
        ET.ElementTree(task).write(xml_path, encoding="utf-16", xml_declaration=True)
        result = _run_schtasks(("/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"))

    if result.returncode != 0:
        print("Could not install the PsyTwin ClawBody Host Bridge login task.", file=sys.stderr)
        return 1
    print("PsyTwin ClawBody Host Bridge login task installed.")
    return 0


def _status() -> int:
    result = _run_schtasks(("/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"))
    if result.returncode != 0:
        print("PsyTwin ClawBody Host Bridge login task is not installed or is unavailable.", file=sys.stderr)
        return 1
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    return 0


def _restart() -> int:
    end_result = _run_schtasks(("/End", "/TN", TASK_NAME))
    run_result = _run_schtasks(("/Run", "/TN", TASK_NAME))
    if run_result.returncode != 0:
        print("Could not start the PsyTwin ClawBody Host Bridge login task.", file=sys.stderr)
        return 1
    if end_result.returncode != 0:
        print("Host Bridge task was not running; started it.")
    else:
        print("PsyTwin ClawBody Host Bridge login task restarted.")
    return 0


def _uninstall() -> int:
    result = _run_schtasks(("/Delete", "/TN", TASK_NAME, "/F"))
    if result.returncode != 0:
        print("Could not remove the PsyTwin ClawBody Host Bridge login task.", file=sys.stderr)
        return 1
    print("PsyTwin ClawBody Host Bridge login task removed.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the PsyTwin ClawBody Host Bridge login task.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("install", help="install or update the current-user login task")
    subcommands.add_parser("status", help="show the fixed login task status")
    subcommands.add_parser("restart", help="restart the fixed login task")
    uninstall = subcommands.add_parser("uninstall", help="remove the fixed login task")
    uninstall.add_argument("--yes", action="store_true", help="confirm removal of the fixed login task")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the fixed-task administration CLI and return its process status."""
    _require_windows()
    arguments = _parser().parse_args(argv)
    if arguments.command == "install":
        return _install()
    if arguments.command == "status":
        return _status()
    if arguments.command == "restart":
        return _restart()
    if not arguments.yes:
        print("Refusing to remove the login task without explicit --yes confirmation.", file=sys.stderr)
        return 2
    return _uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
