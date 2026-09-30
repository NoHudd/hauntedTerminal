#!/usr/bin/env python3
import os
import shutil

# Content, saves, logs and user settings are all addressed relative to the
# repo, and some are opened at import time, so this runs before anything else.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def rotate_logs(log_file: str, previous: str = "combat.log", header: str = "") -> None:
    """Start the session with a fresh log, opened by `header` (the build) when
    given; keep the last session's log as `previous`."""
    if os.path.exists(log_file):
        shutil.copy2(log_file, previous)
    else:
        with open(previous, "w") as f:
            f.write("=== Combat Log (Fresh Session) ===\n")
    with open(log_file, "w") as f:
        if header:
            f.write(header + "\n")


if __name__ == "__main__":
    from datetime import datetime

    from config.dev_config import DEBUG_LOG_FILE
    from src.version import build_label  # logs nothing, so safe before rotating

    # Before the game modules load: some of them log while importing.
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rotate_logs(DEBUG_LOG_FILE, header=f"=== {build_label()} — session started {started} ===")

    from src.game_engine import main
    from src.ui.textual_ui import TextualGameUI  # composition root: the frontend is chosen HERE

    # Run the game — build the concrete frontend and inject it into the backend.
    main(TextualGameUI())
