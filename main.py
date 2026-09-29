#!/usr/bin/env python3
import os
import shutil

# Content, saves, logs and user settings are all addressed relative to the
# repo, and some are opened at import time, so this runs before anything else.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def rotate_logs(log_file: str, previous: str = "combat.log") -> None:
    """Start the session with an empty log; keep the last session's as `previous`."""
    if os.path.exists(log_file):
        shutil.copy2(log_file, previous)
    else:
        with open(previous, "w") as f:
            f.write("=== Combat Log (Fresh Session) ===\n")
    open(log_file, "w").close()


if __name__ == "__main__":
    from config.dev_config import DEBUG_LOG_FILE

    # Before the game modules load: some of them log while importing.
    rotate_logs(DEBUG_LOG_FILE)

    from src.game_engine import main
    from src.ui.textual_ui import TextualGameUI  # composition root: the frontend is chosen HERE

    # Run the game — build the concrete frontend and inject it into the backend.
    main(TextualGameUI())
