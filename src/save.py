#!/usr/bin/env python3
"""Run save slots.

Every run (one new game) owns one file, saves/run_<runId>.json, which each
autosave, checkpoint and `save` overwrites. The player picks a run from the
title menu's LOAD GAME; at most MAX_RUNS exist at once.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from src import difficulty

logger = logging.getLogger(__name__)

# Current on-disk save format version. v5 added room flags; v6 made saves one
# file per run (runId, createdAt, cleared).
SAVE_VERSION = 6

# Saves older than this cannot be loaded: v2 and earlier predate the filesystem
# tree; v3-v4 predate room flags, so /boot's flag gate would strand them.
MIN_SUPPORTED_VERSION = 5

# Run slots on disk at once. NEW GAME with every slot taken asks which run to
# replace.
MAX_RUNS = 9

RUN_PREFIX = "run_"

# The pre-slot pool: save_<timestamp>.json. Migrated once, then kept in legacy/.
LEGACY_PREFIX = "save_"
LEGACY_DIR = "legacy"


def _now() -> float:
    """Wall-clock seconds; one seam for tests to control save order."""
    return time.time()


class IncompatibleSaveError(Exception):
    """Raised when a save predates a world change that cannot be migrated."""


def save_version(save_data) -> int:
    """Envelope version of a loaded save. Pre-versioning saves count as v1."""
    if not isinstance(save_data, dict):
        return 0
    try:
        return int(save_data.get("version", 1))
    except (TypeError, ValueError):
        return 0


def _migrate_save(save_data):
    """Normalize a save envelope to the current version, or refuse it.

    v2 and older persist room_states from before /usr, /var and /boot were
    locked; v3-v4 predate room flags. Neither can be honestly reconstructed,
    so both are refused with a message rather than half-migrated. v5 saves
    load as they are (the v6 fields have defaults).
    """
    if not isinstance(save_data, dict):
        return save_data

    version = save_version(save_data)
    if version < 3:
        raise IncompatibleSaveError(
            f"save format v{version} is from before the filesystem rework and "
            f"cannot be loaded (current format is v{SAVE_VERSION})"
        )
    if version < MIN_SUPPORTED_VERSION:
        raise IncompatibleSaveError(
            f"save format v{version} is from before room flags and cannot be "
            f"loaded (current format is v{SAVE_VERSION})"
        )
    return save_data


@dataclass(frozen=True)
class RunInfo:
    """One run slot, as the save picker shows it."""
    run_id: str
    player_name: str
    player_class: str
    difficulty: str
    level: int
    room_id: str
    health: int
    max_health: int
    saved_at: float
    cleared: bool


class SaveManager:
    """Owns the run slots on disk and which run is being played."""

    def __init__(self, save_dir="saves"):
        self.save_dir = save_dir
        # The run being played, and a run the player chose to replace (deleted
        # by the new run's first save, so backing out of setup loses nothing).
        self.active_run_id: str | None = None
        self.pending_replace: str | None = None
        os.makedirs(self.save_dir, exist_ok=True)

    # -- files ------------------------------------------------------------

    def _run_path(self, run_id: str) -> str:
        return os.path.join(self.save_dir, f"{RUN_PREFIX}{run_id}.json")

    def _run_files(self) -> list[str]:
        try:
            names = os.listdir(self.save_dir)
        except FileNotFoundError:
            return []
        return [n for n in names if n.startswith(RUN_PREFIX) and n.endswith(".json")]

    @staticmethod
    def _read(path: str) -> dict[str, Any] | None:
        try:
            with open(path) as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _write(self, path: str, data: dict[str, Any]) -> None:
        """Write via a temp file + rename, so a crash mid-save never leaves a
        half-written slot."""
        os.makedirs(self.save_dir, exist_ok=True)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w") as file:
                json.dump(data, file, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.error(f"Failed to save game: {e}")
            raise

    # -- the run being played ---------------------------------------------

    def begin_run(self, replace: str | None = None) -> str:
        """Start a new run. Nothing is written until its first save."""
        self.active_run_id = uuid.uuid4().hex[:8]
        self.pending_replace = replace
        return self.active_run_id

    def resume_run(self, run_id: str) -> None:
        """Continue a run picked from LOAD GAME."""
        self.active_run_id = run_id
        self.pending_replace = None

    def end_run(self) -> None:
        """Back at the title: no run is being played."""
        self.active_run_id = None
        self.pending_replace = None

    def save_game(self, player, world_state) -> str:
        """Overwrite the active run's slot (starting a run if none is active —
        the headless GameSession creates players without the menu). Returns the
        file path."""
        if self.active_run_id is None:
            self.begin_run()
        run_id = self.active_run_id
        assert run_id is not None
        path = self._run_path(run_id)
        previous = self._read(path) or {}
        now = _now()
        self._write(path, {
            "version": SAVE_VERSION,
            "runId": run_id,
            "createdAt": previous.get("createdAt", now),
            "cleared": bool(previous.get("cleared", False)),
            "player": player.to_dict(),
            "world": world_state,
            "difficulty": difficulty.current_mode(),
            "savedAt": now,
            "saveDate": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        logger.info(f"Game saved to {path}")

        if self.pending_replace:
            replaced, self.pending_replace = self.pending_replace, None
            if replaced != run_id:
                self.delete_run(replaced)
                logger.info(f"Run {replaced} replaced by {run_id}")
        return path

    def mark_cleared(self) -> None:
        """Mark the active run as beaten. Its last save stays as it is."""
        if self.active_run_id is None:
            return
        path = self._run_path(self.active_run_id)
        data = self._read(path)
        if data is None:
            return
        data["cleared"] = True
        self._write(path, data)

    # -- every run --------------------------------------------------------

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        """The run's save, or None if it is missing or unreadable. Raises
        IncompatibleSaveError for a format that cannot load."""
        path = self._run_path(run_id)
        if not os.path.exists(path):
            logger.warning(f"No save for run {run_id}")
            return None
        data = self._read(path)
        if data is None:
            logger.error(f"Could not read the save for run {run_id}")
            return None
        return _migrate_save(data)

    def list_runs(self) -> list[RunInfo]:
        """Every loadable run, most recently saved first. A bad file (or a
        failed migration) is logged and skipped: one broken save must never
        lock the player out of NEW GAME / LOAD GAME."""
        try:
            self._migrate_legacy()
        except (OSError, TypeError, ValueError, AttributeError) as e:
            logger.warning(f"Old-save migration failed: {e}")
        runs: list[RunInfo] = []
        for name in self._run_files():
            data = self._read(os.path.join(self.save_dir, name))
            if data is None:
                logger.warning(f"Skipping unreadable save {name}")
                continue
            try:
                data = _migrate_save(data)
            except IncompatibleSaveError as e:
                logger.warning(f"Skipping {name}: {e}")
                continue
            try:
                runs.append(self._run_info(name, data))
            except (TypeError, ValueError, AttributeError) as e:
                logger.warning(f"Skipping malformed save {name}: {e}")
        runs.sort(key=lambda run: run.saved_at, reverse=True)
        return runs

    @staticmethod
    def _run_info(filename: str, data: dict[str, Any]) -> RunInfo:
        player = data.get("player") or {}
        return RunInfo(
            run_id=filename[len(RUN_PREFIX):-len(".json")],
            player_name=str(player.get("name", "?")),
            player_class=str(player.get("player_class", "guardian")),
            difficulty=str(data.get("difficulty", difficulty.DEFAULT_MODE)),
            level=int(player.get("level", 1)),
            room_id=str(player.get("current_room", "home_grove")),
            health=int(player.get("health", 0)),
            max_health=int(player.get("max_health", 0)),
            saved_at=float(data.get("savedAt", 0.0)),
            cleared=bool(data.get("cleared", False)),
        )

    def _migrate_legacy(self) -> None:
        """Turn pre-slot saves (one pool of save_<ts>.json files) into run slots.

        Files are grouped by hero (name, class, difficulty); the newest file of
        each group becomes a slot, newest groups first, up to the free slots.
        Every old file (used, too old or unreadable) then moves to
        saves/legacy/. Nothing is deleted.
        """
        try:
            names = [
                n for n in os.listdir(self.save_dir)
                if n.startswith(LEGACY_PREFIX) and n.endswith(".json")
            ]
        except FileNotFoundError:
            return
        if not names:
            return

        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for name in names:
            data = self._read(os.path.join(self.save_dir, name))
            if data is None or save_version(data) < MIN_SUPPORTED_VERSION:
                continue
            player = data.get("player") or {}
            hero = (
                str(player.get("name", "")),
                str(player.get("player_class", "")),
                str(data.get("difficulty", difficulty.DEFAULT_MODE)),
            )
            groups.setdefault(hero, []).append(data)

        def saved_at(save: dict[str, Any]) -> float:
            return float(save.get("savedAt", 0.0))

        free = max(MAX_RUNS - len(self._run_files()), 0)
        newest_first = sorted(
            groups.values(), key=lambda saves: max(map(saved_at, saves)), reverse=True,
        )
        for saves in newest_first[:free]:
            latest = max(saves, key=saved_at)
            run_id = uuid.uuid4().hex[:8]
            self._write(self._run_path(run_id), {
                **latest,
                "version": SAVE_VERSION,
                "runId": run_id,
                "createdAt": min(map(saved_at, saves)),
                "cleared": False,
            })

        legacy = os.path.join(self.save_dir, LEGACY_DIR)
        os.makedirs(legacy, exist_ok=True)
        for name in names:
            os.replace(os.path.join(self.save_dir, name), os.path.join(legacy, name))
        logger.info(
            f"Moved {len(names)} old save(s) to {legacy}; "
            f"{min(len(groups), free)} became run slots"
        )

    def legacy_count(self) -> int:
        """Old-format saves kept in saves/legacy/."""
        try:
            names = os.listdir(os.path.join(self.save_dir, LEGACY_DIR))
        except FileNotFoundError:
            return 0
        return len([n for n in names if n.endswith(".json")])

    def runs_full(self) -> bool:
        return len(self.list_runs()) >= MAX_RUNS

    def delete_run(self, run_id: str) -> bool:
        try:
            os.remove(self._run_path(run_id))
            return True
        except FileNotFoundError:
            return False


# Create a singleton instance
save_manager = SaveManager()
