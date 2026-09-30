"""Launching from another directory: every path the game uses (content, saves,
logs, user settings) is relative, so main.py must move to the repo first.
Before, `python ~/hauntedTerminal/main.py` from $HOME could not find its
content and left empty data/ and saves/ folders in $HOME."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_importing_main_from_elsewhere_works_from_the_repo(tmp_path: Path) -> None:
    probe = (
        "import os, sys; "
        f"sys.path.insert(0, {str(ROOT)!r}); "
        "import main; "
        "from src.save import save_manager; "
        "print(os.getcwd()); "
        "print(os.path.abspath(save_manager.save_dir))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=tmp_path,
        capture_output=True, text=True, timeout=60, check=True,
    )
    cwd, save_dir = result.stdout.strip().splitlines()[-2:]

    assert Path(cwd) == ROOT
    assert Path(save_dir) == ROOT / "saves"
    assert os.listdir(tmp_path) == []
