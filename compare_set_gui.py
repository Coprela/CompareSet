#!/usr/bin/env python3
"""CompareSet desktop application with enhanced diff suppression."""

from __future__ import annotations

import compare_engine
import getpass
import logging
import os
import shutil
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from compare_engine import (
    ComparisonResult,
    PageDiffSummary,
    configure_logging,
    init_log,
    logger,
    run_comparison,
    write_log,
)

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

    try:
        compare_engine.set_connection_state(server_online)
    except Exception:
        pass


set_connection_state(is_server_available(SERVER_ROOT))

USERS_DB_PATH = os.path.join(CONFIG_ROOT, "users.sqlite")
USER_SETTINGS_DB_PATH = os.path.join(CONFIG_ROOT, "user_settings.sqlite")
RELEASED_DB_PATH = os.path.join(CONFIG_ROOT, "released.sqlite")


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




class LogEmitter(QObject):
    """Qt signal emitter for log messages."""

    message = Signal(str)


class PersistentLogHandler(logging.Handler):
    """Logging handler that mirrors messages into the crash-proof log."""

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        write_log(msg)


class QtLogHandler(logging.Handler):
    """Logging handler that forwards messages to Qt widgets."""

    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        self.emitter.message.emit(message)


class CompareSetWorker(QObject):
    """Worker object executing the comparison in a background thread."""

    finished = Signal(ComparisonResult)
    failed = Signal(str)
    progress = Signal(int, int)
    cancelled = Signal()

    def __init__(self, old_path: Path, new_path: Path) -> None:
        super().__init__()
        self.old_path = old_path
        self.new_path = new_path
        self._cancel_event = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            result = run_comparison(
                self.old_path,
                self.new_path,
                update_progress=self._emit_progress,
                is_cancel_requested=self._cancel_event.is_set,
            )
        except Exception as exc:  # pragma: no cover - Qt thread
            logger.exception("Comparison failed: %s", exc)
            self.failed.emit(str(exc))
            return
        if result.cancelled:
            self.cancelled.emit()
            return
        self.finished.emit(result)

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def _emit_progress(self, page_index: int, total_pages: int) -> None:
        self.progress.emit(page_index, total_pages)


