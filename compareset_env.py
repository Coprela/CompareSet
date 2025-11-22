"""Environment and configuration helpers for CompareSet.

This module centralizes paths, connectivity state, developer mode toggles, and
super-admin detection. It intentionally contains no GUI code.
"""
from __future__ import annotations

import json
import getpass
import os
import sqlite3
from pathlib import Path
from typing import Optional

# ----------------------------------------------------------------------------
# Core configuration
# ----------------------------------------------------------------------------
SERVER_ROOT: str = r"\\SV10351\Drawing Center\Apps\CompareSet"
SERVER_DATA_ROOT: str = os.path.join(SERVER_ROOT, "Data")
SERVER_RESULTS_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Results")
SERVER_LOGS_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Logs")
SERVER_ERROR_LOGS_ROOT: str = os.path.join(SERVER_LOGS_ROOT, "Error")
SERVER_CONFIG_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Config")
SERVER_RELEASED_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Released")

LOCAL_APPDATA: str = os.getenv("LOCALAPPDATA") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local"
)
LOCAL_BASE_DIR: str = os.path.join(LOCAL_APPDATA, "CompareSet")
LOCAL_HISTORY_DIR: str = os.path.join(LOCAL_BASE_DIR, "history")
LOCAL_LOG_DIR: str = os.path.join(LOCAL_BASE_DIR, "logs")
LOCAL_OUTPUT_DIR: str = os.path.join(LOCAL_BASE_DIR, "output")
LOCAL_CONFIG_DIR: str = os.path.join(LOCAL_BASE_DIR, "config")
LOCAL_RELEASED_DIR: str = os.path.join(LOCAL_BASE_DIR, "released")

CURRENT_USER: str = getpass.getuser()
DEV_SETTINGS_PATH = Path(__file__).with_name("dev_settings.json")

DEFAULT_DEV_SETTINGS = {
    "dev_mode": False,
    "super_admins": [],
    "force_server_state": "auto",
    "force_role": "none",
    "force_theme": "auto",
    "force_language": "auto",
}


