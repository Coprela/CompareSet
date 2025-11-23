"""Environment and configuration helpers for CompareSet.

This module centralizes paths, connectivity state, developer/test mode
overrides, and super-admin/offline tester detection. It intentionally contains
no GUI code.
"""
from __future__ import annotations

import json
import logging
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

OFFLINE_ALLOWED_USERS: set[str] = set()
LOCAL_STORAGE_ALLOWED_USERS: set[str] = set()

# Developer/test configuration defaults. The JSON file can override any of
# these values and is treated as the single source of truth for dev mode.
DEFAULT_DEV_SETTINGS = {
    "dev_mode": False,
    "force_server_state": "auto",  # "online", "offline", "auto"
    "force_role": "none",  # "none", "viewer", "user", "admin"
    "override_theme": None,  # "light", "dark", None
    "override_language": None,  # "pt-BR", "en-US", None
    "super_admins": [],
    "local_storage_testers": [],
}


def _validated_choice(value: str, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def _normalize_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def load_dev_settings_file() -> dict:
    """Load development settings from :data:`DEV_SETTINGS_PATH`.

    The resulting dictionary always matches :data:`DEFAULT_DEV_SETTINGS` keys and
    performs basic validation of options.
    """

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

    # Legacy key support
    if settings.get("force_language") and not settings.get("override_language"):
        settings["override_language"] = settings.get("force_language")
    if settings.get("force_theme") and not settings.get("override_theme"):
        settings["override_theme"] = settings.get("force_theme")

    settings["force_server_state"] = _validated_choice(
        str(settings.get("force_server_state", "auto")), {"auto", "online", "offline"}, "auto"
    )
    settings["force_role"] = _validated_choice(
        str(settings.get("force_role", "none")), {"none", "viewer", "user", "admin"}, "none"
    )

    language = settings.get("override_language")
    if language is not None:
        language = _validated_choice(str(language), {"pt-BR", "en-US"}, "auto")
    settings["override_language"] = None if language in {None, "auto"} else language

    theme = settings.get("override_theme")
    if theme is not None:
        theme = _validated_choice(str(theme), {"light", "dark"}, "auto")
    settings["override_theme"] = None if theme in {None, "auto"} else theme

    settings["super_admins"] = _normalize_list(settings.get("super_admins"))
    settings["local_storage_testers"] = _normalize_list(settings.get("local_storage_testers"))
    settings["dev_mode"] = bool(settings.get("dev_mode", False))
    return settings


DEV_SETTINGS = load_dev_settings_file()
DEV_MODE: bool = bool(DEV_SETTINGS.get("dev_mode", False))

# ----------------------------------------------------------------------------
# User classification
# ----------------------------------------------------------------------------


def _normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def is_offline_tester(username: str) -> bool:
    """Return True when the user is allowed to run offline using local storage."""

    normalized = _normalize_username(username)
    allowed_defaults = {_normalize_username(user) for user in OFFLINE_ALLOWED_USERS}
    allowed_dev = {_normalize_username(user) for user in DEV_SETTINGS.get("local_storage_testers", [])}
    return normalized in allowed_defaults or normalized in allowed_dev


def is_local_storage_user(username: str) -> bool:
    """Return True when the user can write results to local storage."""

    normalized = _normalize_username(username)
    allowed_defaults = {_normalize_username(user) for user in LOCAL_STORAGE_ALLOWED_USERS}
    allowed_dev = {_normalize_username(user) for user in DEV_SETTINGS.get("local_storage_testers", [])}
    allowed_offline = {_normalize_username(user) for user in OFFLINE_ALLOWED_USERS}
    return (
        normalized in allowed_defaults
        or normalized in allowed_dev
        or normalized in allowed_offline
        or is_dev_mode()
    )


IS_TESTER: bool = is_offline_tester(CURRENT_USER)

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
    """Update connectivity flags and active storage roots.

    ``server_online`` should reflect the real connectivity check. Developer
    overrides (force online/offline) are applied here so callers can always pass
    the real state and let this function decide the effective mode.
    """

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

    use_local = OFFLINE_MODE and is_local_storage_user(get_current_username())
    _determine_storage_paths(use_local)


def ensure_directories() -> None:
    """Create required directories based on current connection state.

    The function is intentionally defensive: when offline it silently skips
    paths that cannot be created (for example, unreachable UNC roots) instead of
    surfacing a traceback to the user.
    """

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
        if not path or not str(path).strip("\\/"):
            continue
        safe_path = make_long_path(path)
        if safe_path in {"\\\\?\\UNC\\", "\\\\?\\"}:
            continue
        try:
            os.makedirs(safe_path, exist_ok=True)
        except Exception as exc:
            if OFFLINE_MODE:
                logging.debug("Skipping directory creation while offline: %s (%s)", safe_path, exc)
                continue
            if is_dev_mode():
                logging.debug("Skipping directory creation in dev mode: %s (%s)", safe_path, exc)
                continue
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

    global DEV_SETTINGS, DEV_MODE, IS_TESTER
    DEV_SETTINGS = load_dev_settings_file()
    DEV_MODE = bool(DEV_SETTINGS.get("dev_mode", False))
    IS_TESTER = is_offline_tester(CURRENT_USER)
    _refresh_super_admins()


def is_dev_mode() -> bool:
    """Return True when developer mode is enabled."""

    return bool(DEV_SETTINGS.get("dev_mode", False))


def get_forced_server_state() -> str:
    return str(DEV_SETTINGS.get("force_server_state", "auto"))


def get_forced_role() -> str:
    return str(DEV_SETTINGS.get("force_role", "none"))


def get_forced_theme() -> str:
    theme = DEV_SETTINGS.get("override_theme")
    if theme is None:
        return "auto"
    return str(theme)


def get_forced_language() -> str:
    language = DEV_SETTINGS.get("override_language")
    if language is None:
        return "auto"
    return str(language)


def load_super_admins() -> set[str]:
    """Load super admin usernames from developer settings."""

    _refresh_super_admins()
    return SUPER_ADMIN_CACHE


def is_super_admin(username: str) -> bool:
    """Return True when the given username is configured as super admin."""

    normalized = _normalize_username(username)
    if not SUPER_ADMIN_CACHE:
        _refresh_super_admins()
    cache = {_normalize_username(user) for user in SUPER_ADMIN_CACHE}
    return normalized in cache


def ensure_server_directories() -> None:
    """Ensure configured directories exist if paths are available."""

    ensure_directories()


def initialize_environment() -> None:
    """Detect connectivity and prepare directories for the current user."""

    server_available = is_server_available(SERVER_ROOT)
    set_connection_state(server_available)

    if SERVER_ONLINE or IS_TESTER:
        ensure_directories()


# Initialize super admin cache on import
_refresh_super_admins()
APP_VERSION: str = "1.0.0"
# Path where the remote TXT with the latest version is published.
VERSION_INFO_PATH: str = os.path.join(SERVER_CONFIG_ROOT, "CompareSetVersion.txt")
