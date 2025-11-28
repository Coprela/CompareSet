"""Self-installation helpers for CompareSet.

These utilities emulate an installer by copying the running executable to a
well-known folder inside ``%LOCALAPPDATA%`` and creating shortcuts. Operations
are no-ops on non-Windows systems so development on Linux/macOS stays simple.
"""
from __future__ import annotations

import os
import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

import compareset_env as csenv

try:
    import winshell  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    winshell = None


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def official_binary_path() -> Path:
    return Path(csenv.LOCAL_BASE_DIR) / "CompareSet.exe"


def ensure_user_config(language: str = "en-US", theme: str = "system") -> None:
    """Create the ``user_config.json`` file with defaults if missing."""

    config_path = Path(csenv.USER_CONFIG_PATH)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(
            '{"language": "%s", "theme": "%s"}' % (language, theme),
            encoding="utf-8",
        )


def _create_shortcut(target: Path, shortcut_path: Path) -> None:
    if winshell is None:
        return
    try:
        with winshell.shortcut(str(shortcut_path)) as link:  # type: ignore[attr-defined]
            link.path = str(target)
            link.description = "CompareSet"
    except Exception:
        pass


def ensure_shortcuts(installed_binary: Path) -> None:
    """Create Start Menu and Desktop shortcuts if possible."""

    if not _is_windows():
        return
    start_menu = os.path.join(os.getenv("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if start_menu:
        shortcut = Path(start_menu) / "CompareSet.lnk"
        shortcut.parent.mkdir(parents=True, exist_ok=True)
        _create_shortcut(installed_binary, shortcut)
    if desktop:
        shortcut = Path(desktop) / "CompareSet.lnk"
        _create_shortcut(installed_binary, shortcut)


def _should_remove_source(source_binary: Path, installed_path: Path) -> bool:
    """Return True when the source binary looks like a downloaded installer."""

    try:
        source_resolved = source_binary.resolve()
        installed_resolved = installed_path.resolve()
    except Exception:
        return False

    if source_resolved == installed_resolved:
        return False

    # Heuristic: remove if the source lives inside a Downloads folder
    parts = [part.lower() for part in source_resolved.parts]
    return any(part == "downloads" for part in parts)


def _current_executable() -> Path:
    """Return the path to the currently running executable or script."""

    if getattr(sys, "frozen", False):  # Running via PyInstaller bundle
        return Path(sys.executable)
    return Path(sys.argv[0]).resolve()


def _init_local_layout() -> None:
    """Ensure CompareSet local directories exist."""

    Path(csenv.LOCAL_BASE_DIR).mkdir(parents=True, exist_ok=True)
    Path(csenv.LOCAL_CONFIG_DIR).mkdir(parents=True, exist_ok=True)
    Path(csenv.LOCAL_TEMP_DIR).mkdir(parents=True, exist_ok=True)
    Path(csenv.LOCAL_HISTORY_DIR).mkdir(parents=True, exist_ok=True)
    Path(csenv.LOCAL_UPDATE_DIR).mkdir(parents=True, exist_ok=True)


def _clone_binary_to_official(src: Path, dest: Path) -> None:
    try:
        if dest.resolve() == src.resolve():
            return
    except Exception:
        pass
    shutil.copy2(src, dest)


def perform_fake_install(source_binary: Optional[Path] = None) -> Path:
    """Copy the current executable to the official location and return it."""

    _init_local_layout()
    ensure_user_config()

    installed_path = official_binary_path()
    src = source_binary or _current_executable()

    if _is_windows():
        try:
            _clone_binary_to_official(src, installed_path)
        except Exception as exc:  # pragma: no cover - defensive
            logging.error("Failed to copy binary to official location: %s", exc)
    else:
        installed_path = src

    ensure_shortcuts(installed_path)

    if _is_windows() and _should_remove_source(src, installed_path):
        try:
            src.unlink()
        except Exception:
            pass

    return installed_path


def ensure_installed_binary() -> Path:
    """Guarantee the official binary exists, copying from current exe if needed."""

    installed = official_binary_path()
    if installed.exists():
        _init_local_layout()
        ensure_user_config()
        ensure_shortcuts(installed)
        return installed

    return perform_fake_install()
