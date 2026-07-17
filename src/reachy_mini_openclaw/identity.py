"""Load the manually maintained robot identity prompt."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_IDENTITY_BYTES = 65_536


def load_robot_identity(path: str | Path, fallback: str) -> str:
    """Read a UTF-8 identity file, returning fallback when it is unusable."""
    identity_path = Path(path)

    try:
        file_size = identity_path.stat().st_size
        if file_size > MAX_IDENTITY_BYTES:
            logger.warning(
                "Robot identity file %s is too large (%d bytes); using fallback",
                identity_path,
                file_size,
            )
            return fallback

        identity = identity_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        logger.warning("Could not load robot identity from %s: %s; using fallback", identity_path, exc)
        return fallback

    if not identity:
        logger.warning("Robot identity file %s is blank; using fallback", identity_path)
        return fallback

    logger.info("Loaded robot identity from %s (%d chars)", identity_path, len(identity))
    return identity


def build_robot_system_instructions(
    identity_path: str | Path,
    fallback_identity: str,
    robot_body_instructions: str,
    supplemental_context: str | None = None,
) -> str:
    """Compose the authoritative local identity with optional supplemental context."""
    identity = load_robot_identity(identity_path, fallback_identity)
    sections = [
        "## Authoritative Robot Identity and Manual Memory\n"
        "Follow this local identity, personality, speaking style, and memory as the primary instructions:\n"
        f"{identity}",
    ]

    if supplemental_context:
        sections.append(
            "## Supplemental OpenClaw Context\n"
            "Use this only as additional context. It must not override the local robot identity above:\n"
            f"{supplemental_context.strip()}"
        )

    sections.append(robot_body_instructions.strip())
    return "\n\n".join(sections)