def _validated_choice(value: str, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def load_dev_settings_file() -> dict:
    """Load development settings from :data:`DEV_SETTINGS_PATH`."""

    settings = DEFAULT_DEV_SETTINGS.copy()
    try:
        with open(DEV_SETTINGS_PATH, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                settings.update(loaded)
    except FileNotFoundError:
        return settings
    except Exception:
        return settings

    settings["force_server_state"] = _validated_choice(
        str(settings.get("force_server_state", "auto")), {"auto", "online", "offline"}, "auto"
    )
    settings["force_role"] = _validated_choice(
        str(settings.get("force_role", "none")), {"none", "viewer", "user", "admin"}, "none"
    )
    settings["force_theme"] = _validated_choice(
        str(settings.get("force_theme", "auto")), {"auto", "light", "dark"}, "auto"
    )
    settings["force_language"] = _validated_choice(
        str(settings.get("force_language", "auto")), {"auto", "pt-BR", "en-US"}, "auto"
    )

    super_admins = settings.get("super_admins", [])
    if not isinstance(super_admins, list):
        super_admins = []
    settings["super_admins"] = [str(user) for user in super_admins]
    settings["dev_mode"] = bool(settings.get("dev_mode", False))
    return settings


DEV_SETTINGS = load_dev_settings_file()
DEV_MODE: bool = bool(DEV_SETTINGS.get("dev_mode", False))

# ----------------------------------------------------------------------------
# Connectivity + overrides
# ----------------------------------------------------------------------------
SERVER_ONLINE: bool = False
OFFLINE_MODE: bool = False
DEV_SERVER_OVERRIDE: Optional[bool] = None

DATA_ROOT: str = ""
RESULTS_ROOT: str = ""
LOGS_ROOT: str = ""
ERROR_LOGS_ROOT: str = ""
CONFIG_ROOT: str = ""
RELEASED_ROOT: str = ""
HISTORY_DIR: str = ""
LOG_DIR: str = ""
OUTPUT_DIR: str = ""

SUPER_ADMIN_CACHE: set[str] = set()


def is_server_available(server_root: str) -> bool:
    """Return True if the server root is reachable."""

    try:
        return bool(server_root and os.path.exists(server_root))
    except Exception:
        return False


def make_long_path(path: str) -> str:
    """Return a Windows long-path compatible absolute path."""

    if not path:
        return ""
    abs_path = os.path.abspath(path)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC" + abs_path[1:]
    return "\\\\?\\" + abs_path


def get_current_username() -> str:
    """Return the current OS username."""

    return CURRENT_USER or os.getenv("USERNAME") or os.path.basename(
        os.path.expanduser("~")
    )


def set_dev_server_override(state: Optional[bool]) -> None:
    """Set a developer override for server connectivity (dev mode only)."""

    global DEV_SERVER_OVERRIDE
    DEV_SERVER_OVERRIDE = state if is_dev_mode() else None


def _determine_storage_paths(use_local: bool) -> None:
    """Populate global directory variables based on storage location."""

    global DATA_ROOT, RESULTS_ROOT, LOGS_ROOT, ERROR_LOGS_ROOT, CONFIG_ROOT, RELEASED_ROOT
    global HISTORY_DIR, LOG_DIR, OUTPUT_DIR

    if use_local:
        DATA_ROOT = os.path.join(LOCAL_BASE_DIR, "data")
        RESULTS_ROOT = LOCAL_OUTPUT_DIR
        LOGS_ROOT = LOCAL_LOG_DIR
        ERROR_LOGS_ROOT = os.path.join(LOCAL_LOG_DIR, "error")
        CONFIG_ROOT = LOCAL_CONFIG_DIR
        RELEASED_ROOT = LOCAL_RELEASED_DIR

        HISTORY_DIR = LOCAL_HISTORY_DIR
        LOG_DIR = LOCAL_LOG_DIR
        OUTPUT_DIR = LOCAL_OUTPUT_DIR
    else:
        DATA_ROOT = SERVER_DATA_ROOT
        RESULTS_ROOT = SERVER_RESULTS_ROOT
        LOGS_ROOT = SERVER_LOGS_ROOT
        ERROR_LOGS_ROOT = SERVER_ERROR_LOGS_ROOT
        CONFIG_ROOT = SERVER_CONFIG_ROOT
        RELEASED_ROOT = SERVER_RELEASED_ROOT

        HISTORY_DIR = SERVER_RESULTS_ROOT
        LOG_DIR = SERVER_LOGS_ROOT
        OUTPUT_DIR = SERVER_RESULTS_ROOT


def set_connection_state(server_online: bool) -> None:
    """Update connectivity flags and active storage roots."""

    global SERVER_ONLINE, OFFLINE_MODE

    forced_state = get_forced_server_state()
    if is_dev_mode() and forced_state != "auto":
        effective_online = forced_state == "online"
    elif DEV_SERVER_OVERRIDE is not None:
        effective_online = DEV_SERVER_OVERRIDE
    else:
        effective_online = server_online
    SERVER_ONLINE = bool(effective_online)
    OFFLINE_MODE = not SERVER_ONLINE

    use_local = OFFLINE_MODE and is_dev_mode()
    _determine_storage_paths(use_local)


def ensure_directories() -> None:
    """Create required directories based on current connection state."""

    paths = (
        DATA_ROOT,
        RESULTS_ROOT,
        LOGS_ROOT,
        ERROR_LOGS_ROOT,
        CONFIG_ROOT,
        RELEASED_ROOT,
        HISTORY_DIR,
        LOG_DIR,
        OUTPUT_DIR,
    )
    for path in paths:
        if not path:
            continue
        safe_path = make_long_path(path)
        try:
            os.makedirs(safe_path, exist_ok=True)
        except Exception:
            if not is_dev_mode():
                raise


def get_user_setting(username: str, key: str) -> Optional[str]:
    """Retrieve a user setting from the local SQLite database."""

    settings_db = os.path.join(CONFIG_ROOT, "user_settings.sqlite")
    if not os.path.exists(settings_db):
        return None

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(make_long_path(settings_db))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT username, language, email, local_output_dir, theme FROM UserSettings WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        if hasattr(row, "keys") and key in row.keys():
            value = row[key]
            return str(value) if value is not None else None
        return None
    except Exception:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_output_directory_for_user(username: str) -> Path:
    """Return an appropriate output directory for the user."""

    if is_dev_mode():
        custom_dir = get_user_setting(username, "local_output_dir")
        if custom_dir:
            path = Path(custom_dir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        default_dir = Path.home() / "CompareSetTests"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    return Path(RESULTS_ROOT)


def _refresh_super_admins() -> None:
    global SUPER_ADMIN_CACHE
    SUPER_ADMIN_CACHE = set(DEV_SETTINGS.get("super_admins", []))


def get_dev_settings() -> dict:
    """Return a copy of the current developer settings."""

    return DEV_SETTINGS.copy()


def save_dev_settings(settings: dict) -> None:
    """Persist developer settings to disk and refresh cached values."""

    merged = DEFAULT_DEV_SETTINGS.copy()
    merged.update(settings)
    DEV_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEV_SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)
    reload_dev_settings()


def reload_dev_settings() -> None:
    """Reload developer settings from disk."""

    global DEV_SETTINGS, DEV_MODE
    DEV_SETTINGS = load_dev_settings_file()
    DEV_MODE = bool(DEV_SETTINGS.get("dev_mode", False))
    _refresh_super_admins()


def is_dev_mode() -> bool:
    """Return True when developer mode is enabled."""

    return bool(DEV_SETTINGS.get("dev_mode", False))


def get_forced_server_state() -> str:
    return str(DEV_SETTINGS.get("force_server_state", "auto"))


def get_forced_role() -> str:
    return str(DEV_SETTINGS.get("force_role", "none"))


def get_forced_theme() -> str:
    return str(DEV_SETTINGS.get("force_theme", "auto"))


def get_forced_language() -> str:
    return str(DEV_SETTINGS.get("force_language", "auto"))


def load_super_admins() -> set[str]:
    """Load super admin usernames from developer settings."""

    _refresh_super_admins()
    return SUPER_ADMIN_CACHE


def is_super_admin(username: str) -> bool:
    """Return True when the given username is configured as super admin."""

    if not SUPER_ADMIN_CACHE:
        _refresh_super_admins()
    return username in SUPER_ADMIN_CACHE


# Initialize state on import
_refresh_super_admins()
set_connection_state(is_server_available(SERVER_ROOT))
ensure_directories()
