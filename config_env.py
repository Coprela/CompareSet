"""Shared configuration and environment helpers for CompareSet."""
from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Optional

SERVER_ROOT = r"\\SV10351\Drawing Center\Apps\CompareSet"
SERVER_DATA_ROOT = os.path.join(SERVER_ROOT, "Data")
SERVER_RESULTS_ROOT = os.path.join(SERVER_DATA_ROOT, "Results")
SERVER_LOGS_ROOT = os.path.join(SERVER_DATA_ROOT, "Logs")
SERVER_ERROR_LOGS_ROOT = os.path.join(SERVER_LOGS_ROOT, "Error")
SERVER_CONFIG_ROOT = os.path.join(SERVER_DATA_ROOT, "Config")
SERVER_RELEASED_ROOT = os.path.join(SERVER_DATA_ROOT, "Released")

LOCAL_APPDATA = os.getenv("LOCALAPPDATA") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local"
)
LOCAL_BASE_DIR = os.path.join(LOCAL_APPDATA, "CompareSet")
LOCAL_HISTORY_DIR = os.path.join(LOCAL_BASE_DIR, "history")
LOCAL_LOG_DIR = os.path.join(LOCAL_BASE_DIR, "logs")
LOCAL_OUTPUT_DIR = os.path.join(LOCAL_BASE_DIR, "output")
LOCAL_CONFIG_DIR = os.path.join(LOCAL_BASE_DIR, "config")
LOCAL_RELEASED_DIR = os.path.join(LOCAL_BASE_DIR, "released")

OFFLINE_ALLOWED_USERS = {"doliveira12"}
LOCAL_STORAGE_ALLOWED_USERS = {"doliveira12"}

CURRENT_USER = getpass.getuser()

SERVER_ONLINE = False
OFFLINE_MODE = False
DATA_ROOT = ""
RESULTS_ROOT = ""
LOGS_ROOT = ""
ERROR_LOGS_ROOT = ""
CONFIG_ROOT = ""
RELEASED_ROOT = ""
HISTORY_DIR = ""
LOG_DIR = ""
OUTPUT_DIR = ""


def is_tester_user(username: str) -> bool:
    return username in LOCAL_STORAGE_ALLOWED_USERS


def get_current_username() -> str:
    return CURRENT_USER or os.getenv("USERNAME") or os.path.basename(os.path.expanduser("~"))


IS_TESTER = is_tester_user(CURRENT_USER)


def is_server_available(server_root: str) -> bool:
    try:
        if not server_root or not server_root.strip():
            return False
        return os.path.exists(server_root)
    except Exception:
        return False


def make_long_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC" + abs_path[1:]
    return "\\\\?\\" + abs_path


def set_connection_state(server_online: bool) -> None:
    global SERVER_ONLINE, OFFLINE_MODE
    global DATA_ROOT, RESULTS_ROOT, LOGS_ROOT, ERROR_LOGS_ROOT, CONFIG_ROOT, RELEASED_ROOT
    global HISTORY_DIR, LOG_DIR, OUTPUT_DIR

    SERVER_ONLINE = server_online
    OFFLINE_MODE = not server_online

    use_local_storage = OFFLINE_MODE and CURRENT_USER in OFFLINE_ALLOWED_USERS

    DATA_ROOT = SERVER_DATA_ROOT if not use_local_storage else os.path.join(LOCAL_BASE_DIR, "data")
    RESULTS_ROOT = SERVER_RESULTS_ROOT if not use_local_storage else LOCAL_OUTPUT_DIR
    LOGS_ROOT = SERVER_LOGS_ROOT if not use_local_storage else LOCAL_LOG_DIR
    ERROR_LOGS_ROOT = (
        SERVER_ERROR_LOGS_ROOT if not use_local_storage else os.path.join(LOCAL_LOG_DIR, "error")
    )
    CONFIG_ROOT = SERVER_CONFIG_ROOT if not use_local_storage else LOCAL_CONFIG_DIR
    RELEASED_ROOT = SERVER_RELEASED_ROOT if not use_local_storage else LOCAL_RELEASED_DIR

    SERVER_HISTORY_DIR = SERVER_RESULTS_ROOT
    SERVER_LOG_DIR = SERVER_LOGS_ROOT
    SERVER_OUTPUT_DIR = SERVER_RESULTS_ROOT

    HISTORY_DIR = SERVER_HISTORY_DIR if not use_local_storage else LOCAL_HISTORY_DIR
    LOG_DIR = SERVER_LOG_DIR if not use_local_storage else LOCAL_LOG_DIR
    OUTPUT_DIR = SERVER_OUTPUT_DIR if not use_local_storage else LOCAL_OUTPUT_DIR


def ensure_server_directories() -> None:
    if SERVER_ONLINE:
        for path in (
            DATA_ROOT,
            RESULTS_ROOT,
            LOGS_ROOT,
            ERROR_LOGS_ROOT,
            CONFIG_ROOT,
            RELEASED_ROOT,
        ):
            if not path or not str(path).strip("\\/"):
                continue
            safe_path = make_long_path(path)
            if safe_path in {"\\\\?\\UNC\\", "\\\\?\\"}:
                continue
            os.makedirs(safe_path, exist_ok=True)
    elif CURRENT_USER in OFFLINE_ALLOWED_USERS:
        for path in (
            LOCAL_BASE_DIR,
            HISTORY_DIR,
            LOG_DIR,
            OUTPUT_DIR,
            CONFIG_ROOT,
            RELEASED_ROOT,
            ERROR_LOGS_ROOT,
        ):
            if not path or not str(path).strip():
                continue
            safe_path = make_long_path(path)
            if safe_path in {"\\\\?\\UNC\\", "\\\\?\\"}:
                continue
            os.makedirs(safe_path, exist_ok=True)


def get_user_setting(username: str, key: str) -> Optional[str]:
    settings_db = os.path.join(CONFIG_ROOT, "user_settings.sqlite")
    if not os.path.exists(settings_db):
        return None
    import sqlite3

    conn = sqlite3.connect(make_long_path(settings_db))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT language, email FROM UserSettings WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return None
        return str(row.get(key, "")) if hasattr(row, "get") else row[key]
    except Exception:
        return None
    finally:
        conn.close()


def get_output_directory_for_user(username: str) -> Path:
    if is_tester_user(username):
        custom_dir = get_user_setting(username, "local_output_dir")
        if custom_dir:
            p = Path(custom_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        base = Path.home() / "CompareSetTests"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return Path(RESULTS_ROOT)


set_connection_state(is_server_available(SERVER_ROOT))
