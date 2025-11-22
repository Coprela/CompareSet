"""Environment and configuration helpers for CompareSet.

This module centralizes paths, connectivity state, developer mode toggles, and
super-admin detection. It intentionally contains no GUI code.
"""
from __future__ import annotations

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
DEV_MODE: bool = os.getenv("COMPARESET_DEV_MODE", "0") == "1"
OFFLINE_ALLOWED_USERS: set[str] = {"doliveira12"}
IS_TESTER: bool = CURRENT_USER in OFFLINE_ALLOWED_USERS

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
    DEV_SERVER_OVERRIDE = state if DEV_MODE else None


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

    effective_online = DEV_SERVER_OVERRIDE if DEV_SERVER_OVERRIDE is not None else server_online
    SERVER_ONLINE = bool(effective_online)
    OFFLINE_MODE = not SERVER_ONLINE

    use_local = OFFLINE_MODE and (DEV_MODE or CURRENT_USER in OFFLINE_ALLOWED_USERS)
    _determine_storage_paths(use_local)


def ensure_directories() -> None:
    """Create required directories based on current connection state."""

    if OFFLINE_MODE and not DEV_MODE:
        return

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
            if not DEV_MODE:
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

    if DEV_MODE:
        custom_dir = get_user_setting(username, "local_output_dir")
        if custom_dir:
            path = Path(custom_dir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        default_dir = Path.home() / "CompareSetTests"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    return Path(RESULTS_ROOT)


def load_super_admins() -> set[str]:
    """Load super admin usernames from configuration files."""

    global SUPER_ADMIN_CACHE
    candidates = [
        os.path.join(CONFIG_ROOT, "super_admins.txt"),
        os.path.join(LOCAL_CONFIG_DIR, "super_admins.txt"),
    ]
    admins: set[str] = set()
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    username = line.strip()
                    if username:
                        admins.add(username)
        except FileNotFoundError:
            continue
        except Exception:
            if not DEV_MODE:
                raise
    SUPER_ADMIN_CACHE = admins
    return admins


def is_super_admin(username: str) -> bool:
    """Return True when the given username is configured as super admin."""

    if not SUPER_ADMIN_CACHE:
        load_super_admins()
    return username in SUPER_ADMIN_CACHE


# Initialize state on import
set_connection_state(is_server_available(SERVER_ROOT))
ensure_directories()