class HistoryDialog(QDialog):
    """Dialog showing previous comparisons for the current user."""

    def __init__(self, username: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username = username
        self.user_results_dir = os.path.join(OUTPUT_DIR, username)
        self.user_logs_dir = os.path.join(LOG_DIR, username)
        self.setWindowTitle("My History")
        self.entries: List[Dict[str, Union[str, datetime]]] = []

        layout = QVBoxLayout(self)
        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date/Time", "Base name", "File name", "Actions"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        self.released_button = QPushButton("Released")
        self.released_button.clicked.connect(self.send_selected_to_released)
        clear_button = QPushButton("Limpar Histórico")
        clear_button.clicked.connect(self.clear_history)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(clear_button)
        button_row.addWidget(self.released_button)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.refresh_history()

    def refresh_history(self) -> None:
        self.entries = self._collect_entries()
        self.table.setRowCount(len(self.entries))

        if not self.entries:
            self.info_label.setText("No previous comparisons found.")
        else:
            self.info_label.setText(f"Showing {len(self.entries)} result(s) for {self.username}.")

        for row_index, entry in enumerate(self.entries):
            timestamp_item = QTableWidgetItem(entry["display_time"])
            timestamp_item.setData(Qt.UserRole, entry["timestamp"])
            self.table.setItem(row_index, 0, timestamp_item)
            self.table.setItem(row_index, 1, QTableWidgetItem(entry["base_name"]))
            self.table.setItem(row_index, 2, QTableWidgetItem(entry["filename"]))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            view_button = QPushButton("View")
            view_button.clicked.connect(
                lambda _=False, p=entry["path"]: open_with_default_application(p)
            )
            export_button = QPushButton("Export")
            export_button.clicked.connect(
                lambda _=False, p=entry["path"], fn=entry["filename"]: self.export_result(p, fn)
            )
            action_layout.addWidget(view_button)
            action_layout.addWidget(export_button)

            if entry.get("log_path") and getattr(self.parent(), "role", "") == "admin":
                log_button = QPushButton("View log")
                log_button.clicked.connect(
                    lambda _=False, lp=entry["log_path"]: self.view_log(lp)
                )
                action_layout.addWidget(log_button)

            action_layout.addStretch()
            self.table.setCellWidget(row_index, 3, action_widget)

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        total_width = (
            self.table.verticalHeader().width()
            + self.table.horizontalHeader().length()
            + self.table.frameWidth() * 4
        )
        total_height = (
            self.table.horizontalHeader().height()
            + sum(self.table.rowHeight(row) for row in range(self.table.rowCount()))
            + self.table.frameWidth() * 4
            + self.info_label.sizeHint().height()
            + 100
        )
        self.resize(max(self.width(), total_width + 40), max(320, min(total_height, 720)))

    def _collect_entries(self) -> List[Dict[str, Union[str, datetime]]]:
        if not os.path.exists(self.user_results_dir):
            return []

        entries: List[Dict[str, Union[str, datetime]]] = []
        for pdf_path in Path(self.user_results_dir).glob("ECR-*.pdf"):
            parsed = parse_result_filename(pdf_path)
            if not parsed:
                continue
            base_name, timestamp = parsed
            log_name = f"ECR-{base_name}_{timestamp.strftime('%Y%m%d-%H%M%S')}_{self.username}.log"
            log_path = Path(self.user_logs_dir) / log_name
            entries.append(
                {
                    "base_name": base_name,
                    "timestamp": timestamp,
                    "display_time": timestamp.strftime("%d/%m/%Y %H:%M:%S"),
                    "filename": pdf_path.name,
                    "path": str(pdf_path),
                    "log_path": str(log_path) if log_path.exists() else "",
                }
            )

        entries.sort(key=lambda item: item["timestamp"], reverse=True)
        return entries

    def export_result(self, source_path: str, filename: str) -> None:
        target_path, _ = QFileDialog.getSaveFileName(
            self, "Save As", filename, "PDF Files (*.pdf)"
        )
        if not target_path:
            return
        try:
            shutil.copyfile(source_path, target_path)
            QMessageBox.information(
                self,
                "CompareSet",
                f"File exported to:\n{target_path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "CompareSet", f"Unable to export file:\n{exc}")

    def view_log(self, log_path: str) -> None:
        if not log_path or not os.path.exists(log_path):
            QMessageBox.information(self, "CompareSet", "Log file not found.")
            return
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
        except Exception as exc:
            QMessageBox.warning(self, "CompareSet", f"Unable to read log:\n{exc}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Comparison Log")
        layout = QVBoxLayout(dialog)
        text_view = QTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText(content)
        layout.addWidget(text_view)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(close_button)
        layout.addLayout(button_row)
        dialog.resize(600, 400)
        dialog.exec()

    def send_selected_to_released(self) -> None:
        if self.table.currentRow() < 0 or self.table.currentRow() >= len(self.entries):
            QMessageBox.information(self, "ECR Released", "Selecione um registro para liberar.")
            return

        entry = self.entries[self.table.currentRow()]
        dialog = ReleaseDialog(self)
        dialog.name_file_old.setText(f"{entry['base_name']}.pdf")
        dialog.name_file_new.setText(f"{entry['base_name']}.pdf")
        if dialog.exec() != QDialog.Accepted:
            return

        data = dialog.data()
        new_base = Path(data["name_file_new"]).stem
        target_filename = f"ECR-{new_base}{data['revision_new']}_{self.username}.pdf"
        existing = find_released_entry(target_filename)
        if existing and existing.get("created_by") != self.username:
            QMessageBox.warning(
                self,
                "ECR Released",
                "Já existe um ECR liberado com este nome por outro usuário.",
            )
            return

        target_dir = os.path.join(RELEASED_ROOT, self.username)
        if SERVER_ONLINE:
            os.makedirs(make_long_path(target_dir), exist_ok=True)
            target_path = make_long_path(os.path.join(target_dir, target_filename))
        else:
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, target_filename)

        try:
            if existing and existing.get("created_by") == self.username:
                if os.path.exists(existing.get("source_result", "")):
                    source_result = existing["source_result"]
                    if SERVER_ONLINE:
                        os.remove(make_long_path(source_result))
                    else:
                        os.remove(source_result)
            if os.path.exists(target_path):
                os.remove(target_path)
            if SERVER_ONLINE:
                shutil.move(make_long_path(str(entry["path"])), target_path)
            else:
                shutil.move(str(entry["path"]), target_path)
            record_released_entry(
                filename=target_filename,
                name_file_old=data["name_file_old"],
                revision_old=data["revision_old"],
                name_file_new=data["name_file_new"],
                revision_new=data["revision_new"],
                created_by=self.username,
                source_result=target_path,
            )
            QMessageBox.information(
                self,
                "ECR Released",
                f"Arquivo liberado em:\n{target_path}",
            )
            self.refresh_history()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "ECR Released",
                f"Não foi possível enviar o arquivo para Released:\n{exc}",
            )

    def clear_history(self) -> None:
        if not os.path.exists(self.user_results_dir):
            QMessageBox.information(self, "My History", "Nenhum histórico para limpar.")
            return
        if QMessageBox.question(
            self,
            "Limpar Histórico",
            "Remover todos os resultados exibidos? Esta ação não pode ser desfeita.",
        ) != QMessageBox.Yes:
            return
        try:
            for pdf_path in Path(self.user_results_dir).glob("ECR-*.pdf"):
                pdf_path.unlink(missing_ok=True)
            self.refresh_history()
            QMessageBox.information(self, "My History", "Histórico limpo.")
        except Exception as exc:
            QMessageBox.critical(self, "My History", f"Erro ao limpar histórico:\n{exc}")


