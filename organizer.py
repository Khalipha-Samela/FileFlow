"""FileFlow core logic. Nothing in this module touches the UI."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

APP_NAME = "FileFlow"
OTHER = "Other"
MAX_RUNS = 25  # how many past runs are kept for undo
INVALID_NAME_CHARS = set('<>:"/\\|?*')
IGNORED_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}

DEFAULT_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv", ".webm"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".php"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".deb"],
}

Progress = Optional[Callable[[int, int], None]]


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def data_dir() -> Path:
    """Per-user folder for settings, history and the activity log."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


_FOLDER_IDS = {
    "Downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "Desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
}


def _windows_known_folder(name: str) -> Optional[Path]:
    """Ask Windows where a library folder really is (it may be redirected to OneDrive)."""
    try:
        import ctypes
        import uuid

        guid = ctypes.create_string_buffer(uuid.UUID(_FOLDER_IDS[name]).bytes_le, 16)
        buffer = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(buffer))
        try:
            return Path(buffer.value) if result == 0 and buffer.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(buffer)
    except Exception:
        return None


def quick_folders() -> list[tuple[str, Path]]:
    """Downloads, Desktop and Documents for one-click access. Only folders that exist."""
    found = []
    for name in ("Downloads", "Desktop", "Documents"):
        path = _windows_known_folder(name) if sys.platform == "win32" else None
        path = path or Path.home() / name
        if path.is_dir():
            found.append((name, path))
    return found


def _read_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data) -> None:
    # Write to a temp file first so a crash can't leave a half-written file.
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    os.replace(temp, path)


def unique_path(directory: Path, name: str) -> Path:
    """Return directory/name, or directory/name_1, name_2... if taken."""
    candidate = directory / name
    stem, suffix = Path(name).stem, Path(name).suffix
    count = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{count}{suffix}"
        count += 1
    return candidate


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def normalize_extensions(raw) -> list[str]:
    """Turn 'JPG, .png  gif' into ['.jpg', '.png', '.gif']."""
    if isinstance(raw, str):
        items = re.split(r"[,\s;]+", raw)
    elif isinstance(raw, (list, tuple)):
        items = [str(item) for item in raw]
    else:
        return []
    result: list[str] = []
    for item in items:
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        if ext not in result:
            result.append(ext)
    return result


def valid_category_name(name: str) -> bool:
    """A category becomes a folder name, so it has to be a legal one."""
    if not name or name != name.strip() or name in {".", ".."}:
        return False
    if name.endswith("."):
        return False
    return not any(char in INVALID_NAME_CHARS for char in name)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings:
    def __init__(self, directory: Path):
        self.path = directory / "settings.json"
        self.categories: dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_CATEGORIES.items()}
        self.sort_unmatched = False
        self.last_folder = ""
        self._load()
        if not self.last_folder:  # first run: start on Downloads, the folder most people want sorted
            folders = quick_folders()
            if folders:
                self.last_folder = str(folders[0][1])

    def _load(self) -> None:
        data = _read_json(self.path, {})
        if not isinstance(data, dict):
            return
        stored = data.get("categories")
        if isinstance(stored, dict):
            cleaned = {
                name: normalize_extensions(exts)
                for name, exts in stored.items()
                if isinstance(name, str) and valid_category_name(name)
            }
            if cleaned:
                self.categories = cleaned
        self.sort_unmatched = bool(data.get("sort_unmatched", False))
        last = data.get("last_folder", "")
        self.last_folder = last if isinstance(last, str) else ""

    def save(self) -> None:
        _write_json(
            self.path,
            {
                "categories": self.categories,
                "sort_unmatched": self.sort_unmatched,
                "last_folder": self.last_folder,
            },
        )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class Move:
    src: Path
    category: str


@dataclass
class RunResult:
    moved: int = 0
    counts: dict = field(default_factory=dict)
    failed: list = field(default_factory=list)


@dataclass
class UndoResult:
    restored: int = 0
    skipped: int = 0


# ---------------------------------------------------------------------------
# Organizer
# ---------------------------------------------------------------------------

