from pathlib import Path

from reachy_mini_openclaw.identity import (
    MAX_IDENTITY_BYTES,
    build_robot_system_instructions,
    load_robot_identity,
)

FALLBACK = "fallback identity"


def test_load_robot_identity_reads_utf8_markdown(tmp_path: Path) -> None:
    identity_file = tmp_path / "AGENTS.md"
    identity_file.write_text("# 身份\n\n名字：小瑞", encoding="utf-8")

    assert load_robot_identity(identity_file, FALLBACK) == "# 身份\n\n名字：小瑞"


def test_load_robot_identity_falls_back_for_missing_file(tmp_path: Path) -> None:
    assert load_robot_identity(tmp_path / "missing.md", FALLBACK) == FALLBACK


def test_load_robot_identity_falls_back_for_blank_file(tmp_path: Path) -> None:
    identity_file = tmp_path / "AGENTS.md"
    identity_file.write_text(" \n\t", encoding="utf-8")

    assert load_robot_identity(identity_file, FALLBACK) == FALLBACK


def test_load_robot_identity_falls_back_for_oversized_file(tmp_path: Path) -> None:
    identity_file = tmp_path / "AGENTS.md"
    identity_file.write_bytes(b"x" * (MAX_IDENTITY_BYTES + 1))

    assert load_robot_identity(identity_file, FALLBACK) == FALLBACK


def test_load_robot_identity_reads_changes_on_next_call(tmp_path: Path) -> None:
    identity_file = tmp_path / "AGENTS.md"
    identity_file.write_text("第一版身份", encoding="utf-8")
    assert load_robot_identity(identity_file, FALLBACK) == "第一版身份"

    identity_file.write_text("第二版身份", encoding="utf-8")
    assert load_robot_identity(identity_file, FALLBACK) == "第二版身份"


def test_system_instructions_hot_reload_identity(tmp_path: Path) -> None:
    identity_file = tmp_path / "AGENTS.md"
    identity_file.write_text("名字：小瑞\n语气：亲和自然", encoding="utf-8")

    first_prompt = build_robot_system_instructions(identity_file, FALLBACK, "身体规则")

    identity_file.write_text("名字：小星\n语气：清晰温暖", encoding="utf-8")
    second_prompt = build_robot_system_instructions(identity_file, FALLBACK, "身体规则")

    assert "名字：小瑞" in first_prompt
    assert "名字：小星" not in first_prompt
    assert "名字：小星" in second_prompt
    assert "名字：小瑞" not in second_prompt


def test_local_identity_precedes_supplemental_openclaw_context(tmp_path: Path) -> None:
    identity_file = tmp_path / "AGENTS.md"
    identity_file.write_text("本地身份设定", encoding="utf-8")

    prompt = build_robot_system_instructions(
        identity_file,
        FALLBACK,
        "身体规则",
        supplemental_context="OpenClaw 补充记忆",
    )

    assert prompt.index("本地身份设定") < prompt.index("OpenClaw 补充记忆")
