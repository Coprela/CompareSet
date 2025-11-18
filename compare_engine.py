#!/usr/bin/env python3
"""Compare SET desktop application with enhanced diff suppression.

Main adjustments in this step:
- Improve thin-line sensitivity by relaxing component thresholds and enhancing the
  dedicated line-boost stage so technical cut/dimension lines are preserved.
- Make unchanged-text suppression and movement pruning more conservative so
  small string edits (e.g., ASTM A37 → ASTM A36) are not discarded while still
  handling genuine shifts.
- Strengthen false-positive filtering via refined stable-region pruning and
  stricter overlap/mean-difference checks, while skipping expensive SSIM work
  when it brings little value for large pages. These changes speed up heavy
  drawings without sacrificing accuracy.
"""

from __future__ import annotations

import getpass
import logging
import math
import os
import shutil
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from importlib import util
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import cv2
import fitz
import numpy as np

# =============================================================================
# Pipeline configuration (internal constants)
# =============================================================================
BASE_RENDER_DPI = 200
ALLOW_NON_UNIFORM_SCALE = True
MAX_RENDER_WIDTH = 6000
MAX_RENDER_HEIGHT = 6000
DEBUG_PERFORMANCE = False

DPI = BASE_RENDER_DPI
DPI_HIGH = int(BASE_RENDER_DPI * 2)
BLUR_KSIZE = 3
THRESH = 28
ADAPTIVE_DIFF_STD_FACTOR = 0.6
ADAPTIVE_DIFF_MIN_INCREASE = 6.0
MORPH_KERNEL = 3
DILATE_ITERS = 1
ERODE_ITERS = 0
MIN_DIM = 1
MIN_DIFF_AREA = 20
MIN_LINE_LENGTH = 18
MIN_LINE_ASPECT_RATIO = 3.5
MERGE_IOU_THRESHOLD = 0.10
MERGE_CENTER_DIST_FACTOR = 0.5
PADDING_PX = 2
PADDING_FRAC = 0.01
VIEW_EXPAND = 1.04
VIEW_MAX_GROW = 12
MEAN_DIFF_MIN = 14.0
MEAN_TEXT_DIFF_MIN = 9.0
MIN_FORE_FRACTION = 0.18
MIN_FORE_FRACTION_LINE_BONUS = 0.12
WORD_IOU_MIN = 0.52
BASELINE_DELTA_MAX_PX = 4
WORD_SHIFT_TOLERANCE_PX = 5
ABSMEAN_MAX_UNCHANGED_TXT = 8.0
EDGE_OVERLAP_MIN = 0.92
LINE_MIN_LEN = 10
ECC_EPS = 1e-4
ECC_ITERS = 300
STROKE_WIDTH_PT = 1.1
STROKE_OPACITY = 0.55
RED = (1.0, 0.0, 0.0)
GREEN = (0.0, 1.0, 0.0)
DEBUG_DUMPS = False
PREVIEW_DPI = 100
MAX_CENTER_SHIFT_PX = 5.0
SIZE_TOLERANCE = 0.28
MIN_IOU_FOR_SAME = 0.55
MIN_PATCH_SSIM_FOR_SAME = 0.989
DIMMING_ENABLED = True
DIMMING_ALPHA = 0.4
DIMMING_MODE = "dark"
DIMMING_FEATHER = 2
PATCH_PAD = 2
DEBUG_MOVEMENT_SUPPRESSION = False
MAX_CANDIDATES_PER_REMOVED = 5
MAX_BOXES_FOR_MOVEMENT_SUPPRESSION = 1200
PATCH_SIM_SIZE = 48

MAX_COMPONENTS_PER_PAGE = 1600
MIN_COMPONENT_AREA = 6
LINE_LENGTH_THRESHOLD = 15


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


def is_server_available(server_root: str) -> bool:
    """Return True when the UNC server root exists and is reachable."""

    try:
        if not server_root or not server_root.strip():
            return False
        return os.path.exists(server_root)
    except Exception:
        return False


def set_connection_state(server_online: bool) -> None:
    """Update global flags and filesystem paths for the current connection state."""

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


set_connection_state(is_server_available(SERVER_ROOT))

USERS_DB_PATH = os.path.join(CONFIG_ROOT, "users.sqlite")
USER_SETTINGS_DB_PATH = os.path.join(CONFIG_ROOT, "user_settings.sqlite")
RELEASED_DB_PATH = os.path.join(CONFIG_ROOT, "released.sqlite")


_ssim_spec = util.find_spec("skimage.metrics")
if _ssim_spec is not None:  # pragma: no cover - optional dependency
    from skimage.metrics import structural_similarity  # type: ignore
else:  # pragma: no cover - optional dependency
    structural_similarity = None  # type: ignore

Rect = Tuple[float, float, float, float]
WordBox = Tuple[str, Rect, int]
Zoom = Union[float, Tuple[float, float]]


LOG_FILE: Optional[str] = None


def make_long_path(path: str) -> str:
    """Return a Windows long-path-safe absolute path."""

    abs_path = os.path.abspath(path)
    if abs_path.startswith("\\\\?\\"):
        return abs_path

    if abs_path.startswith("\\\\"):
        # UNC paths must use the special ``\\\\?\\UNC`` prefix to remain valid.
        # Simply pre-pending ``\\\\?\\`` would yield an invalid path such as
        # ``\\\\?\\server`` which Windows rejects (manifesting as ``\\`` when
        # ``os.makedirs`` recurses). By swapping the leading ``\\`` for
        # ``\\\\?\\UNC`` the resulting path stays usable while keeping long-path
        # support enabled. Example: ``\\\\server\\share`` -> ``\\\\?\\UNC\\server\\share``.
        return "\\\\?\\UNC" + abs_path[1:]

    return "\\\\?\\" + abs_path


def get_current_username() -> str:
    """Return the current Windows username for authentication."""

    return CURRENT_USER or os.getenv("USERNAME") or os.path.basename(os.path.expanduser("~"))


def ensure_server_directories() -> None:
    """Ensure all shared directories exist."""

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


