"""Environment and path helpers for CompareSet (compareset_env.py).

This module centralizes server/local directory configuration, connection
state management, and helper utilities for determining user-specific paths.
It is intentionally independent from any GUI framework.
"""
from __future__ import annotations

import getpass
import os
import sqlite3
from pathlib import Path
from typing import Optional

# Server directory configuration
SERVER_ROOT: str = r"\\SV10351\Drawing Center\Apps\CompareSet"
SERVER_DATA_ROOT: str = os.path.join(SERVER_ROOT, "Data")
SERVER_RESULTS_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Results")
SERVER_LOGS_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Logs")
SERVER_ERROR_LOGS_ROOT: str = os.path.join(SERVER_LOGS_ROOT, "Error")
SERVER_CONFIG_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Config")
SERVER_RELEASED_ROOT: str = os.path.join(SERVER_DATA_ROOT, "Released")

# Local directory configuration
LOCAL_APPDATA: str = os.getenv("LOCALAPPDATA") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local"
)
LOCAL_BASE_DIR: str = os.path.join(LOCAL_APPDATA, "CompareSet")
LOCAL_HISTORY_DIR: str = os.path.join(LOCAL_BASE_DIR, "history")
LOCAL_LOG_DIR: str = os.path.join(LOCAL_BASE_DIR, "logs")
LOCAL_OUTPUT_DIR: str = os.path.join(LOCAL_BASE_DIR, "output")
LOCAL_CONFIG_DIR: str = os.path.join(LOCAL_BASE_DIR, "config")
LOCAL_RELEASED_DIR: str = os.path.join(LOCAL_BASE_DIR, "released")

# User permissions
OFFLINE_ALLOWED_USERS: set[str] = {"doliveira12"}
LOCAL_STORAGE_ALLOWED_USERS: set[str] = {"doliveira12"}

# User information
CURRENT_USER: str = getpass.getuser()
IS_TESTER: bool = False

# Connection state
SERVER_ONLINE: bool = False
OFFLINE_MODE: bool = False

# Active roots (resolved via connection state)
DATA_ROOT: str = ""
RESULTS_ROOT: str = ""
LOGS_ROOT: str = ""
ERROR_LOGS_ROOT: str = ""
CONFIG_ROOT: str = ""
RELEASED_ROOT: str = ""

# Local/session directories
HISTORY_DIR: str = ""
LOG_DIR: str = ""
OUTPUT_DIR: str = ""


def is_tester_user(username: str) -> bool:
    """Return True if the username is considered a tester."""

    return username in LOCAL_STORAGE_ALLOWED_USERS


def get_current_username() -> str:
    """Return the current username using common environment fallbacks."""

    return CURRENT_USER or os.getenv("USERNAME") or os.path.basename(os.path.expanduser("~"))


def is_server_available(server_root: str) -> bool:
    """Check if the given server root path is reachable."""

    try:
        if not server_root or not server_root.strip():
            return False
        return os.path.exists(server_root)
    except Exception:
        return False


def make_long_path(path: str) -> str:
    """Return a Windows long-path compatible string for the given path."""

    if not path:
        return ""
    abs_path = os.path.abspath(path)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC" + abs_path[1:]
    return "\\\\?\\" + abs_path


def set_connection_state(server_online: bool) -> None:
    """Update global paths based on whether the server is reachable."""

    global SERVER_ONLINE, OFFLINE_MODE
    global DATA_ROOT, RESULTS_ROOT, LOGS_ROOT, ERROR_LOGS_ROOT, CONFIG_ROOT, RELEASED_ROOT
    global HISTORY_DIR, LOG_DIR, OUTPUT_DIR

    SERVER_ONLINE = bool(server_online)
    OFFLINE_MODE = not SERVER_ONLINE

    use_local_storage = OFFLINE_MODE and (
        CURRENT_USER in OFFLINE_ALLOWED_USERS or CURRENT_USER in LOCAL_STORAGE_ALLOWED_USERS
    )

    if SERVER_ONLINE:
        DATA_ROOT = SERVER_DATA_ROOT
        RESULTS_ROOT = SERVER_RESULTS_ROOT
        LOGS_ROOT = SERVER_LOGS_ROOT
        ERROR_LOGS_ROOT = SERVER_ERROR_LOGS_ROOT
        CONFIG_ROOT = SERVER_CONFIG_ROOT
        RELEASED_ROOT = SERVER_RELEASED_ROOT

        HISTORY_DIR = SERVER_RESULTS_ROOT
        LOG_DIR = SERVER_LOGS_ROOT
        OUTPUT_DIR = SERVER_RESULTS_ROOT
        return

    # Server offline
    if use_local_storage:
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


def ensure_server_directories() -> None:
    """Create required directories based on the current connection state."""

    def _create_paths(paths: tuple[str, ...]) -> None:
        for path in paths:
            if not path or not str(path).strip():
                continue
            safe_path = make_long_path(path)
            if safe_path in {"\\\\?\\UNC\\", "\\\\?\\"}:
                continue
            os.makedirs(safe_path, exist_ok=True)

    if SERVER_ONLINE:
        _create_paths(
            (
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
        )
    elif CURRENT_USER in OFFLINE_ALLOWED_USERS:
        _create_paths(
            (
                LOCAL_BASE_DIR,
                LOCAL_HISTORY_DIR,
                LOCAL_LOG_DIR,
                LOCAL_OUTPUT_DIR,
                LOCAL_CONFIG_DIR,
                LOCAL_RELEASED_DIR,
                os.path.join(LOCAL_LOG_DIR, "error"),
            )
        )


def get_user_setting(username: str, key: str) -> Optional[str]:
    """Retrieve a specific user setting from the local SQLite database."""

    settings_db = os.path.join(CONFIG_ROOT, "user_settings.sqlite")
    if not os.path.exists(settings_db):
        return None

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(make_long_path(settings_db))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT username, language, email, local_output_dir FROM UserSettings WHERE username = ?",
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
    """Return the output directory for the given user, creating it if needed."""

    if is_tester_user(username):
        custom_dir = get_user_setting(username, "local_output_dir")
        if custom_dir:
            path = Path(custom_dir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        default_dir = Path.home() / "CompareSetTests"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    return Path(RESULTS_ROOT)


# Initialize state
IS_TESTER = is_tester_user(CURRENT_USER)
set_connection_state(is_server_available(SERVER_ROOT))
ensure_server_directories()
