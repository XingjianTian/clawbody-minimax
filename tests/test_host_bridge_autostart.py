from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from xml.etree import ElementTree as ET

import pytest

from reachy_mini_openclaw.host_bridge import autostart


def _successful_run(
    calls: list[list[str]],
    xml_documents: list[str],
    options: list[dict[str, object]] | None = None,
):
    def run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        if options is not None:
            options.append(_kwargs)
        if "/XML" in command:
            xml_documents.append(Path(command[command.index("/XML") + 1]).read_text(encoding="utf-16"))
        return CompletedProcess(command, 0, "", "")

    return run


def test_install_creates_exact_current_user_logon_task(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[list[str]] = []
    xml_documents: list[str] = []
    options: list[dict[str, object]] = []
    executable = tmp_path / "PsyTwin Workspace" / ".venv" / "Scripts" / "python.exe"
    repository_root = tmp_path / "PsyTwin Workspace" / "clawbody-minimax"

    monkeypatch.setattr(autostart, "_current_user_sid", lambda: "S-1-5-21-101-202-303-1001")
    monkeypatch.setattr(autostart, "_pythonw_executable", lambda: executable.with_name("pythonw.exe"))
    monkeypatch.setattr(autostart, "_repository_root", lambda: repository_root)
    monkeypatch.setattr(autostart.subprocess, "run", _successful_run(calls, xml_documents, options))
    monkeypatch.setenv("HOST_BRIDGE_API_KEY", "must-not-appear-in-task-xml")

    assert autostart.main(["install"]) == 0
    assert calls and calls[0][:5] == [
        "schtasks.exe",
        "/Create",
        "/TN",
        "PsyTwin ClawBody Host Bridge",
        "/XML",
    ]
    assert calls[0][-1] == "/F"

    document = ET.fromstring(xml_documents[0])
    namespace = {"task": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert document.findtext("task:Triggers/task:LogonTrigger/task:UserId", namespaces=namespace) == "S-1-5-21-101-202-303-1001"
    assert document.findtext("task:Principals/task:Principal/task:RunLevel", namespaces=namespace) == "LeastPrivilege"
    assert document.findtext("task:Settings/task:Hidden", namespaces=namespace) == "true"
    assert document.findtext("task:Settings/task:AllowHardTerminate", namespaces=namespace) == "true"
    assert document.findtext("task:Actions/task:Exec/task:Command", namespaces=namespace) == str(
        executable.with_name("pythonw.exe")
    )
    assert document.findtext("task:Actions/task:Exec/task:Arguments", namespaces=namespace) == (
        "-m reachy_mini_openclaw.host_bridge.api"
    )
    assert document.findtext("task:Actions/task:Exec/task:WorkingDirectory", namespaces=namespace) == str(repository_root)
    assert "must-not-appear-in-task-xml" not in xml_documents[0]
    assert all("must-not-appear-in-task-xml" not in " ".join(call) for call in calls)
    assert options == [
        {
            "capture_output": True,
            "check": False,
            "encoding": "utf-8",
            "errors": "replace",
            "shell": False,
            "text": True,
        }
    ]


def test_status_queries_only_the_fixed_task(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(autostart.subprocess, "run", _successful_run(calls, []))

    assert autostart.main(["status"]) == 0
    assert calls == [
        [
            "schtasks.exe",
            "/Query",
            "/TN",
            "PsyTwin ClawBody Host Bridge",
            "/FO",
            "LIST",
            "/V",
        ]
    ]


def test_restart_ends_then_runs_only_the_fixed_task(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(autostart.subprocess, "run", _successful_run(calls, []))

    assert autostart.main(["restart"]) == 0
    assert calls == [
        ["schtasks.exe", "/End", "/TN", "PsyTwin ClawBody Host Bridge"],
        ["schtasks.exe", "/Run", "/TN", "PsyTwin ClawBody Host Bridge"],
    ]


def test_every_scheduler_operation_disables_the_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[list[str]] = []
    options: list[dict[str, object]] = []
    monkeypatch.setattr(autostart, "_current_user_sid", lambda: "S-1-5-21-101-202-303-1001")
    monkeypatch.setattr(autostart, "_pythonw_executable", lambda: tmp_path / "pythonw.exe")
    monkeypatch.setattr(autostart, "_repository_root", lambda: tmp_path)
    monkeypatch.setattr(autostart.subprocess, "run", _successful_run(calls, [], options))

    assert autostart.main(["install"]) == 0
    assert autostart.main(["status"]) == 0
    assert autostart.main(["restart"]) == 0
    assert autostart.main(["uninstall", "--yes"]) == 0
    assert len(calls) == 5
    assert all(option["shell"] is False for option in options)


def test_current_user_sid_lookup_disables_the_shell(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []
    options: list[dict[str, object]] = []

    def sid_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        options.append(kwargs)
        return CompletedProcess(command, 0, '"PsyTwin\\\\Operator","S-1-5-21-101-202-303-1001"\n', "")

    monkeypatch.setattr(autostart.subprocess, "run", sid_run)

    assert autostart._current_user_sid() == "S-1-5-21-101-202-303-1001"
    assert calls == [["whoami.exe", "/user", "/fo", "csv", "/nh"]]
    assert options[0]["shell"] is False


def test_uninstall_requires_yes_before_deleting(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    calls: list[list[str]] = []
    monkeypatch.setattr(autostart.subprocess, "run", _successful_run(calls, []))

    assert autostart.main(["uninstall"]) == 2
    assert calls == []
    assert "--yes" in capsys.readouterr().err


def test_uninstall_deletes_only_the_fixed_task(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(autostart.subprocess, "run", _successful_run(calls, []))

    assert autostart.main(["uninstall", "--yes"]) == 0
    assert calls == [["schtasks.exe", "/Delete", "/TN", "PsyTwin ClawBody Host Bridge", "/F"]]


def test_scheduler_failure_returns_error_without_echoing_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def failed_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, "password=should-not-leak", "token=should-not-leak")

    monkeypatch.setattr(autostart.subprocess, "run", failed_run)

    assert autostart.main(["status"]) == 1
    output = capsys.readouterr()
    assert "should-not-leak" not in output.out + output.err