def ensure_users_db_initialized() -> None:
    """Create the Users table if needed and seed an admin if empty."""

    ensure_server_directories()
    conn = sqlite3.connect(make_long_path(USERS_DB_PATH))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        cursor = conn.execute("SELECT COUNT(*) FROM Users")
        total = cursor.fetchone()[0]
        if total == 0:
            now = datetime.utcnow().isoformat()
            seed_user = get_current_username()
            conn.execute(
                "INSERT INTO Users (username, role, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (seed_user, "admin", 1, now, now),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_role(username: str) -> Optional[str]:
    """Return the active role for the given user, if any."""

    conn = sqlite3.connect(make_long_path(USERS_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT role, is_active FROM Users WHERE username = ?", (username,)
        ).fetchone()
        if row and row["is_active"]:
            return str(row["role"])
        return None
    finally:
        conn.close()


def list_users() -> List[Dict[str, Union[str, int]]]:
    """Return all users for admin display, including email if available."""

    ensure_user_settings_db_initialized()
    conn = sqlite3.connect(make_long_path(USERS_DB_PATH))
    settings_conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        settings_conn.row_factory = sqlite3.Row
        email_map = {
            row["username"]: row["email"]
            for row in settings_conn.execute("SELECT username, email FROM UserSettings")
        }
        rows = conn.execute("SELECT username, role, is_active FROM Users ORDER BY username").fetchall()
        return [
            {
                "username": row["username"],
                "role": row["role"],
                "is_active": int(row["is_active"]),
                "email": email_map.get(row["username"], ""),
            }
            for row in rows
        ]
    finally:
        settings_conn.close()
        conn.close()


def add_user(username: str, role: str) -> None:
    """Add a new active user entry."""

    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(make_long_path(USERS_DB_PATH))
    try:
        conn.execute(
            "INSERT INTO Users (username, role, is_active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
            (username.strip(), role, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def update_user_record(username: str, *, role: Optional[str] = None, is_active: Optional[int] = None) -> None:
    """Update role and/or activation state for a user."""

    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(make_long_path(USERS_DB_PATH))
    try:
        if role is not None:
            conn.execute(
                "UPDATE Users SET role = ?, updated_at = ? WHERE username = ?",
                (role, now, username),
            )
        if is_active is not None:
            conn.execute(
                "UPDATE Users SET is_active = ?, updated_at = ? WHERE username = ?",
                (is_active, now, username),
            )
        conn.commit()
    finally:
        conn.close()


def ensure_user_settings_db_initialized() -> None:
    """Create the user settings table when missing."""

    ensure_server_directories()
    conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS UserSettings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                language TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT "",
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # Backfill email column for existing deployments
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(UserSettings)").fetchall()
        }
        if "email" not in columns:
            conn.execute("ALTER TABLE UserSettings ADD COLUMN email TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def get_or_create_user_settings(username: str) -> Dict[str, str]:
    """Fetch or create settings for a user."""

    ensure_user_settings_db_initialized()
    conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT username, language, email FROM UserSettings WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            return {
                "username": row["username"],
                "language": row["language"],
                "email": row["email"],
            }
        now = datetime.utcnow().isoformat()
        default_language = "pt-BR"
        conn.execute(
            "INSERT INTO UserSettings (username, language, email, created_at, updated_at) VALUES (?, ?, '', ?, ?)",
            (username, default_language, now, now),
        )
        conn.commit()
        return {"username": username, "language": default_language, "email": ""}
    finally:
        conn.close()


def update_user_settings(username: str, **kwargs: str) -> None:
    """Update stored settings for a user."""

    ensure_user_settings_db_initialized()
    allowed_fields = {"language", "email"}
    updates = {key: value for key, value in kwargs.items() if key in allowed_fields}
    if not updates:
        return

    now = datetime.utcnow().isoformat()
    assignments = ", ".join(f"{field} = ?" for field in updates)
    values = list(updates.values())
    values.extend([now, username])

    conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.execute(
            f"UPDATE UserSettings SET {assignments}, updated_at = ? WHERE username = ?",
            tuple(values),
        )
        if conn.total_changes == 0:
            default_language = updates.get("language", "pt-BR")
            default_email = updates.get("email", "")
            conn.execute(
                "INSERT INTO UserSettings (username, language, email, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (username, default_language, default_email, now, now),
            )
        conn.commit()
    finally:
        conn.close()


def ensure_released_db_initialized() -> None:
    """Create the Released table if needed."""

    ensure_server_directories()
    conn = sqlite3.connect(make_long_path(RELEASED_DB_PATH))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Released (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                name_file_old TEXT NOT NULL,
                revision_old TEXT NOT NULL,
                name_file_new TEXT NOT NULL,
                revision_new TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_result TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def list_released_entries() -> List[Dict[str, str]]:
    """Return all released ECR metadata."""

    ensure_released_db_initialized()
    conn = sqlite3.connect(make_long_path(RELEASED_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT filename, name_file_old, revision_old, name_file_new, revision_new, created_by, created_at, source_result FROM Released ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def find_released_entry(filename: str) -> Optional[Dict[str, str]]:
    """Return an existing released entry by filename if present."""

    ensure_released_db_initialized()
    conn = sqlite3.connect(make_long_path(RELEASED_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT filename, name_file_old, revision_old, name_file_new, revision_new, created_by, created_at, source_result FROM Released WHERE filename = ?",
            (filename,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def record_released_entry(
    *,
    filename: str,
    name_file_old: str,
    revision_old: str,
    name_file_new: str,
    revision_new: str,
    created_by: str,
    source_result: str,
) -> None:
    """Insert or replace a released entry for the current user."""

    ensure_released_db_initialized()
    conn = sqlite3.connect(make_long_path(RELEASED_DB_PATH))
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO Released (filename, name_file_old, revision_old, name_file_new, revision_new, created_by, created_at, source_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                name_file_old=excluded.name_file_old,
                revision_old=excluded.revision_old,
                name_file_new=excluded.name_file_new,
                revision_new=excluded.revision_new,
                created_by=excluded.created_by,
                created_at=excluded.created_at,
                source_result=excluded.source_result
            """,
            (
                filename,
                name_file_old,
                revision_old,
                name_file_new,
                revision_new,
                created_by,
                now,
                source_result,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_released_entry(filename: str) -> None:
    """Remove an entry from the released registry."""

    ensure_released_db_initialized()
    conn = sqlite3.connect(make_long_path(RELEASED_DB_PATH))
    try:
        conn.execute("DELETE FROM Released WHERE filename = ?", (filename,))
        conn.commit()
    finally:
        conn.close()


class CancellationRequested(Exception):
    """Raised when the user requests cancellation."""



@dataclass
class TextGroup:
    """Representation of a grouped text run in page pixel coordinates."""

    text: str
    bbox: Rect


@dataclass
class PageDiffSummary:
    """Summary of results for a single page pair."""

    index: int
    alignment_method: str
    old_boxes_raw: int
    old_boxes_merged: int
    new_boxes_raw: int
    new_boxes_merged: int


@dataclass
class ComparisonResult:
    """Container for comparison output."""

    pdf_bytes: bytes
    server_result_path: Optional[str] = None
    summaries: List[PageDiffSummary] = field(default_factory=list)
    cancelled: bool = False


def init_log(base_name: str) -> str:
    """Initialize a crash-proof log file for the current execution."""

    global LOG_FILE

    if OFFLINE_MODE and CURRENT_USER not in OFFLINE_ALLOWED_USERS:
        LOG_FILE = None
        return ""

    ensure_server_directories()
    username = get_current_username()
    user_logs_dir = os.path.join(LOG_DIR, username)
    try:
        if SERVER_ONLINE:
            os.makedirs(make_long_path(user_logs_dir), exist_ok=True)
        else:
            os.makedirs(user_logs_dir, exist_ok=True)
    except Exception:
        LOG_FILE = None
        return ""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"ECR-{base_name}_{timestamp}_{username}.log"
    raw_path = os.path.join(user_logs_dir, filename)
    safe_path = make_long_path(raw_path) if SERVER_ONLINE else raw_path

    LOG_FILE = safe_path
    return safe_path


def write_log(message: str) -> None:
    """Append a message to the persistent log, flushing immediately."""

    if not LOG_FILE:
        return

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(message + "\n")
            handle.flush()
    except Exception:
        # Logging must not break the workflow.
        pass


def remove_signature_widgets(pdf_doc: fitz.Document) -> int:
    """Remove visible signature widgets so they do not affect rendering."""

    def _is_signature(annot: fitz.Annot) -> bool:
        if annot.type[0] != fitz.PDF_ANNOT_WIDGET:
            return False
        field_type = getattr(annot, "field_type", None)
        if field_type == getattr(fitz, "PDF_WIDGET_TYPE_SIG", None):
            return True
        type_string = str(getattr(annot, "field_type_string", "") or "").lower()
        return "sig" in type_string

    removed = 0
    for page_index in range(pdf_doc.page_count):
        page = pdf_doc.load_page(page_index)
        annots = list(page.annots() or [])
        for annot in annots:
            if _is_signature(annot):
                page.delete_annot(annot)
                removed += 1
    return removed


def build_output_filename(old_path: Path) -> str:
    """Create a timestamped output filename based on the first input."""

    base_name = old_path.stem or old_path.name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"ECR-{base_name}_{timestamp}.pdf"


def parse_result_filename(path: Path) -> Optional[Tuple[str, datetime]]:
    """Parse a result PDF filename into its base name and timestamp."""

    stem = path.stem
    if not stem.startswith("ECR-"):
        return None
    try:
        base_and_timestamp = stem[4:]
        base_name, timestamp_text = base_and_timestamp.rsplit("_", 1)
    except ValueError:
        return None
    try:
        timestamp = datetime.strptime(timestamp_text, "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return base_name, timestamp


def map_pdf_rect_to_pixels(rect: fitz.Rect, zoom: Zoom) -> Tuple[int, int, int, int]:
    """Map a PDF rectangle to pixel coordinates at the working DPI."""

    bounds = getattr(map_pdf_rect_to_pixels, "_bounds", None)
    page_width = page_height = None
    if bounds is not None:
        page_width, page_height = bounds

    zx, zy = zoom if isinstance(zoom, tuple) else (zoom, zoom)

    x0 = int(math.floor(rect.x0 * zx))
    y0 = int(math.floor(rect.y0 * zy))
    x1 = int(math.ceil(rect.x1 * zx))
    y1 = int(math.ceil(rect.y1 * zy))

    if page_width is not None and page_width > 0:
        x0 = max(0, min(x0, page_width - 1))
        x1 = max(x0 + 1, min(x1, page_width))
    else:
        x1 = max(x0 + 1, x1)

    if page_height is not None and page_height > 0:
        y0 = max(0, min(y0, page_height - 1))
        y1 = max(y0 + 1, min(y1, page_height))
    else:
        y1 = max(y0 + 1, y1)

    width = max(1, x1 - x0)
    height = max(1, y1 - y0)
    return x0, y0, width, height


def words_to_pixel_boxes(doc_page: fitz.Page, zoom: Zoom) -> List[WordBox]:
    """Extract word boxes from a PDF page and convert them to pixel space."""

    zx, zy = zoom if isinstance(zoom, tuple) else (zoom, zoom)

    page_rect = doc_page.rect
    page_width = int(round(page_rect.width * zx))
    page_height = int(round(page_rect.height * zy))
    results: List[WordBox] = []

    setattr(map_pdf_rect_to_pixels, "_bounds", (max(1, page_width), max(1, page_height)))
    try:
        for entry in doc_page.get_text("words"):
            if len(entry) < 5:
                continue
            x0, y0, x1, y1, word_text, *_ = entry
            if not word_text:
                continue
            text = str(word_text).strip()
            if not text:
                continue
            rect = fitz.Rect(float(x0), float(y0), float(x1), float(y1))
            px, py, w_box, h_box = map_pdf_rect_to_pixels(rect, zoom)
            if w_box <= 0 or h_box <= 0:
                continue
            bbox: Rect = (float(px), float(py), float(px + w_box), float(py + h_box))
            baseline = py + h_box
            if page_height > 0:
                baseline = min(baseline, page_height - 1)
            results.append((text, bbox, int(max(0, baseline))))
    finally:
        if hasattr(map_pdf_rect_to_pixels, "_bounds"):
            delattr(map_pdf_rect_to_pixels, "_bounds")

    return results


class PageProcessingResult:
    """Detailed results for a processed page pair."""

    alignment_method: str
    old_boxes: List[Rect]
    new_boxes: List[Rect]
    old_raw: int
    new_raw: int
    pixel_scale: float
    preview_skipped: bool = False


@dataclass
class PageTextGroups:
    """Text-group information for a page pair."""

    old_groups: List[TextGroup]
    new_groups: List[TextGroup]


def run_comparison(
    old_path: Path,
    new_path: Path,
    *,
    update_progress: Optional[Callable[[int, int], None]] = None,
    is_cancel_requested: Optional[Callable[[], bool]] = None,
) -> ComparisonResult:
    """Execute the raster diff comparison workflow."""

    update_progress = update_progress or (lambda _a, _b: None)
    is_cancel_requested = is_cancel_requested or (lambda: False)

    def _check_cancel() -> None:
        if is_cancel_requested():
            write_log("Cancellation requested; aborting run.")
            raise CancellationRequested()

    try:
        log_path = init_log(old_path.stem or old_path.name)
        configure_logging()
        username = get_current_username()
        user_results_dir = os.path.join(OUTPUT_DIR, username)
        if SERVER_ONLINE:
            os.makedirs(make_long_path(user_results_dir), exist_ok=True)
        else:
            os.makedirs(user_results_dir, exist_ok=True)
        result_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_name = f"ECR-{old_path.stem or old_path.name}_{result_timestamp}.pdf"
        result_path = os.path.join(user_results_dir, output_name)
        server_result_path = make_long_path(result_path) if SERVER_ONLINE else result_path
        write_log("=== CompareSet run started ===")
        write_log(f"User: {username}")
        write_log(f"Log file: {log_path}")
        write_log(f"Results directory: {server_result_path}")
        write_log(f"OLD file: {old_path}")
        write_log(f"NEW file: {new_path}")

        summaries: List[PageDiffSummary] = []
        output_doc = fitz.open()

        diff_found = False

        with fitz.open(old_path) as old_doc, fitz.open(new_path) as new_doc:
            if old_doc.page_count != new_doc.page_count:
                raise ValueError("OLD and NEW PDFs must have the same number of pages for comparison.")
            if old_doc.page_count == 0:
                raise ValueError("No pages available for comparison.")

            write_log(f"Total pages: {old_doc.page_count}")
            removed_old = remove_signature_widgets(old_doc)
            removed_new = remove_signature_widgets(new_doc)
            write_log(
                f"Signature widgets removed - OLD: {removed_old} NEW: {removed_new}"
            )

            for index in range(old_doc.page_count):
                _check_cancel()
                write_log(f"[Page {index + 1}] Rasterization start")
                page_start = time.perf_counter()
                old_page = old_doc.load_page(index)
                new_page = new_doc.load_page(index)
                result = process_page_pair(
                    old_page,
                    new_page,
                    index,
                    is_cancel_requested=is_cancel_requested,
                )
                write_log(
                    f"[Page {index + 1}] Rasterization complete in {time.perf_counter() - page_start:.3f}s"
                )

                if result.preview_skipped:
                    logger.info("Page %d alignment: %s", index + 1, result.alignment_method)
                    logger.info("Page %d: no change (preview)", index + 1)
                    write_log(f"[Page {index + 1}] Preview skip, no diffs")
                else:
                    logger.info("Page %d alignment: %s", index + 1, result.alignment_method)
                    if not result.old_boxes and not result.new_boxes:
                        logger.info("Page %d: No diffs detected.", index + 1)
                        write_log(f"[Page {index + 1}] No diffs detected")
                    else:
                        diff_found = True
                        logger.info(
                            "Page %d OLD boxes: raw=%d merged=%d",
                            index + 1,
                            result.old_raw,
                            len(result.old_boxes),
                        )
                        logger.info(
                            "Page %d NEW boxes: raw=%d merged=%d",
                            index + 1,
                            result.new_raw,
                            len(result.new_boxes),
                        )
                        write_log(
                            f"[Page {index + 1}] Boxes OLD raw={result.old_raw} merged={len(result.old_boxes)}"
                        )
                        write_log(
                            f"[Page {index + 1}] Boxes NEW raw={result.new_raw} merged={len(result.new_boxes)}"
                        )

                old_insert_index: Optional[int] = None
                new_insert_index: Optional[int] = None

                try:
                    if 0 <= index < old_doc.page_count:
                        old_insert_index = output_doc.page_count
                        output_doc.insert_pdf(
                            old_doc,
                            from_page=index,
                            to_page=min(index, old_doc.page_count - 1),
                            start_at=old_insert_index,
                        )

                    if 0 <= index < new_doc.page_count:
                        new_insert_index = output_doc.page_count
                        output_doc.insert_pdf(
                            new_doc,
                            from_page=index,
                            to_page=min(index, new_doc.page_count - 1),
                            start_at=new_insert_index,
                        )
                except IndexError:
                    write_log(
                        f"[Page {index + 1}] Insert PDF failed due to invalid page range"
                    )
                    logger.exception("Insert PDF failed")
                    continue

                write_log(f"[Page {index + 1}] Spotlight rendering")
                if old_insert_index is not None and result.old_boxes:
                    old_page_out = output_doc.load_page(old_insert_index)
                    apply_dimming_overlay(old_page_out, result.old_boxes, result.pixel_scale)
                    for rect in result.old_boxes:
                        pdf_rect = fitz.Rect(
                            rect[0] / result.pixel_scale,
                            rect[1] / result.pixel_scale,
                            rect[2] / result.pixel_scale,
                            rect[3] / result.pixel_scale,
                        )
                        old_page_out.draw_rect(
                            pdf_rect,
                            color=RED,
                            fill=None,
                            width=STROKE_WIDTH_PT,
                            stroke_opacity=STROKE_OPACITY,
                        )

                if new_insert_index is not None and result.new_boxes:
                    new_page_out = output_doc.load_page(new_insert_index)
                    apply_dimming_overlay(new_page_out, result.new_boxes, result.pixel_scale)
                    for rect in result.new_boxes:
                        pdf_rect = fitz.Rect(
                            rect[0] / result.pixel_scale,
                            rect[1] / result.pixel_scale,
                            rect[2] / result.pixel_scale,
                            rect[3] / result.pixel_scale,
                        )
                        new_page_out.draw_rect(
                            pdf_rect,
                            color=GREEN,
                            fill=None,
                            width=STROKE_WIDTH_PT,
                            stroke_opacity=STROKE_OPACITY,
                        )

                write_log(f"[Page {index + 1}] Page output complete")
                summaries.append(
                    PageDiffSummary(
                        index=index + 1,
                        alignment_method=result.alignment_method,
                        old_boxes_raw=result.old_raw,
                        old_boxes_merged=len(result.old_boxes),
                        new_boxes_raw=result.new_raw,
                        new_boxes_merged=len(result.new_boxes),
                    )
                )
                update_progress(index + 1, old_doc.page_count)

        if not diff_found:
            logger.info("No diffs")

        output_pages = output_doc.page_count
        pdf_bytes = output_doc.tobytes()
        output_doc.close()
        with open(server_result_path, "wb") as output_handle:
            output_handle.write(pdf_bytes)
        logger.info("Generated diff with %d page pair(s).", len(summaries))
        logger.info("Output document pages: %d", output_pages)
        write_log("Comparison finished successfully")
        return ComparisonResult(
            pdf_bytes=pdf_bytes, server_result_path=server_result_path, summaries=summaries
        )
    except CancellationRequested:
        write_log("Comparison cancelled by user")
        return ComparisonResult(pdf_bytes=b"", summaries=[], cancelled=True)
    except Exception:
        exc_text = traceback.format_exc()
        write_log("Exception during comparison:")
        write_log(exc_text)

        try:
            if SERVER_ONLINE:
                os.makedirs(make_long_path(ERROR_LOGS_ROOT), exist_ok=True)
            else:
                os.makedirs(ERROR_LOGS_ROOT, exist_ok=True)
            base_name = old_path.stem or old_path.name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            username = get_current_username()
            error_filename = f"ECR_ERROR-{base_name}_{timestamp}_{username}.txt"
            raw_error_path = os.path.join(ERROR_LOGS_ROOT, error_filename)
            error_path = make_long_path(raw_error_path) if SERVER_ONLINE else raw_error_path
            if LOG_FILE and os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "a", encoding="utf-8") as handle:
                        handle.flush()
                        os.fsync(handle.fileno())
                except Exception:
                    pass
                shutil.copyfile(LOG_FILE, error_path)
        except Exception:
            pass
        raise


def process_page_pair(
    old_page: fitz.Page,
    new_page: fitz.Page,
    page_index: int,
    *,
    is_cancel_requested: Optional[Callable[[], bool]] = None,
) -> PageProcessingResult:
    """Process a pair of pages and return rectangles for old/new differences."""

    perf_start = time.perf_counter()
    cancel_check = is_cancel_requested or (lambda: False)

    def _check_cancel() -> None:
        if cancel_check():
            write_log(f"[Page {page_index + 1}] Cancellation requested")
            raise CancellationRequested()

    _check_cancel()
    write_log(f"[Page {page_index + 1}] High-DPI render start")
    old_high, new_high, old_zoom_high, new_zoom_high_x, new_zoom_high_y = render_normalized_pages(
        old_page, new_page, DPI_HIGH
    )
    perf_after_render = time.perf_counter()
    write_log(
        f"[Page {page_index + 1}] High-DPI render complete in {perf_after_render - perf_start:.3f}s"
    )

    preview_zoom = compute_zoom(old_page.rect, PREVIEW_DPI)
    preview_scale = preview_zoom / old_zoom_high if old_zoom_high else 1.0
    preview_old = downsample_to_working_resolution(old_high, scale_factor=preview_scale)
    preview_new = downsample_to_working_resolution(new_high, scale_factor=preview_scale)
    perf_after_preview = time.perf_counter()
    preview_diff = cv2.absdiff(preview_old, preview_new)
    _, preview_mask = cv2.threshold(preview_diff, 20, 255, cv2.THRESH_BINARY)
    nonzero_ratio = float(cv2.countNonZero(preview_mask)) / float(preview_mask.size or 1)
    preview_mean = float(preview_diff.mean()) if preview_diff.size else 0.0
    if nonzero_ratio < 0.00035 and preview_mean < 3.5:
        logger.info("unchanged-text suppressed: 0 on OLD, 0 on NEW")
        write_log(f"[Page {page_index + 1}] Preview skip after {perf_after_preview - perf_after_render:.3f}s")
        return PageProcessingResult(
            alignment_method="preview_skip",
            old_boxes=[],
            new_boxes=[],
            old_raw=0,
            new_raw=0,
            pixel_scale=old_zoom_high,
            preview_skipped=True,
        )

    _check_cancel()
    aligned_new_high, alignment_method, warp_matrix = align_images(old_high, new_high)
    perf_after_align = time.perf_counter()
    write_log(
        f"[Page {page_index + 1}] Alignment ({alignment_method}) completed in {perf_after_align - perf_after_preview:.3f}s"
    )

    _check_cancel()
    write_log(f"[Page {page_index + 1}] Diff mask creation")
    blur_old = cv2.GaussianBlur(old_high, (BLUR_KSIZE, BLUR_KSIZE), 0)
    blur_new = cv2.GaussianBlur(aligned_new_high, (BLUR_KSIZE, BLUR_KSIZE), 0)

    diff = cv2.absdiff(blur_old, blur_new)

    intensity_mask = compute_intensity_mask(diff)
    edge_old, edge_new, edge_mask = compute_edge_mask(blur_old, blur_new)
    line_boost = compute_line_boost(diff)
    line_emphasis = cv2.dilate(
        line_boost, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1
    )

    change_mask = cv2.bitwise_and(intensity_mask, cv2.bitwise_or(edge_mask, line_emphasis))

    ssim_mask = compute_ssim_mask(blur_old, blur_new)
    if ssim_mask is not None:
        change_mask = cv2.bitwise_and(change_mask, ssim_mask)

    _, old_ink = cv2.threshold(blur_old, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, new_ink = cv2.threshold(blur_new, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    old_bin = (old_ink > 0).astype(np.uint8)
    new_bin = (new_ink > 0).astype(np.uint8)

    removed_mask = np.where(np.logical_and(old_bin == 1, new_bin == 0), 255, 0).astype(np.uint8)
    added_mask = np.where(np.logical_and(new_bin == 1, old_bin == 0), 255, 0).astype(np.uint8)

    ink_union = cv2.bitwise_or(old_ink, new_ink)
    change_mask = cv2.bitwise_and(change_mask, ink_union)

    # Ensure thin line work is not suppressed by intensity gating and preserve added / removed ink explicitly.
    change_mask = cv2.bitwise_or(
        change_mask,
        cv2.bitwise_or(removed_mask, added_mask),
    )
    change_mask = cv2.bitwise_or(change_mask, cv2.bitwise_and(line_emphasis, ink_union))

    _check_cancel()
    write_log(f"[Page {page_index + 1}] Bounding box extraction")
    groups = prepare_page_text_groups(
        old_page,
        new_page,
        warp_matrix,
        old_zoom_high,
        (new_zoom_high_x, new_zoom_high_y),
        1.0,
    )
    words_old = words_to_pixel_boxes(old_page, old_zoom_high)
    words_new_high = words_to_pixel_boxes(new_page, (new_zoom_high_x, new_zoom_high_y))
    words_new = align_word_boxes(words_new_high, warp_matrix, 1.0)

    detection_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    removed_detection = cv2.dilate(removed_mask, detection_kernel, iterations=1)
    added_detection = cv2.dilate(added_mask, detection_kernel, iterations=1)

    removed_regions = cv2.bitwise_and(change_mask, removed_detection)
    added_regions = cv2.bitwise_and(change_mask, added_detection)

    line_diff_mask = cv2.bitwise_xor(edge_old, edge_new)
    line_diff_mask = cv2.dilate(
        line_diff_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1
    )
    bridge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    change_mask = cv2.morphologyEx(change_mask, cv2.MORPH_CLOSE, bridge_kernel, iterations=1)
    line_removed_regions = cv2.bitwise_and(line_diff_mask, removed_detection)
    line_added_regions = cv2.bitwise_and(line_diff_mask, added_detection)

    old_filtered_main, old_kept_main, old_raw_components, old_after_noise = extract_regions(
        removed_regions,
        diff,
        old_high,
        old_ink,
        groups.old_groups,
        groups.new_groups,
        edge_old,
        edge_new,
        line_boost,
        "old",
    )
    new_filtered_main, new_kept_main, new_raw_components, new_after_noise = extract_regions(
        added_regions,
        diff,
        aligned_new_high,
        new_ink,
        groups.old_groups,
        groups.new_groups,
        edge_old,
        edge_new,
        line_boost,
        "new",
    )

    old_line_filtered, old_line_kept, old_line_raw, old_line_after_noise = extract_regions(
        line_removed_regions,
        diff,
        old_high,
        old_ink,
        groups.old_groups,
        groups.new_groups,
        edge_old,
        edge_new,
        line_boost,
        "old_line",
    )
    new_line_filtered, new_line_kept, new_line_raw, new_line_after_noise = extract_regions(
        line_added_regions,
        diff,
        aligned_new_high,
        new_ink,
        groups.old_groups,
        groups.new_groups,
        edge_old,
        edge_new,
        line_boost,
        "new_line",
    )

    old_filtered = old_filtered_main + old_line_filtered
    new_filtered = new_filtered_main + new_line_filtered
    perf_after_regions = time.perf_counter()
    write_log(f"[Page {page_index + 1}] Regions extracted in {perf_after_regions - perf_after_align:.3f}s")
    write_log(
        f"[Page {page_index + 1}] OLD components raw={old_raw_components + old_line_raw} after_noise={old_after_noise + old_line_after_noise} kept={len(old_filtered)} (main {old_kept_main}, line {old_line_kept})"
    )
    write_log(
        f"[Page {page_index + 1}] NEW components raw={new_raw_components + new_line_raw} after_noise={new_after_noise + new_line_after_noise} kept={len(new_filtered)} (main {new_kept_main}, line {new_line_kept})"
    )

    _check_cancel()
    write_log(f"[Page {page_index + 1}] Rectangle merging")
    old_raw = len(old_filtered)
    new_raw = len(new_filtered)
    old_boxes = merge_close_rectangles(merge_rectangles(old_filtered))
    new_boxes = merge_close_rectangles(merge_rectangles(new_filtered))

    write_log(f"[Page {page_index + 1}] Unchanged text suppression")
    old_boxes, suppressed_old = suppress_unchanged_text(
        old_boxes,
        diff,
        edge_old,
        edge_new,
        words_old,
        words_new,
    )
    new_boxes, suppressed_new = suppress_unchanged_text(
        new_boxes,
        diff,
        edge_old,
        edge_new,
        words_old,
        words_new,
    )

    old_boxes, overlap_suppressed = drop_overlapping_removals(old_boxes, new_boxes)
    write_log(f"[Page {page_index + 1}] Movement suppression (geometry/SSIM)")
    old_boxes, new_boxes, movement_suppressed = suppress_moved_pairs(
        old_boxes, new_boxes, old_high, aligned_new_high
    )
    write_log(f"[Page {page_index + 1}] Movement suppression removed {movement_suppressed} pairs")

    old_boxes, new_boxes, text_shift_suppressed = suppress_identical_text_pairs(
        old_boxes, new_boxes, words_old, words_new
    )
    write_log(f"[Page {page_index + 1}] Text-based movement suppression removed {text_shift_suppressed} pairs")

    old_boxes, new_boxes, identical_text_suppressed = filter_identical_text_regions(
        old_boxes, new_boxes, words_old, words_new
    )
    write_log(f"[Page {page_index + 1}] Text filter removed {identical_text_suppressed} regions")

    old_boxes, old_stable = drop_stable_regions(
        old_boxes, diff, old_high, aligned_new_high, similarity_cutoff=0.995
    )
    new_boxes, new_stable = drop_stable_regions(
        new_boxes, diff, aligned_new_high, old_high, similarity_cutoff=0.995
    )
    write_log(
        f"[Page {page_index + 1}] Stable-region pruning removed old={old_stable} new={new_stable}"
    )

    logger.info(
        "unchanged-text suppressed: %d on OLD, %d on NEW",
        suppressed_old,
        suppressed_new,
    )
    if overlap_suppressed:
        logger.info("overlap-pruned removals: %d", overlap_suppressed)
    if movement_suppressed:
        logger.info("movement-pruned pairs: %d", movement_suppressed)
    if text_shift_suppressed:
        logger.info("text-based movement suppression: %d", text_shift_suppressed)
    if identical_text_suppressed:
        logger.info("text filter removed regions: %d", identical_text_suppressed)

    if DEBUG_PERFORMANCE:
        logger.info(
            "performance page %d: render=%.3fs preview=%.3fs align=%.3fs regions=%.3fs",
            getattr(old_page, "number", -1) + 1,
            perf_after_render - perf_start,
            perf_after_preview - perf_after_render,
            perf_after_align - perf_after_preview,
            perf_after_regions - perf_after_align,
        )

    _check_cancel()
    return PageProcessingResult(
        alignment_method=alignment_method,
        old_boxes=old_boxes,
        new_boxes=new_boxes,
        old_raw=old_raw,
        new_raw=new_raw,
        pixel_scale=old_zoom_high,
    )


def compute_zoom(rect: fitz.Rect, dpi: int) -> float:
    """Compute a DPI-based zoom while clamping to configured pixel limits."""

    base_zoom = dpi / 72.0
    max_zoom_w = MAX_RENDER_WIDTH / rect.width if rect.width > 0 else base_zoom
    max_zoom_h = MAX_RENDER_HEIGHT / rect.height if rect.height > 0 else base_zoom
    return max(1e-3, min(base_zoom, max_zoom_w, max_zoom_h))


def render_page_to_gray(page: fitz.Page, scale_x: float, scale_y: Optional[float] = None) -> np.ndarray:
    """Render a page to a grayscale numpy array using explicit scaling."""

    sy = scale_y if scale_y is not None else scale_x
    matrix = fitz.Matrix(scale_x, sy)
    pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
    array = np.frombuffer(pix.samples, dtype=np.uint8)
    return array.reshape(pix.height, pix.width)


def render_normalized_pages(
    old_page: fitz.Page, new_page: fitz.Page, dpi: int
) -> Tuple[np.ndarray, np.ndarray, float, float, float]:
    """Render both pages to the same pixel size based on the OLD page."""

    old_zoom = compute_zoom(old_page.rect, dpi)
    scale_x = old_page.rect.width / new_page.rect.width if new_page.rect.width else 1.0
    scale_y = old_page.rect.height / new_page.rect.height if new_page.rect.height else 1.0
    if not ALLOW_NON_UNIFORM_SCALE:
        uniform = min(scale_x, scale_y)
        scale_x = scale_y = uniform

    new_zoom_x = old_zoom * scale_x
    new_zoom_y = old_zoom * scale_y

    old_img = render_page_to_gray(old_page, old_zoom)
    new_img = render_page_to_gray(new_page, new_zoom_x, new_zoom_y)

    target_width, target_height = old_img.shape[1], old_img.shape[0]
    if new_img.shape[0] != target_height or new_img.shape[1] != target_width:
        new_img = cv2.resize(new_img, (target_width, target_height), interpolation=cv2.INTER_AREA)

    return old_img, new_img, old_zoom, new_zoom_x, new_zoom_y


def align_images(old_img: np.ndarray, new_img: np.ndarray) -> Tuple[np.ndarray, str, np.ndarray]:
    """Align images using hierarchical ECC with fallbacks."""

    scale = 0.5
    target_size = (
        max(1, int(round(old_img.shape[1] * scale))),
        max(1, int(round(old_img.shape[0] * scale))),
    )
    old_small = cv2.resize(old_img, target_size, interpolation=cv2.INTER_AREA)
    new_small = cv2.resize(new_img, target_size, interpolation=cv2.INTER_AREA)

    old_norm = old_small.astype(np.float32) / 255.0
    new_norm = new_small.astype(np.float32) / 255.0

    best_cc = -1.0
    best_warp: Optional[np.ndarray] = None
    best_method = ""

    def try_ecc(mode: int, iterations: int) -> Tuple[float, Optional[np.ndarray]]:
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            iterations,
            ECC_EPS,
        )
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            cc, warp = cv2.findTransformECC(old_norm, new_norm, warp, mode, criteria)
        except cv2.error:
            return -1.0, None
        return float(cc), warp

    cc, warp = try_ecc(cv2.MOTION_EUCLIDEAN, ECC_ITERS)
    if warp is not None:
        best_cc, best_warp, best_method = cc, warp, "euclidean_ecc"
    if best_cc < 0.90:
        cc_affine, warp_affine = try_ecc(cv2.MOTION_AFFINE, 200)
        if warp_affine is not None and cc_affine > best_cc:
            best_cc, best_warp, best_method = cc_affine, warp_affine, "affine_ecc"

    scale_factor = old_img.shape[1] / float(target_size[0]) if target_size[0] else 1.0

    if best_warp is None:
        shift, _ = cv2.phaseCorrelate(old_norm, new_norm)
        warp_matrix = np.array(
            [[1.0, 0.0, shift[0] * scale_factor], [0.0, 1.0, shift[1] * scale_factor]],
            dtype=np.float32,
        )
        aligned = cv2.warpAffine(
            new_img,
            warp_matrix,
            (old_img.shape[1], old_img.shape[0]),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_REFLECT,
        )
        return aligned, "phase_correlation", warp_matrix

    warp_matrix = best_warp.copy()
    warp_matrix[0, 2] *= scale_factor
    warp_matrix[1, 2] *= scale_factor

    aligned = cv2.warpAffine(
        new_img,
        warp_matrix,
        (old_img.shape[1], old_img.shape[0]),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REFLECT,
    )
    return aligned, f"{best_method}:{best_cc:.3f}", warp_matrix


def downsample_to_working_resolution(
    image: np.ndarray, *, scale_factor: Optional[float] = None, target_size: Optional[Tuple[int, int]] = None
) -> np.ndarray:
    """Downsample the high DPI image to the working DPI using area resampling."""

    if target_size is None:
        factor = scale_factor if scale_factor is not None else (DPI / DPI_HIGH)
        target_width = int(round(image.shape[1] * factor))
        target_height = int(round(image.shape[0] * factor))
    else:
        target_width, target_height = target_size
    target_width = max(1, target_width)
    target_height = max(1, target_height)
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def compute_intensity_mask(diff: np.ndarray) -> np.ndarray:
    """Compute the intensity-based change mask."""

    mean_val = float(diff.mean())
    std_val = float(diff.std())
    adaptive = mean_val + std_val * ADAPTIVE_DIFF_STD_FACTOR + ADAPTIVE_DIFF_MIN_INCREASE
    threshold_value = max(THRESH, adaptive)
    _, coarse = cv2.threshold(diff, threshold_value, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (MORPH_KERNEL, MORPH_KERNEL))
    coarse = cv2.morphologyEx(coarse, cv2.MORPH_CLOSE, kernel)
    if DILATE_ITERS:
        coarse = cv2.dilate(coarse, kernel, iterations=DILATE_ITERS)
    if ERODE_ITERS:
        coarse = cv2.erode(coarse, kernel, iterations=ERODE_ITERS)
    if std_val < 4.0:
        cleaner = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        coarse = cv2.morphologyEx(coarse, cv2.MORPH_OPEN, cleaner)
    return coarse


def compute_edge_mask(old_img: np.ndarray, new_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute edge representations and a mask highlighting structural changes."""

    grad_old_x = cv2.Scharr(old_img, cv2.CV_32F, 1, 0)
    grad_old_y = cv2.Scharr(old_img, cv2.CV_32F, 0, 1)
    grad_new_x = cv2.Scharr(new_img, cv2.CV_32F, 1, 0)
    grad_new_y = cv2.Scharr(new_img, cv2.CV_32F, 0, 1)

    mag_old = cv2.magnitude(grad_old_x, grad_old_y)
    mag_new = cv2.magnitude(grad_new_x, grad_new_y)

    mag_old_u8 = cv2.convertScaleAbs(mag_old)
    mag_new_u8 = cv2.convertScaleAbs(mag_new)

    _, edge_old = cv2.threshold(mag_old_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, edge_new = cv2.threshold(mag_new_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    edge_diff = cv2.absdiff(edge_old, edge_new)
    edge_mask = np.where(edge_diff > 0, 255, 0).astype(np.uint8)
    return edge_old, edge_new, edge_mask


def compute_line_boost(diff_img: np.ndarray) -> np.ndarray:
    """Enhance thin-line differences using anisotropic closings."""

    # Use a lower Canny threshold to preserve faint strokes, then close in
    # horizontal/vertical directions to reconnect dashed or very thin cuts.
    canny = cv2.Canny(diff_img, 20, 70)
    kx = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))
    ky = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
    close_x = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, kx)
    close_y = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, ky)
    merged = cv2.max(close_x, close_y)
    # A light dilation strengthens single-pixel traces without ballooning boxes.
    dilated = cv2.dilate(merged, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)), iterations=1)
    return dilated


def compute_ssim_mask(old_img: np.ndarray, new_img: np.ndarray) -> Optional[np.ndarray]:
    """Optional SSIM-based refinement mask."""

    if structural_similarity is None:
        return None
    # Skip SSIM when images are extremely large to avoid heavy CPU cost; the
    # subsequent patch-similarity pruning will handle stability checks.
    if old_img.size > 5_000_000 or new_img.size > 5_000_000:
        return None
    try:
        reduced_old = cv2.resize(old_img, (0, 0), fx=0.45, fy=0.45, interpolation=cv2.INTER_AREA)
        reduced_new = cv2.resize(new_img, (0, 0), fx=0.45, fy=0.45, interpolation=cv2.INTER_AREA)
        _, ssim_map = structural_similarity(reduced_old, reduced_new, full=True)
    except Exception:  # pragma: no cover - optional dependency runtime errors
        return None

    diff_map = np.clip((1.0 - ssim_map) * 255.0, 0, 255).astype(np.uint8)
    upsampled = cv2.resize(diff_map, (old_img.shape[1], old_img.shape[0]), interpolation=cv2.INTER_LINEAR)
    _, mask = cv2.threshold(upsampled, THRESH, 255, cv2.THRESH_BINARY)
    return mask


def prepare_page_text_groups(
    old_page: fitz.Page,
    new_page: fitz.Page,
    warp_matrix: np.ndarray,
    old_scale: float,
    new_scales: Tuple[float, float],
    scale_factor: float,
) -> PageTextGroups:
    """Extract grouped text runs for both pages and align the new groups."""

    old_groups = extract_text_groups(old_page, old_scale, old_scale)
    new_high_groups = extract_text_groups(new_page, new_scales[0], new_scales[1])

    aligned_new: List[TextGroup] = []
    for group in new_high_groups:
        transformed = transform_rect(group.bbox, warp_matrix)
        scaled = tuple(coord * scale_factor for coord in transformed)
        aligned_new.append(TextGroup(group.text, scaled))

    return PageTextGroups(old_groups=old_groups, new_groups=aligned_new)


def align_word_boxes(words: Sequence[WordBox], warp_matrix: np.ndarray, scale_factor: float) -> List[WordBox]:
    """Align new-page word boxes to the old page coordinate space."""

    aligned: List[WordBox] = []
    for text, rect, _baseline in words:
        transformed = transform_rect(rect, warp_matrix)
        scaled = tuple(coord * scale_factor for coord in transformed)
        baseline = int(round(max(0.0, scaled[3])))
        aligned.append((text, (scaled[0], scaled[1], scaled[2], scaled[3]), baseline))
    return aligned


def extract_text_groups(page: fitz.Page, scale_x: float, scale_y: Optional[float] = None) -> List[TextGroup]:
    """Extract grouped text regions from a PDF page at the specified scale."""

    text = page.get_text("rawdict")
    scale_y_val = scale_y if scale_y is not None else scale_x
    groups: List[TextGroup] = []
    for block in text.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                current_text: List[str] = []
                min_x, min_y = float("inf"), float("inf")
                max_x, max_y = float("-inf"), float("-inf")
                for char in span.get("chars", []):
                    c = char.get("c")
                    bbox = char.get("bbox")
                    if c is None or bbox is None:
                        continue
                    if c.isspace():
                        if current_text:
                            groups.append(
                                TextGroup(
                                    "".join(current_text),
                                    (
                                        min_x * scale_x,
                                        min_y * scale_y_val,
                                        max_x * scale_x,
                                        max_y * scale_y_val,
                                    ),
                                )
                            )
                            current_text = []
                            min_x, min_y = float("inf"), float("inf")
                            max_x, max_y = float("-inf"), float("-inf")
                        continue
                    x0, y0, x1, y1 = bbox
                    current_text.append(c)
                    min_x = min(min_x, x0)
                    min_y = min(min_y, y0)
                    max_x = max(max_x, x1)
                    max_y = max(max_y, y1)
                if current_text:
                    groups.append(
                        TextGroup(
                            "".join(current_text),
                            (
                                min_x * scale_x,
                                min_y * scale_y_val,
                                max_x * scale_x,
                                max_y * scale_y_val,
                            ),
                        )
                    )
    return groups


def transform_rect(rect: Rect, matrix: np.ndarray) -> Rect:
    """Apply an affine transform to a rectangle and return its axis-aligned bounds."""

    points = np.array(
        [
            [rect[0], rect[1], 1.0],
            [rect[2], rect[1], 1.0],
            [rect[0], rect[3], 1.0],
            [rect[2], rect[3], 1.0],
        ],
        dtype=np.float32,
    )
    transformed = (matrix @ points.T).T
    xs = transformed[:, 0]
    ys = transformed[:, 1]
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def extract_regions(
    mask: np.ndarray,
    diff_img: np.ndarray,
    base_img: np.ndarray,
    ink_mask: np.ndarray,
    old_groups: Sequence[TextGroup],
    new_groups: Sequence[TextGroup],
    edge_old: np.ndarray,
    edge_new: np.ndarray,
    line_boost: np.ndarray,
    label: str,
) -> Tuple[List[Rect], int, int, int]:
    """Extract filtered bounding boxes from a binary mask."""

    if mask is None or not np.any(mask):
        return [], 0, 0, 0

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    height, width = mask.shape
    rectangles: List[Rect] = []
    pad = max(PADDING_PX, int(min(width, height) * PADDING_FRAC))
    global_std = 0.0
    try:
        _, std = cv2.meanStdDev(diff_img)
        global_std = float(std[0][0]) if std is not None else 0.0
    except Exception:
        global_std = 0.0

    kernel = np.ones((3, 3), np.uint8)
    raw_components = list(range(1, num_labels))
    filtered_indices: List[int] = []

    for label_idx in raw_components:
        x = stats[label_idx, cv2.CC_STAT_LEFT]
        y = stats[label_idx, cv2.CC_STAT_TOP]
        w_box = stats[label_idx, cv2.CC_STAT_WIDTH]
        h_box = stats[label_idx, cv2.CC_STAT_HEIGHT]

        area = w_box * h_box
        longest_side = max(w_box, h_box)
        aspect_ratio = longest_side / float(max(1, min(w_box, h_box)))
        is_thin_line = (
            aspect_ratio >= MIN_LINE_ASPECT_RATIO and longest_side >= MIN_LINE_LENGTH
        )

        if (area < MIN_COMPONENT_AREA and longest_side < LINE_LENGTH_THRESHOLD and not is_thin_line) or w_box < MIN_DIM or h_box < MIN_DIM:
            continue

        filtered_indices.append(label_idx)

    logger.info(
        "%s components raw=%d after_noise=%d", label, len(raw_components), len(filtered_indices)
    )

    if len(filtered_indices) > MAX_COMPONENTS_PER_PAGE:
        filtered_indices.sort(key=lambda idx: stats[idx, cv2.CC_STAT_AREA], reverse=True)
        kept = filtered_indices[:MAX_COMPONENTS_PER_PAGE]
        logger.info(
            "%s regions truncated: kept %d of %d components (after noise filter)",
            label,
            len(kept),
            len(filtered_indices),
        )
        filtered_indices = kept

    for label_idx in filtered_indices:
        x = stats[label_idx, cv2.CC_STAT_LEFT]
        y = stats[label_idx, cv2.CC_STAT_TOP]
        w_box = stats[label_idx, cv2.CC_STAT_WIDTH]
        h_box = stats[label_idx, cv2.CC_STAT_HEIGHT]

        component_mask = np.where(labels == label_idx, 255, 0).astype(np.uint8)

        raw_rect = (x, y, x + w_box, y + h_box)

        region = base_img[y : y + h_box, x : x + w_box]
        std_val = 0.0
        if region.size:
            _, stddev = cv2.meanStdDev(region)
            std_val = float(stddev[0][0])

        mean_val = cv2.mean(diff_img, mask=component_mask)[0]
        mean_threshold = MEAN_DIFF_MIN * (0.6 if is_thin_line or line_boost is not None else 1.0)
        cx1 = max(0, x - pad * 2)
        cy1 = max(0, y - pad * 2)
        cx2 = min(width, x + w_box + pad * 2)
        cy2 = min(height, y + h_box + pad * 2)
        context_mask = np.zeros_like(mask)
        context_mask[cy1:cy2, cx1:cx2] = 255
        context_mean = cv2.mean(diff_img, mask=context_mask)[0]
        adaptive_delta = mean_threshold - min(mean_threshold * 0.25, global_std * 0.6)
        if std_val < 2.0 and mean_val < mean_threshold and not line_evidence:
            continue

        glyph_match = is_identical_text_region(
            raw_rect,
            old_groups,
            new_groups,
            component_mask,
            diff_img,
            edge_old,
            edge_new,
            kernel,
        )
        if glyph_match:
            continue
        line_region = cv2.bitwise_and(component_mask, line_boost)
        has_line_pixels = cv2.countNonZero(line_region) > 0
        line_evidence = False
        if has_line_pixels:
            try:
                lines = cv2.HoughLinesP(
                    line_region,
                    1.0,
                    np.pi / 180.0,
                    threshold=12,
                    minLineLength=LINE_MIN_LEN,
                    maxLineGap=6,
                )
                line_evidence = lines is not None and len(lines) > 0
            except cv2.error:
                line_evidence = False

        if mean_val < mean_threshold and not line_evidence:
            continue
        if (mean_val - context_mean) < adaptive_delta and not line_evidence:
            continue

        foreground = cv2.bitwise_and(component_mask, ink_mask)
        if area == 0:
            continue
        fore_fraction = float(cv2.countNonZero(foreground)) / float(area)
        fore_cutoff = MIN_FORE_FRACTION
        if line_evidence or is_thin_line:
            fore_cutoff = min(fore_cutoff, MIN_FORE_FRACTION_LINE_BONUS)
        if fore_fraction < fore_cutoff and not line_evidence:
            continue

        short_side = max(1, min(w_box, h_box))
        aspect_ratio = max(w_box, h_box) / float(short_side)
        if aspect_ratio >= 5.0 and not line_evidence and fore_fraction < MIN_FORE_FRACTION:
            continue

        padded_rect = (
            max(0.0, float(x - pad)),
            max(0.0, float(y - pad)),
            min(float(width), float(x + w_box + pad)),
            min(float(height), float(y + h_box + pad)),
        )
        rectangles.append(apply_view_expand(padded_rect, width, height, ink_mask))

    return rectangles, len(rectangles), len(raw_components), len(filtered_indices)


def is_identical_text_region(
    rect: Rect,
    old_groups: Sequence[TextGroup],
    new_groups: Sequence[TextGroup],
    component_mask: np.ndarray,
    diff_img: np.ndarray,
    edge_old: np.ndarray,
    edge_new: np.ndarray,
    kernel: np.ndarray,
) -> bool:
    """Return True if the region should be suppressed as stable text."""

    old_text, old_iou = gather_text_groups(old_groups, rect)
    new_text, new_iou = gather_text_groups(new_groups, rect)
    if not old_text or not new_text or old_text != new_text:
        return False
    if old_iou < 0.6 or new_iou < 0.6:
        return False

    eroded = cv2.erode(component_mask, kernel, iterations=1)
    if cv2.countNonZero(eroded) == 0:
        eroded = component_mask
    mean_absdiff = cv2.mean(diff_img, mask=eroded)[0]
    if mean_absdiff >= MEAN_TEXT_DIFF_MIN:
        return False

    overlap = compute_edge_overlap(rect, component_mask, edge_old, edge_new)
    return overlap >= EDGE_OVERLAP_MIN


def gather_text_groups(groups: Sequence[TextGroup], rect: Rect) -> Tuple[str, float]:
    """Collect grouped text overlapping a rectangle and compute IoU."""

    x1, y1, x2, y2 = rect
    selected: List[TextGroup] = []
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    for group in groups:
        gx1, gy1, gx2, gy2 = group.bbox
        if gx2 <= x1 or gx1 >= x2 or gy2 <= y1 or gy1 >= y2:
            continue
        inter_x1 = max(x1, gx1)
        inter_y1 = max(y1, gy1)
        inter_x2 = min(x2, gx2)
        inter_y2 = min(y2, gy2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            continue
        selected.append(group)
        min_x = min(min_x, gx1)
        min_y = min(min_y, gy1)
        max_x = max(max_x, gx2)
        max_y = max(max_y, gy2)

    if not selected:
        return "", 0.0

    bbox = (min_x, min_y, max_x, max_y)
    iou = compute_iou(rect, bbox)

    sorted_groups = sorted(selected, key=lambda g: (round(g.bbox[1] / 4.0) * 4.0, g.bbox[0]))
    text = " ".join(group.text for group in sorted_groups)
    return text, iou


def compute_iou(a: Rect, b: Rect) -> float:
    """Compute the intersection over union of two rectangles."""

    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0.0:
        return 0.0
    return float(inter_area / union)


def box_center(box: Rect) -> Tuple[float, float]:
    """Return the center point of an axis-aligned rectangle."""

    x1, y1, x2, y2 = box
    return (0.5 * (x1 + x2), 0.5 * (y1 + y2))


def box_iou(a: Rect, b: Rect) -> float:
    """Alias to compute IoU with clearer naming for box matching."""

    return compute_iou(a, b)


def compute_patch_similarity(
    old_img: Optional[np.ndarray],
    new_img: Optional[np.ndarray],
    r_box: Rect,
    a_box: Rect,
    pad: int = PATCH_PAD,
) -> float:
    """Compute SSIM or correlation similarity between two patches.

    Patches are taken from the aligned grayscale images. They are padded, resized to a
    common size, normalized and compared. A return value of 1.0 means identical.
    """

    if old_img is None or new_img is None:
        return 0.0

    height, width = old_img.shape[:2]

    def _clip(box: Rect) -> Tuple[int, int, int, int]:
        x1 = max(0, int(math.floor(box[0] - pad)))
        y1 = max(0, int(math.floor(box[1] - pad)))
        x2 = min(width, int(math.ceil(box[2] + pad)))
        y2 = min(height, int(math.ceil(box[3] + pad)))
        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)
        return x1, y1, x2, y2

    rx1, ry1, rx2, ry2 = _clip(r_box)
    ax1, ay1, ax2, ay2 = _clip(a_box)

    ref_patch = old_img[ry1:ry2, rx1:rx2]
    new_patch = new_img[ay1:ay2, ax1:ax2]

    if ref_patch.size == 0 or new_patch.size == 0:
        return 0.0

    target_w = max(1, PATCH_SIM_SIZE)
    target_h = max(1, PATCH_SIM_SIZE)

    ref_patch = cv2.resize(ref_patch, (target_w, target_h), interpolation=cv2.INTER_AREA)
    new_patch = cv2.resize(new_patch, (target_w, target_h), interpolation=cv2.INTER_AREA)

    ref_f = ref_patch.astype(np.float32) / 255.0
    new_f = new_patch.astype(np.float32) / 255.0

    if structural_similarity is not None:
        try:
            score = structural_similarity(ref_f, new_f)
            return float(score)
        except Exception:
            pass

    ref_mean = ref_f.mean()
    new_mean = new_f.mean()
    ref_std = ref_f.std()
    new_std = new_f.std()
    if ref_std == 0.0 or new_std == 0.0:
        return 0.0
    norm_ref = (ref_f - ref_mean) / ref_std
    norm_new = (new_f - new_mean) / new_std
    corr = float(np.mean(norm_ref * norm_new))
    return max(0.0, min(1.0, 0.5 + 0.5 * corr))


def drop_stable_regions(
    boxes: Sequence[Rect],
    diff_img: Optional[np.ndarray],
    ref_img: Optional[np.ndarray],
    cmp_img: Optional[np.ndarray],
    *,
    mean_threshold: float = MEAN_DIFF_MIN,
    similarity_cutoff: float = 0.992,
) -> Tuple[List[Rect], int]:
    """Filter out boxes whose patches are nearly identical and low-energy.

    This reduces false positives from background noise while retaining genuine
    differences due to low similarity scores or higher local mean differences.
    """

    if diff_img is None or ref_img is None or cmp_img is None:
        return list(boxes), 0

    height, width = diff_img.shape[:2]
    kept: List[Rect] = []
    suppressed = 0

    for box in boxes:
        x1 = max(0, int(math.floor(box[0])))
        y1 = max(0, int(math.floor(box[1])))
        x2 = min(width, int(math.ceil(box[2])))
        y2 = min(height, int(math.ceil(box[3])))
        if x2 <= x1 or y2 <= y1:
            continue
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[y1:y2, x1:x2] = 255
        mean_val = cv2.mean(diff_img, mask=mask)[0]
        if mean_val >= mean_threshold:
            kept.append(box)
            continue

        # Tiny regions provide little SSIM signal; accept them when the mean
        # difference is above noise, otherwise treat them as stable only with
        # extremely high similarity.
        similarity = compute_patch_similarity(ref_img, cmp_img, box, box, PATCH_PAD)
        dynamic_cutoff = similarity_cutoff
        if (x2 - x1) * (y2 - y1) < 36:
            dynamic_cutoff = max(dynamic_cutoff, 0.995)
        if similarity >= dynamic_cutoff and mean_val < mean_threshold * 0.9:
            suppressed += 1
            continue
        kept.append(box)

    return kept, suppressed


def suppress_moved_pairs(
    removed_boxes: Sequence[Rect],
    added_boxes: Sequence[Rect],
    old_img: Optional[np.ndarray] = None,
    new_img: Optional[np.ndarray] = None,
) -> Tuple[List[Rect], List[Rect], int]:
    """Drop pairs of boxes that represent the same object shifted slightly.

    A geometric filter selects candidate pairs, and a patch similarity score confirms
    that their content is effectively identical, suppressing false positives from
    slight movement.
    """

    if not removed_boxes or not added_boxes:
        return list(removed_boxes), list(added_boxes), 0

    matched_removed: set[int] = set()
    matched_added: set[int] = set()
    suppressed = 0
    total_boxes = len(removed_boxes) + len(added_boxes)
    heavy_load = total_boxes > MAX_BOXES_FOR_MOVEMENT_SUPPRESSION

    def _area(rect: Rect) -> float:
        return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])

    def _cutoff(values: Sequence[float]) -> float:
        if not values:
            return float("inf")
        sorted_vals = sorted(values, reverse=True)
        keep_index = max(0, int(math.ceil(len(sorted_vals) * 0.2)) - 1)
        return sorted_vals[keep_index]

    removed_cut = _cutoff([_area(box) for box in removed_boxes]) if heavy_load else 0.0
    added_cut = _cutoff([_area(box) for box in added_boxes]) if heavy_load else 0.0

    for ridx, rbox in enumerate(removed_boxes):
        rw = rbox[2] - rbox[0]
        rh = rbox[3] - rbox[1]
        r_center = box_center(rbox)

        candidates: List[Tuple[float, int, Rect]] = []

        for aidx, abox in enumerate(added_boxes):
            if aidx in matched_added:
                continue

            aw = abox[2] - abox[0]
            ah = abox[3] - abox[1]

            if rw <= 0 or rh <= 0 or aw <= 0 or ah <= 0:
                continue

            if abs(rw - aw) / max(rw, aw) > SIZE_TOLERANCE:
                continue
            if abs(rh - ah) / max(rh, ah) > SIZE_TOLERANCE:
                continue

            a_center = box_center(abox)
            shift = math.hypot(r_center[0] - a_center[0], r_center[1] - a_center[1])
            if shift > MAX_CENTER_SHIFT_PX:
                continue

            iou = box_iou(rbox, abox)
            if iou < MIN_IOU_FOR_SAME:
                continue

            candidates.append((shift, aidx, abox))

        candidates.sort(key=lambda entry: entry[0])

        for shift, aidx, abox in candidates[:MAX_CANDIDATES_PER_REMOVED]:
            r_area = _area(rbox)
            a_area = _area(abox)
            needs_ssim = not heavy_load or (r_area >= removed_cut and a_area >= added_cut)
            similarity = 1.0 if not needs_ssim else compute_patch_similarity(old_img, new_img, rbox, abox, PATCH_PAD)
            if similarity < MIN_PATCH_SSIM_FOR_SAME:
                continue

            if DEBUG_MOVEMENT_SUPPRESSION:
                logger.info(
                    "movement suppression candidate: shift=%.2f sim=%.3f size=(%.1f,%.1f)/(%.1f,%.1f)",
                    shift,
                    similarity,
                    rw,
                    rh,
                    abox[2] - abox[0],
                    abox[3] - abox[1],
                )

            matched_removed.add(ridx)
            matched_added.add(aidx)
            suppressed += 1
            break

    kept_removed = [box for idx, box in enumerate(removed_boxes) if idx not in matched_removed]
    kept_added = [box for idx, box in enumerate(added_boxes) if idx not in matched_added]
    return kept_removed, kept_added, suppressed


def suppress_identical_text_pairs(
    removed_boxes: Sequence[Rect],
    added_boxes: Sequence[Rect],
    words_old: Sequence[WordBox],
    words_new: Sequence[WordBox],
) -> Tuple[List[Rect], List[Rect], int]:
    """Suppress pairs where PDF text content is identical but moved slightly."""

    if not removed_boxes or not added_boxes:
        return list(removed_boxes), list(added_boxes), 0

    suppressed = 0
    matched_removed: set[int] = set()
    matched_added: set[int] = set()

    def _normalize_text(text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _collect_text(words: Sequence[WordBox], rect: Rect) -> str:
        collected = [w[0] for w in words if compute_iou(w[1], rect) >= WORD_IOU_MIN]
        return _normalize_text(" ".join(sorted(collected))) if collected else ""

    for ridx, rbox in enumerate(removed_boxes):
        if ridx in matched_removed:
            continue
        rw = rbox[2] - rbox[0]
        rh = rbox[3] - rbox[1]
        r_center = box_center(rbox)

        for aidx, abox in enumerate(added_boxes):
            if aidx in matched_added:
                continue

            aw = abox[2] - abox[0]
            ah = abox[3] - abox[1]
            if rw <= 0 or rh <= 0 or aw <= 0 or ah <= 0:
                continue
            if abs(rw - aw) / max(rw, aw) > SIZE_TOLERANCE:
                continue
            if abs(rh - ah) / max(rh, ah) > SIZE_TOLERANCE:
                continue

            a_center = box_center(abox)
            shift = math.hypot(r_center[0] - a_center[0], r_center[1] - a_center[1])
            if shift > MAX_CENTER_SHIFT_PX:
                continue

            old_text = _collect_text(words_old, rbox)
            new_text = _collect_text(words_new, abox)
            if not old_text or not new_text:
                continue
            if old_text != new_text:
                continue

            matched_removed.add(ridx)
            matched_added.add(aidx)
            suppressed += 1
            break

    kept_removed = [box for idx, box in enumerate(removed_boxes) if idx not in matched_removed]
    kept_added = [box for idx, box in enumerate(added_boxes) if idx not in matched_added]
    return kept_removed, kept_added, suppressed


def filter_identical_text_regions(
    removed_boxes: Sequence[Rect],
    added_boxes: Sequence[Rect],
    words_old: Sequence[WordBox],
    words_new: Sequence[WordBox],
) -> Tuple[List[Rect], List[Rect], int]:
    """Remove regions where text content matches between OLD and NEW."""

    def _normalize(text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _collect(rect: Rect) -> Tuple[str, str]:
        old_text = [w[0] for w in words_old if compute_iou(w[1], rect) >= WORD_IOU_MIN]
        new_text = [w[0] for w in words_new if compute_iou(w[1], rect) >= WORD_IOU_MIN]
        norm_old = _normalize(" ".join(sorted(old_text))) if old_text else ""
        norm_new = _normalize(" ".join(sorted(new_text))) if new_text else ""
        return norm_old, norm_new

    suppressed = 0
    kept_removed: List[Rect] = []
    kept_added: List[Rect] = []

    for rect in removed_boxes:
        old_text, new_text = _collect(rect)
        if old_text and old_text == new_text:
            suppressed += 1
            continue
        kept_removed.append(rect)

    for rect in added_boxes:
        old_text, new_text = _collect(rect)
        if new_text and old_text == new_text:
            suppressed += 1
            continue
        kept_added.append(rect)

    return kept_removed, kept_added, suppressed


def apply_dimming_overlay(page: fitz.Page, boxes: Sequence[Rect], scale: float) -> None:
    """Dim everything outside the provided boxes using an even-odd fill overlay."""

    if not DIMMING_ENABLED or not boxes:
        return

    dim_color = (0.0, 0.0, 0.0) if DIMMING_MODE.lower() == "dark" else (1.0, 1.0, 1.0)
    feather = max(0.0, DIMMING_FEATHER) / max(scale, 1e-6)

    try:
        shape = page.new_shape()
        shape.draw_rect(page.rect)
        for rect in boxes:
            pdf_rect = fitz.Rect(
                (rect[0] / scale) - feather,
                (rect[1] / scale) - feather,
                (rect[2] / scale) + feather,
                (rect[3] / scale) + feather,
            )
            pdf_rect = pdf_rect & page.rect
            shape.draw_rect(pdf_rect)

        shape.finish(
            fill=dim_color,
            color=None,
            even_odd=True,
            fill_opacity=DIMMING_ALPHA,
        )
        shape.commit()
    except Exception:
        # Fallback: overlay + holes set to zero opacity.
        page.draw_rect(
            page.rect,
            color=None,
            fill=dim_color,
            fill_opacity=DIMMING_ALPHA,
            overlay=True,
        )
        for rect in boxes:
            pdf_rect = fitz.Rect(
                rect[0] / scale,
                rect[1] / scale,
                rect[2] / scale,
                rect[3] / scale,
            )
            pdf_rect = pdf_rect & page.rect
            page.draw_rect(
                pdf_rect,
                color=None,
                fill=dim_color,
                fill_opacity=0.0,
                overlay=True,
            )


def drop_overlapping_removals(
    old_boxes: Sequence[Rect],
    new_boxes: Sequence[Rect],
    *,
    iou_threshold: float = 0.65,
) -> Tuple[List[Rect], int]:
    """Remove removal boxes that overlap additions, avoiding false deletions."""

    if not old_boxes or not new_boxes:
        return list(old_boxes), 0

    pruned: List[Rect] = []
    suppressed = 0
    for old_rect in old_boxes:
        if any(compute_iou(old_rect, new_rect) >= iou_threshold for new_rect in new_boxes):
            suppressed += 1
            continue
        pruned.append(old_rect)
    return pruned, suppressed


def compute_edge_overlap(rect: Rect, component_mask: np.ndarray, edge_old: np.ndarray, edge_new: np.ndarray) -> float:
    """Compute overlap ratio between old/new edge maps inside a region."""

    x1, y1, x2, y2 = [int(round(v)) for v in rect]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(edge_old.shape[1], x2)
    y2 = min(edge_old.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0

    region_mask = component_mask[y1:y2, x1:x2] > 0
    if not np.any(region_mask):
        return 0.0

    old_edges = np.logical_and(edge_old[y1:y2, x1:x2] > 0, region_mask)
    new_edges = np.logical_and(edge_new[y1:y2, x1:x2] > 0, region_mask)

    union = np.logical_or(old_edges, new_edges)
    union_count = int(np.count_nonzero(union))
    if union_count == 0:
        return 0.0
    intersection = int(np.count_nonzero(np.logical_and(old_edges, new_edges)))
    return float(intersection / union_count)


def suppress_unchanged_text(
    candidates: Sequence[Rect],
    absdiff: np.ndarray,
    edge_old: np.ndarray,
    edge_new: np.ndarray,
    words_old: Sequence[WordBox],
    words_new: Sequence[WordBox],
) -> Tuple[List[Rect], int]:
    """Remove unchanged-text boxes based on word-level comparisons."""

    if not candidates:
        return [], 0

    height, width = absdiff.shape[:2]

    def clip_rect(rect: Rect) -> Rect:
        x1 = max(0.0, min(rect[0], float(width)))
        y1 = max(0.0, min(rect[1], float(height)))
        x2 = max(x1, min(rect[2], float(width)))
        y2 = max(y1, min(rect[3], float(height)))
        return x1, y1, x2, y2

    def clip_word(word: WordBox) -> Optional[WordBox]:
        text, rect, baseline = word
        clipped = clip_rect(rect)
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            return None
        clamped_baseline = baseline
        if height > 0:
            clamped_baseline = min(max(0, baseline), height - 1)
        return text, clipped, clamped_baseline

    clipped_old = [cw for cw in (clip_word(word) for word in words_old) if cw is not None]
    clipped_new = [cw for cw in (clip_word(word) for word in words_new) if cw is not None]

    if not clipped_old or not clipped_new:
        return list(candidates), 0

    kept: List[Rect] = []
    suppressed = 0
    kernel = np.ones((3, 3), np.uint8)

    def _is_word_match(old_word: WordBox, new_word: WordBox) -> bool:
        if abs(old_word[2] - new_word[2]) > BASELINE_DELTA_MAX_PX:
            return False

        iou = compute_iou(old_word[1], new_word[1])
        if iou >= WORD_IOU_MIN:
            return True

        ox1, oy1, ox2, oy2 = old_word[1]
        nx1, ny1, nx2, ny2 = new_word[1]
        old_cx = 0.5 * (ox1 + ox2)
        old_cy = 0.5 * (oy1 + oy2)
        new_cx = 0.5 * (nx1 + nx2)
        new_cy = 0.5 * (ny1 + ny2)
        shift = math.hypot(old_cx - new_cx, old_cy - new_cy)
        return shift <= WORD_SHIFT_TOLERANCE_PX

    for rect in candidates:
        clipped = clip_rect(rect)
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            kept.append(rect)
            continue

        old_hits = [word for word in clipped_old if compute_iou(word[1], clipped) >= WORD_IOU_MIN]
        if not old_hits:
            kept.append(rect)
            continue

        new_hits = [word for word in clipped_new if compute_iou(word[1], clipped) >= WORD_IOU_MIN]
        if not new_hits:
            kept.append(rect)
            continue

        norm_old_full = _normalize_text(" ".join(sorted(word[0] for word in old_hits)))
        norm_new_full = _normalize_text(" ".join(sorted(word[0] for word in new_hits)))
        if norm_old_full != norm_new_full:
            kept.append(rect)
            continue

        matches: dict[str, List[WordBox]] = {}
        for word in new_hits:
            matches.setdefault(word[0], []).append(word)

        suppressed_here = False
        mean_absdiff: Optional[float] = None
        edge_overlap: Optional[float] = None
        sample_text = ""

        for old_word in old_hits:
            candidates_new = matches.get(old_word[0])
            if not candidates_new:
                continue
            for new_word in candidates_new:
                if not _is_word_match(old_word, new_word):
                    continue
                if mean_absdiff is None or edge_overlap is None:
                    x1 = max(0, min(width, int(math.floor(clipped[0]))))
                    y1 = max(0, min(height, int(math.floor(clipped[1]))))
                    x2 = max(x1 + 1, min(width, int(math.ceil(clipped[2]))))
                    y2 = max(y1 + 1, min(height, int(math.ceil(clipped[3]))))
                    if x2 <= x1 or y2 <= y1:
                        break
                    roi = absdiff[y1:y2, x1:x2]
                    mask = np.ones((roi.shape[0], roi.shape[1]), dtype=np.uint8) * 255
                    eroded = cv2.erode(mask, kernel, iterations=1)
                    if not np.any(eroded):
                        eroded = mask
                    mean_absdiff = float(cv2.mean(roi, mask=eroded)[0])

                    old_edges = edge_old[y1:y2, x1:x2] > 0
                    new_edges = edge_new[y1:y2, x1:x2] > 0
                    union = np.logical_or(old_edges, new_edges)
                    union_count = int(np.count_nonzero(union))
                    if union_count == 0:
                        edge_overlap = 0.0
                    else:
                        intersection = int(np.count_nonzero(np.logical_and(old_edges, new_edges)))
                        edge_overlap = float(intersection / union_count)

                if mean_absdiff is None or edge_overlap is None:
                    continue

                if mean_absdiff <= ABSMEAN_MAX_UNCHANGED_TXT and edge_overlap >= EDGE_OVERLAP_MIN:
                    suppressed_here = True
                    sample_text = old_word[0]
                    break
            if suppressed_here:
                break

        if suppressed_here:
            suppressed += 1
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "unchanged-text veto: %r mean=%.2f overlap=%.3f",
                    sample_text,
                    mean_absdiff if mean_absdiff is not None else -1.0,
                    edge_overlap if edge_overlap is not None else -1.0,
                )
            continue

        kept.append(rect)

    return kept, suppressed


def apply_view_expand(rect: Rect, width: int, height: int, ink_mask: np.ndarray) -> Rect:
    """Apply visual padding expansion with caps and ink-aware shrinking."""

    x1, y1, x2, y2 = rect
    x1 = max(0.0, min(float(width), float(x1)))
    y1 = max(0.0, min(float(height), float(y1)))
    x2 = max(x1, min(float(width), float(x2)))
    y2 = max(y1, min(float(height), float(y2)))

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    half_w = max((x2 - x1) / 2.0, MIN_DIM / 2.0)
    half_h = max((y2 - y1) / 2.0, MIN_DIM / 2.0)

    extra_w = min(half_w * (VIEW_EXPAND - 1.0), VIEW_MAX_GROW)
    extra_h = min(half_h * (VIEW_EXPAND - 1.0), VIEW_MAX_GROW)

    expanded_x1 = max(0.0, cx - half_w - extra_w)
    expanded_y1 = max(0.0, cy - half_h - extra_h)
    expanded_x2 = min(float(width), cx + half_w + extra_w)
    expanded_y2 = min(float(height), cy + half_h + extra_h)

    expanded = (expanded_x1, expanded_y1, expanded_x2, expanded_y2)
    if compute_rect_ink_fraction(expanded, ink_mask) < 0.22:
        return (x1, y1, x2, y2)
    return expanded


def compute_rect_ink_fraction(rect: Rect, ink_mask: np.ndarray) -> float:
    """Compute the fraction of ink within a rectangle."""

    x1, y1, x2, y2 = [int(round(v)) for v in rect]
    x1 = max(0, min(ink_mask.shape[1], x1))
    y1 = max(0, min(ink_mask.shape[0], y1))
    x2 = max(x1 + 1, min(ink_mask.shape[1], x2))
    y2 = max(y1 + 1, min(ink_mask.shape[0], y2))
    region = ink_mask[y1:y2, x1:x2]
    if region.size == 0:
        return 0.0
    ink = cv2.countNonZero(region)
    area = float((x2 - x1) * (y2 - y1))
    if area <= 0.0:
        return 0.0
    return float(ink) / area


def merge_rectangles(rectangles: Sequence[Rect]) -> List[Rect]:
    """Merge overlapping or touching rectangles within a color set."""

    rects = [tuple(rect) for rect in rectangles]
    if not rects:
        return []

    merged: List[Rect] = list(rects)
    changed = True
    while changed:
        changed = False
        next_pass: List[Rect] = []
        while merged:
            current = merged.pop()
            index = 0
            while index < len(merged):
                other = merged[index]
                if rectangles_touch(current, other):
                    current = (
                        min(current[0], other[0]),
                        min(current[1], other[1]),
                        max(current[2], other[2]),
                        max(current[3], other[3]),
                    )
                    merged.pop(index)
                    changed = True
                else:
                    index += 1
            next_pass.append(current)
        merged = next_pass
    merged.reverse()
    return merged


def merge_close_rectangles(rectangles: Sequence[Rect]) -> List[Rect]:
    """Group rectangles that are close enough to describe one dimension cluster."""

    rects = list(rectangles)
    if not rects:
        return []

    merged: List[Rect] = []
    used: set[int] = set()

    for idx, base in enumerate(rects):
        if idx in used:
            continue
        cluster = [base]
        used.add(idx)
        changed = True
        while changed:
            changed = False
            cluster_box = (
                min(r[0] for r in cluster),
                min(r[1] for r in cluster),
                max(r[2] for r in cluster),
                max(r[3] for r in cluster),
            )
            cluster_cx, cluster_cy = box_center(cluster_box)
            cluster_span = (cluster_box[2] - cluster_box[0] + cluster_box[3] - cluster_box[1]) / 2.0
            for other_idx, other in enumerate(rects):
                if other_idx in used:
                    continue
                if rectangles_touch(cluster_box, other) or compute_iou(cluster_box, other) >= MERGE_IOU_THRESHOLD:
                    used.add(other_idx)
                    cluster.append(other)
                    changed = True
                    continue
                ocx, ocy = box_center(other)
                dist = math.hypot(cluster_cx - ocx, cluster_cy - ocy)
                other_span = (other[2] - other[0] + other[3] - other[1]) / 2.0
                if dist <= MERGE_CENTER_DIST_FACTOR * max(cluster_span, other_span):
                    used.add(other_idx)
                    cluster.append(other)
                    changed = True
        merged_box = (
            min(r[0] for r in cluster),
            min(r[1] for r in cluster),
            max(r[2] for r in cluster),
            max(r[3] for r in cluster),
        )
        merged.append(merged_box)

    return merge_rectangles(merged)


def rectangles_touch(a: Rect, b: Rect) -> bool:
    """Return True if rectangles overlap or touch."""

    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


class PersistentLogHandler(logging.Handler):
    """Logging handler that mirrors messages into the crash-proof log."""

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        write_log(msg)


def configure_logging() -> None:
    """Configure root logger for console output."""

    logger.setLevel(logging.INFO)
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    if LOG_FILE and not any(isinstance(handler, PersistentLogHandler) for handler in logger.handlers):
        file_handler = PersistentLogHandler()
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)
    logger.propagate = False


logger = logging.getLogger("compare_set")
configure_logging()