class SettingsDialog(QDialog):
    """Modal dialog to edit per-user settings."""

    def __init__(self, username: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username = username
        self.setWindowTitle("Settings")

        self.language_combo = QComboBox()
        self.language_combo.addItems(["pt-BR", "en-US"])

        layout = QFormLayout(self)
        layout.addRow("Language", self.language_combo)

        button_row = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(ok_button)
        layout.addRow(button_row)

    def load(self) -> None:
        settings = get_or_create_user_settings(self.username)
        language = settings.get("language", "pt-BR")
        if language in {"pt-BR", "en-US"}:
            self.language_combo.setCurrentText(language)

    def save(self) -> None:
        update_user_settings(self.username, language=self.language_combo.currentText())


class EmailPromptDialog(QDialog):
    """Blocking prompt requesting the user's email address."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CompareSet")
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.label = QLabel("Por favor, insira seu e-mail.")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("email@dominio.com")
        layout.addWidget(self.label)
        layout.addWidget(self.email_edit)

        button_row = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_row.addStretch()
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    def get_email(self) -> str:
        return self.email_edit.text().strip()


class AdminDialog(QDialog):
    """Dialog for managing users, detached from the main window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Administração")
        self.resize(480, 520)

        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search username…")
        self.search_input.textChanged.connect(self.refresh_user_list)
        layout.addWidget(self.search_input)

        self.user_list = QListWidget()
        self.user_list.currentItemChanged.connect(self.on_user_selected)
        layout.addWidget(self.user_list)

        self.admin_username_input = QLineEdit()
        self.admin_role_combo = QComboBox()
        self.admin_role_combo.addItems(["admin", "user", "viewer"])
        self.admin_active_checkbox = QCheckBox("Active")
        self.admin_active_checkbox.setChecked(True)
        self.email_label = QLabel("")

        form_layout = QFormLayout()
        form_layout.addRow("Username", self.admin_username_input)
        form_layout.addRow("Role", self.admin_role_combo)
        form_layout.addRow("Status", self.admin_active_checkbox)
        form_layout.addRow("Email", self.email_label)
        layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        self.add_user_button = QPushButton("Add User")
        self.update_user_button = QPushButton("Save Changes")
        button_row.addWidget(self.add_user_button)
        button_row.addWidget(self.update_user_button)
        layout.addLayout(button_row)

        self.add_user_button.clicked.connect(self.on_add_user)
        self.update_user_button.clicked.connect(self.on_update_user)

        self.refresh_user_list()

    def refresh_user_list(self) -> None:
        try:
            users = list_users()
        except Exception as exc:
            QMessageBox.critical(self, "Admin", f"Could not load users:\n{exc}")
            return
        self.user_list.clear()
        search_text = (self.search_input.text() or "").lower().strip()
        for user in users:
            if search_text and search_text not in str(user.get("username", "")).lower():
                continue
            status = "Active" if user.get("is_active") else "Inactive"
            email = user.get("email") or "(sem e-mail)"
            item = QListWidgetItem(f"{user['username']} - {email} - {user['role']} ({status})")
            item.setData(Qt.UserRole, user)
            self.user_list.addItem(item)

    def on_user_selected(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ) -> None:
        if not current:
            return
        data = current.data(Qt.UserRole) or {}
        self.admin_username_input.setText(data.get("username", ""))
        self.admin_role_combo.setCurrentText(str(data.get("role", "user")))
        self.admin_active_checkbox.setChecked(bool(data.get("is_active", 0)))
        self.email_label.setText(data.get("email") or "")

    def on_add_user(self) -> None:
        username = self.admin_username_input.text().strip()
        role = self.admin_role_combo.currentText()
        if not username:
            QMessageBox.warning(self, "Admin", "Please enter a Windows username.")
            return
        try:
            add_user(username, role)
            QMessageBox.information(self, "Admin", "User added successfully.")
            self.refresh_user_list()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Admin", "User already exists.")
        except Exception as exc:
            QMessageBox.critical(self, "Admin", f"Unable to add user:\n{exc}")

    def on_update_user(self) -> None:
        if not self.user_list or not self.user_list.currentItem():
            QMessageBox.warning(self, "Admin", "Select a user to update.")
            return
        username = self.admin_username_input.text().strip()
        role = self.admin_role_combo.currentText()
        is_active = 1 if self.admin_active_checkbox.isChecked() else 0
        if not username:
            QMessageBox.warning(self, "Admin", "Please enter a Windows username.")
            return
        try:
            update_user_record(username, role=role, is_active=is_active)
            QMessageBox.information(self, "Admin", "User updated.")
            self.refresh_user_list()
        except Exception as exc:
            QMessageBox.critical(self, "Admin", f"Unable to update user:\n{exc}")


class ReleaseDialog(QDialog):
    """Dialog that captures required metadata before releasing an ECR."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ECR Released")

        self.name_file_old = QLineEdit()
        self.rev_old = QLineEdit()
        self.name_file_new = QLineEdit()
        self.rev_new = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("Name File OLD", self.name_file_old)
        layout.addRow("Revision File OLD", self.rev_old)
        layout.addRow("Name File NEW", self.name_file_new)
        layout.addRow("Revision File NEW", self.rev_new)

        button_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        ok = QPushButton("Send to Released")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._validate)
        button_row.addStretch()
        button_row.addWidget(cancel)
        button_row.addWidget(ok)
        layout.addRow(button_row)

    def _validate(self) -> None:
        fields = [
            self.name_file_old.text().strip(),
            self.rev_old.text().strip(),
            self.name_file_new.text().strip(),
            self.rev_new.text().strip(),
        ]
        if any(not value for value in fields):
            QMessageBox.warning(
                self,
                "ECR Released",
                "All fields are required before sending to Released.",
            )
            return
        self.accept()

    def data(self) -> Dict[str, str]:
        return {
            "name_file_old": self.name_file_old.text().strip(),
            "revision_old": self.rev_old.text().strip(),
            "name_file_new": self.name_file_new.text().strip(),
            "revision_new": self.rev_new.text().strip(),
        }


class ReleasedDialog(QDialog):
    """Dialog showing all released ECRs with search and actions."""

    def __init__(self, role: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.role = role
        self.setWindowTitle("ECR Released")
        self.resize(800, 420)

        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by file or user…")
        self.search_input.textChanged.connect(self.refresh)
        layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Date/Time",
                "Name File OLD",
                "Revision File OLD",
                "Name File NEW",
                "Revision File NEW",
                "Created by",
                "Status",
                "File name",
                "Actions",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        entries = list_released_entries()
        search_text = (self.search_input.text() or "").lower().strip()
        if search_text:
            entries = [
                entry
                for entry in entries
                if search_text in entry.get("filename", "").lower()
                or search_text in entry.get("created_by", "").lower()
            ]

        self.table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            created_at = entry.get("created_at", "")
            try:
                display_time = datetime.fromisoformat(created_at).strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                display_time = created_at
            self.table.setItem(row_index, 0, QTableWidgetItem(display_time))
            self.table.setItem(row_index, 1, QTableWidgetItem(entry.get("name_file_old", "")))
            self.table.setItem(row_index, 2, QTableWidgetItem(entry.get("revision_old", "")))
            self.table.setItem(row_index, 3, QTableWidgetItem(entry.get("name_file_new", "")))
            self.table.setItem(row_index, 4, QTableWidgetItem(entry.get("revision_new", "")))
            self.table.setItem(row_index, 5, QTableWidgetItem(entry.get("created_by", "")))
            self.table.setItem(row_index, 6, QTableWidgetItem("Released"))
            self.table.setItem(row_index, 7, QTableWidgetItem(entry.get("filename", "")))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            view_btn = QPushButton("View")
            export_btn = QPushButton("Export")
            view_btn.clicked.connect(
                lambda _=False, p=entry.get("source_result", ""): open_with_default_application(p)
            )
            export_btn.clicked.connect(
                lambda _=False, p=entry.get("source_result", ""), fn=entry.get("filename", ""): self.export_file(p, fn)
            )
            actions_layout.addWidget(view_btn)
            actions_layout.addWidget(export_btn)
            if self.role == "admin":
                delete_btn = QPushButton("Delete")
                delete_btn.clicked.connect(
                    lambda _=False, e=entry: self.delete_entry(e)
                )
                actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()
            self.table.setCellWidget(row_index, 8, actions)

    def export_file(self, source_path: str, filename: str) -> None:
        if not source_path:
            QMessageBox.warning(self, "ECR Released", "No file available to export.")
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self, "Save Released", filename or "released.pdf", "PDF Files (*.pdf)"
        )
        if not target_path:
            return
        try:
            shutil.copyfile(source_path, target_path)
            QMessageBox.information(self, "ECR Released", f"File exported to:\n{target_path}")
        except Exception as exc:
            QMessageBox.critical(self, "ECR Released", f"Unable to export file:\n{exc}")

    def delete_entry(self, entry: Dict[str, str]) -> None:
        filename = entry.get("filename", "")
        source_path = entry.get("source_result", "")
        if not filename:
            return
        if QMessageBox.question(
            self,
            "Delete Released",
            f"Remove {filename}? This will delete the released copy.",
        ) != QMessageBox.Yes:
            return
        try:
            if source_path and os.path.exists(source_path):
                os.remove(source_path)
            delete_released_entry(filename)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Released", f"Unable to delete file:\n{exc}")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, username: str, role: str, user_settings: Dict[str, str]) -> None:
        super().__init__()
        self.username = username
        self.role = role
        self.user_settings = user_settings
        self.current_language = user_settings.get("language", "pt-BR")
        self.last_browse_dir: Optional[str] = None
        self.setWindowTitle("CompareSet")

        self._log_emitter = LogEmitter()
        self._log_handler = QtLogHandler(self._log_emitter)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(self._log_handler)
        self._log_emitter.message.connect(self.append_log)

        self._thread: Optional[QThread] = None
        self._worker: Optional[CompareSetWorker] = None

        self.old_path_edit = QLineEdit()
        self.new_path_edit = QLineEdit()
        for line_edit in (self.old_path_edit, self.new_path_edit):
            line_edit.setPlaceholderText("Select a PDF file")

        self.old_browse_button = QPushButton("Browse…")
        self.new_browse_button = QPushButton("Browse…")
        self.old_browse_button.clicked.connect(lambda: self.select_file(self.old_path_edit))
        self.new_browse_button.clicked.connect(lambda: self.select_file(self.new_path_edit))

        self.compare_button = QPushButton("Compare")
        self.compare_button.clicked.connect(self.start_comparison)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.request_cancel)
        self.history_button = QPushButton("My History")
        self.history_button.clicked.connect(self.open_history)
        self.released_button = QPushButton("Released")
        self.released_button.clicked.connect(self.open_released)
        self.settings_button = QPushButton("Configurações")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.admin_button: Optional[QPushButton] = None

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.status_label = QLabel(f"Ready (Language: {self.current_language})")
        self.connection_status_label = QLabel()
        self.connection_status_label.setAlignment(Qt.AlignLeft)
        self.reload_button = QPushButton()
        self.reload_button.setFixedHeight(22)
        self.reload_button.clicked.connect(self.reload_server_status)
        self._offline_warning_shown = False

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)

        self._last_old_path: Optional[Path] = None

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        file_layout = QGridLayout()
        file_layout.addWidget(QLabel("Old revision (PDF)"), 0, 0)
        file_layout.addWidget(self.old_path_edit, 0, 1)
        file_layout.addWidget(self.old_browse_button, 0, 2)
        file_layout.addWidget(QLabel("New revision (PDF)"), 1, 0)
        file_layout.addWidget(self.new_path_edit, 1, 1)
        file_layout.addWidget(self.new_browse_button, 1, 2)

        main_layout.addLayout(file_layout)
        main_layout.addSpacing(8)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.history_button)
        button_layout.addWidget(self.released_button)
        button_layout.addWidget(self.settings_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.compare_button)
        main_layout.addLayout(button_layout)

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)
        if self.role == "admin":
            self.admin_button = QPushButton("Administração")
            self.admin_button.clicked.connect(self.open_admin_dialog)
            main_layout.addWidget(self.admin_button)
            main_layout.addWidget(self.log_view)

        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.addWidget(self.connection_status_label, 1)
        status_bar.addPermanentWidget(self.reload_button)

        self.setStatusBar(status_bar)
        self.apply_language_setting()
        self.setCentralWidget(central_widget)
        self.resize(720, 520)
        self.show_offline_warning_once()
        self.prompt_for_email_if_missing()

    @Slot(str)
    def append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.log_view.ensureCursorVisible()

    def select_file(self, target: QLineEdit) -> None:
        start_dir = self.last_browse_dir or str(Path.home())
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select PDF", start_dir, "PDF Files (*.pdf)"
        )
        if selected:
            target.setText(selected)
            self.last_browse_dir = os.path.dirname(selected)

    @Slot()
    def request_cancel(self) -> None:
        if self._worker is not None:
            logger.info("Cancellation requested by user.")
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancelling…")

    def start_comparison(self) -> None:
        old_path = Path(self.old_path_edit.text()).expanduser().resolve()
        new_path = Path(self.new_path_edit.text()).expanduser().resolve()

        if not old_path.is_file() or old_path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Invalid file", "Please select a valid PDF for the old revision.")
            return
        if not new_path.is_file() or new_path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Invalid file", "Please select a valid PDF for the new revision.")
            return

        self.toggle_controls(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.status_label.setText("Comparing…")
        self.cancel_button.setEnabled(True)
        logger.info("Starting comparison: %s vs %s", old_path, new_path)

        self._last_old_path = old_path

        self._thread = QThread(self)
        self._worker = CompareSetWorker(old_path, new_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_comparison_finished)
        self._worker.failed.connect(self.on_comparison_failed)
        self._worker.cancelled.connect(self.on_comparison_cancelled)
        self._worker.progress.connect(self.on_progress_update)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot(ComparisonResult)
    def on_comparison_finished(self, result: ComparisonResult) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.toggle_controls(True)
        self.status_label.setText("Comparison complete.")
        self.cancel_button.setEnabled(False)
        logger.info("Comparison finished.")
        if result.server_result_path:
            logger.info("Result stored at %s", result.server_result_path)
        else:
            QMessageBox.warning(
                self,
                "CompareSet",
                "Result could not be saved to the server. Please contact an administrator.",
            )

        if result.server_result_path:
            QMessageBox.information(
                self,
                "CompareSet",
                (
                    "Comparison stored on server:\n"
                    if SERVER_ONLINE
                    else "Comparison stored locally:\n"
                )
                + f"{result.server_result_path}",
            )

        self._worker = None
        self._thread = None

    @Slot(str)
    def on_comparison_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.toggle_controls(True)
        self.status_label.setText("Comparison failed.")
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "CompareSet", f"Comparison failed:\n{message}")
        self._worker = None
        self._thread = None

    @Slot()
    def on_comparison_cancelled(self) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.toggle_controls(True)
        self.status_label.setText("Comparison cancelled.")
        self.cancel_button.setEnabled(False)
        QMessageBox.information(self, "CompareSet", "Comparison was cancelled.")
        self._worker = None
        self._thread = None

    @Slot(int, int)
    def on_progress_update(self, page_index: int, total_pages: int) -> None:
        self.progress_bar.setRange(0, max(1, total_pages))
        self.progress_bar.setValue(page_index)
        self.status_label.setText(f"Processing page {page_index} of {total_pages}…")

    def on_language_changed(self, language: str) -> None:
        self.user_settings["language"] = language
        update_user_settings(self.username, language=language)
        self.current_language = language
        self.apply_language_setting()

    def apply_language_setting(self) -> None:
        self.status_label.setText(f"Ready (Language: {self.current_language})")
        translations = self._connection_texts()
        self.reload_button.setText(translations["reload_label"])
        self.update_connection_banner()

    def _connection_texts(self) -> Dict[str, str]:
        if self.current_language == "pt-BR":
            return {
                "online_status": "Status: Conectado ao servidor",
                "offline_status": "Status: Offline (sem conexão com o servidor)",
                "offline_info": (
                    "Modo offline: sem conexão com o servidor. As comparações funcionarão, "
                    "mas o histórico, logs e arquivos de saída serão salvos apenas localmente."
                ),
                "reload_label": "Recarregar",
                "still_offline": "Servidor ainda indisponível. Verifique sua VPN/conexão.",
                "reconnected": "Reconectado ao servidor.",
            }
        return {
            "online_status": "Status: Connected to server",
            "offline_status": "Status: Offline (no connection to the server)",
            "offline_info": (
                "Offline mode: no connection to the server. Comparisons will work, but history, "
                "logs and output files will be saved only locally."
            ),
            "reload_label": "Reload",
            "still_offline": "Server still unavailable. Please check your VPN/connection.",
            "reconnected": "Reconnected to server.",
        }

    def update_connection_banner(self) -> None:
        translations = self._connection_texts()
        if OFFLINE_MODE:
            self.connection_status_label.setText(translations["offline_status"])
            self.connection_status_label.setStyleSheet(
                "color: #842029; background-color: #f8d7da; "
                "border: 1px solid #f5c2c7; padding: 4px 8px; border-radius: 4px;"
            )
        else:
            self.connection_status_label.setText(translations["online_status"])
            self.connection_status_label.setStyleSheet(
                "color: #0f5132; background-color: #d1e7dd; "
                "border: 1px solid #badbcc; padding: 4px 8px; border-radius: 4px;"
            )

    def show_offline_warning_once(self) -> None:
        if OFFLINE_MODE and not self._offline_warning_shown:
            translations = self._connection_texts()
            QMessageBox.warning(self, "CompareSet", translations["offline_info"])
            self._offline_warning_shown = True

    def reload_server_status(self) -> None:
        was_offline = OFFLINE_MODE
        set_connection_state(is_server_available(SERVER_ROOT))

        if SERVER_ONLINE or CURRENT_USER in OFFLINE_ALLOWED_USERS:
            ensure_server_directories()

        self.update_connection_banner()

        if was_offline and SERVER_ONLINE:
            translations = self._connection_texts()
            self.status_label.setText(translations["reconnected"])
        elif OFFLINE_MODE:
            translations = self._connection_texts()
            QMessageBox.information(self, "CompareSet", translations["still_offline"])

    def open_history(self) -> None:
        dialog = HistoryDialog(self.username, self)
        dialog.exec()

    def open_released(self) -> None:
        dialog = ReleasedDialog(self.role, self)
        dialog.exec()

    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.username, self)
        dialog.load()
        if dialog.exec() == QDialog.Accepted:
            dialog.save()
            self.current_language = dialog.language_combo.currentText()
            self.user_settings["language"] = self.current_language
            self.apply_language_setting()

    def open_admin_dialog(self) -> None:
        dialog = AdminDialog(self)
        dialog.exec()

    def prompt_for_email_if_missing(self) -> None:
        current_email = (self.user_settings.get("email") or "").strip()
        while not current_email:
            dialog = EmailPromptDialog(self)
            if dialog.exec() == QDialog.Accepted:
                current_email = dialog.get_email()
                if current_email:
                    self.user_settings["email"] = current_email
                    update_user_settings(self.username, email=current_email)
                    break
            else:
                current_email = ""

    def toggle_controls(self, enabled: bool) -> None:
        for widget in (
            self.old_browse_button,
            self.new_browse_button,
            self.compare_button,
            self.old_path_edit,
            self.new_path_edit,
        ):
            widget.setEnabled(enabled)
        self.cancel_button.setEnabled(not enabled and self._worker is not None)

def main() -> None:
    """Entry point for the application."""

    app = QApplication(sys.argv)
    username = get_current_username()

    if OFFLINE_MODE and username not in OFFLINE_ALLOWED_USERS:
        lang_hint = (os.getenv("LANG") or "").lower()
        message = (
            "Sem conexão com o servidor. Este usuário não está autorizado a usar o CompareSet em modo offline. "
            "Feche o aplicativo e conecte-se ao servidor."
        )
        if not lang_hint.startswith("pt"):
            message = (
                "No connection to the server. This user is not allowed to use CompareSet in offline mode. "
                "Please close the application and connect to the server."
            )
        QMessageBox.critical(None, "CompareSet", message)
        sys.exit(0)

    ensure_server_directories()
    ensure_users_db_initialized()
    ensure_released_db_initialized()

    role = get_user_role(username)

    if role is None:
        QMessageBox.critical(
            None,
            "CompareSet",
            "Your user is not authorized to use CompareSet. Please contact an administrator.",
        )
        sys.exit(1)

    ensure_user_settings_db_initialized()
    user_settings = get_or_create_user_settings(username)

    init_log("session")
    configure_logging()
    write_log("=== CompareSet startup ===")
    write_log(f"User: {username}")
    write_log(f"Role: {role}")
    write_log(f"User settings file: {USER_SETTINGS_DB_PATH}")
    write_log(f"Server online: {SERVER_ONLINE}")
    if OFFLINE_MODE:
        write_log(f"Offline mode enabled. Local base: {LOCAL_BASE_DIR}")

    window = MainWindow(username, role, user_settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