class Organizer:
    def __init__(self, settings: Settings, directory: Path):
        self.settings = settings
        self.runs_path = directory / "runs.json"
        self.log_path = directory / "activity.log"

    # -- planning ----------------------------------------------------------

    def plan(self, folder) -> list[Move]:
        """Work out what would move, without touching anything."""
        root = Path(folder)
        if not root.is_dir():
            raise ValueError("That folder doesn't exist.")

        lookup: dict[str, str] = {}
        for category, extensions in self.settings.categories.items():
            for ext in extensions:
                lookup.setdefault(ext, category)  # first category wins

        try:
            with os.scandir(root) as scan:
                entries = sorted(scan, key=lambda entry: entry.name.lower())
        except PermissionError:
            raise ValueError("FileFlow doesn't have permission to read that folder.")

        moves: list[Move] = []
        for entry in entries:
            name = entry.name
            if name.startswith(".") or name.lower() in IGNORED_FILES:
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            category = lookup.get(Path(name).suffix.lower())
            if category is None and self.settings.sort_unmatched:
                category = OTHER
            if category:
                moves.append(Move(Path(entry.path), category))
        return moves

    # -- running -----------------------------------------------------------

    def run(self, folder, progress: Progress = None) -> RunResult:
        root = Path(folder)
        moves = self.plan(root)
        result = RunResult()
        recorded: list[dict] = []
        created: list[str] = []
        total = len(moves)

        for index, move in enumerate(moves, start=1):
            dest_dir = root / move.category
            try:
                if not dest_dir.exists():
                    dest_dir.mkdir()
                    created.append(str(dest_dir))
                destination = unique_path(dest_dir, move.src.name)
                shutil.move(str(move.src), str(destination))
            except OSError as error:
                reason = error.strerror or str(error)
                result.failed.append(f"{move.src.name}: {reason}")
                self.log(f"Failed to move '{move.src.name}': {reason}")
            else:
                recorded.append({"src": str(move.src), "dst": str(destination)})
                result.moved += 1
                result.counts[move.category] = result.counts.get(move.category, 0) + 1
                self.log(f"Moved '{move.src.name}' to {move.category}/")
            if progress:
                progress(index, total)

        if recorded:
            self._save_run(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "folder": str(root),
                    "moves": recorded,
                    "created_dirs": created,
                    "undone": False,
                }
            )
        else:
            for directory in created:  # nothing moved: don't leave empty folders behind
                try:
                    Path(directory).rmdir()
                except OSError:
                    pass
        return result

    # -- undo --------------------------------------------------------------

    def last_undoable(self) -> Optional[dict]:
        for run in reversed(self._load_runs()):
            if not run.get("undone"):
                return run
        return None

    def undo_last(self, progress: Progress = None) -> UndoResult:
        runs = self._load_runs()
        target = next((run for run in reversed(runs) if not run.get("undone")), None)
        if target is None:
            raise ValueError("There is nothing to undo.")

        result = UndoResult()
        moves = list(reversed(target["moves"]))
        total = len(moves)

        for index, move in enumerate(moves, start=1):
            src, dst = Path(move["src"]), Path(move["dst"])
            if not dst.exists():
                result.skipped += 1
                self.log(f"Could not restore '{dst.name}': it was moved or deleted")
            else:
                try:
                    src.parent.mkdir(parents=True, exist_ok=True)
                    back = src if not src.exists() else unique_path(src.parent, src.name)
                    shutil.move(str(dst), str(back))
                    result.restored += 1
                    self.log(f"Restored '{back.name}' to {src.parent}")
                except OSError as error:
                    result.skipped += 1
                    self.log(f"Could not restore '{dst.name}': {error.strerror or error}")
            if progress:
                progress(index, total)

        for directory in target.get("created_dirs", []):
            try:
                Path(directory).rmdir()  # only succeeds when the folder is empty
            except OSError:
                pass

        target["undone"] = True
        _write_json(self.runs_path, runs)
        self.log(f"Undo finished: {result.restored} restored, {result.skipped} skipped")
        return result

    def _load_runs(self) -> list:
        data = _read_json(self.runs_path, [])
        return data if isinstance(data, list) else []

    def _save_run(self, run: dict) -> None:
        runs = self._load_runs()
        runs.append(run)
        _write_json(self.runs_path, runs[-MAX_RUNS:])

    # -- activity log ------------------------------------------------------

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(f"{stamp}  {message}\n")
        except OSError:
            pass  # logging must never break an organize run

    def read_log(self) -> str:
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError:
            return ""

    def clear_log(self) -> None:
        try:
            open(self.log_path, "w", encoding="utf-8").close()
        except OSError:
            pass