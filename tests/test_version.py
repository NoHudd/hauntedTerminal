"""The game names its build: one version in pyproject.toml, shown on the title
screen and written at the top of every session's debug.log, so a screenshot
or a log always says which code produced it."""
from __future__ import annotations

import importlib
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

import main
from src import version
from src.ui.title_menu import TitleMenu


def test_version_comes_from_pyproject() -> None:
    with open("pyproject.toml", "rb") as f:
        declared = tomllib.load(f)["project"]["version"]
    assert version.version() == declared
    assert re.fullmatch(r"\d+\.\d+\.\d+", declared), "use MAJOR.MINOR.PATCH"


def test_version_works_on_python_3_10_without_tomllib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launchers accept Python 3.10, which has no tomllib."""
    monkeypatch.setitem(sys.modules, "tomllib", None)  # import tomllib -> ImportError
    fresh = importlib.reload(version)
    try:
        assert re.fullmatch(r"\d+\.\d+\.\d+", fresh.version())
    finally:
        monkeypatch.delitem(sys.modules, "tomllib")
        importlib.reload(version)


def test_build_label_names_the_version_and_commit() -> None:
    label = version.build_label()
    assert f"v{version.version()}" in label
    commit = version.commit()
    if commit is not None:  # a source download without git has no commit
        assert commit in label


def test_a_log_session_starts_with_the_build(tmp_path: Path) -> None:
    log, previous = tmp_path / "debug.log", tmp_path / "combat.log"
    main.rotate_logs(str(log), str(previous), header="=== Haunted Terminal v9.9.9 ===")
    assert log.read_text().splitlines()[0] == "=== Haunted Terminal v9.9.9 ==="


class _FakeApp:
    def __init__(self) -> None:
        self.shown: list[Any] = []

    def add_class(self, name: str) -> None:
        pass

    def update_output(self, renderable: Any) -> None:
        self.shown.append(renderable)


def test_title_screen_shows_the_version() -> None:
    app = _FakeApp()
    TitleMenu(app).show(skip_typewriter=True)  # type: ignore[arg-type]
    assert f"v{version.version()}" in app.shown[-1].plain
