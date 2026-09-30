"""The game's version. One source of truth, `version` in pyproject.toml, plus
the git commit when running from a checkout, so a screenshot or a log always
names the build that produced it. Imports nothing from the game and logs
nothing, so main.py may use it before the debug log is rotated."""
from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
# The first `version = "..."` line is [project]'s: it heads pyproject.toml.
# Read with a regex, not tomllib, which Python 3.10 (still supported) lacks.
_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


@lru_cache(maxsize=1)
def version() -> str:
    try:
        text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    match = _VERSION_LINE.search(text)
    return match.group(1) if match else "unknown"


@lru_cache(maxsize=1)
def commit() -> str | None:
    """Short hash of the checked-out commit, or None outside a git checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT, capture_output=True, text=True, timeout=2, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def build_label() -> str:
    """'Haunted Terminal v0.2.0 (8ed4512)', or without the hash outside git."""
    sha = commit()
    return f"Haunted Terminal v{version()}" + (f" ({sha})" if sha else "")
