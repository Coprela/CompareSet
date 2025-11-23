#!/usr/bin/env python3
"""CompareSet desktop application with Developer Layout Mode for draggable panels."""

from __future__ import annotations

import compareset_engine as compare_engine
import json
import logging
import os
import shutil
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QEvent, QPoint, QRect, QSize, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QShortcut
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
    QMenu,
    QMenuBar,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QProgressBar,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from compareset_engine import (
    ComparisonResult,
    PageDiffSummary,
    configure_logging,
    init_log,
    logger,
    run_comparison,
    write_log,
)
import compareset_env as csenv
from developer_tools_dialog import DeveloperToolsDialog
from compareset_env import (
    CURRENT_USER,
    IS_TESTER,
    OFFLINE_MODE,
    SERVER_ONLINE,
    RESULTS_ROOT,
    HISTORY_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    initialize_environment,
    is_super_admin,
    is_offline_tester,
    is_dev_mode,
    get_dev_settings,
    DEV_SETTINGS_PATH,
    get_output_directory_for_user,
)
from developer_layout_designer import LayoutDesignerDialog

SERVER_ROOT = csenv.SERVER_ROOT
SERVER_DATA_ROOT = csenv.SERVER_DATA_ROOT
SERVER_RESULTS_ROOT = csenv.SERVER_RESULTS_ROOT
SERVER_LOGS_ROOT = csenv.SERVER_LOGS_ROOT
SERVER_ERROR_LOGS_ROOT = csenv.SERVER_ERROR_LOGS_ROOT
SERVER_CONFIG_ROOT = csenv.SERVER_CONFIG_ROOT
SERVER_RELEASED_ROOT = csenv.SERVER_RELEASED_ROOT

LOCAL_APPDATA = csenv.LOCAL_APPDATA
LOCAL_BASE_DIR = csenv.LOCAL_BASE_DIR
LOCAL_HISTORY_DIR = csenv.LOCAL_HISTORY_DIR
LOCAL_LOG_DIR = csenv.LOCAL_LOG_DIR
LOCAL_OUTPUT_DIR = csenv.LOCAL_OUTPUT_DIR
LOCAL_CONFIG_DIR = csenv.LOCAL_CONFIG_DIR
LOCAL_RELEASED_DIR = csenv.LOCAL_RELEASED_DIR

SERVER_ONLINE = csenv.SERVER_ONLINE
OFFLINE_MODE = csenv.OFFLINE_MODE
DATA_ROOT = csenv.DATA_ROOT
RESULTS_ROOT = csenv.RESULTS_ROOT
LOGS_ROOT = csenv.LOGS_ROOT
ERROR_LOGS_ROOT = csenv.ERROR_LOGS_ROOT
CONFIG_ROOT = csenv.CONFIG_ROOT
RELEASED_ROOT = csenv.RELEASED_ROOT
HISTORY_DIR = csenv.HISTORY_DIR
LOG_DIR = csenv.LOG_DIR


def is_server_available(server_root: str) -> bool:
    """Return True when the UNC server root exists and is reachable."""

    return csenv.is_server_available(server_root)


def set_connection_state(server_online: bool) -> None:
    """Update global flags and filesystem paths for the current connection state."""

    global SERVER_ONLINE, OFFLINE_MODE
    global DATA_ROOT, RESULTS_ROOT, LOGS_ROOT, ERROR_LOGS_ROOT, CONFIG_ROOT, RELEASED_ROOT
    global HISTORY_DIR, LOG_DIR, OUTPUT_DIR, USERS_DB_PATH, USER_SETTINGS_DB_PATH, RELEASED_DB_PATH

    csenv.set_connection_state(server_online)
    try:
        compare_engine.set_connection_state(server_online)
    except Exception:
        pass

    SERVER_ONLINE = csenv.SERVER_ONLINE
    OFFLINE_MODE = csenv.OFFLINE_MODE
    DATA_ROOT = csenv.DATA_ROOT
    RESULTS_ROOT = csenv.RESULTS_ROOT
    LOGS_ROOT = csenv.LOGS_ROOT
    ERROR_LOGS_ROOT = csenv.ERROR_LOGS_ROOT
    CONFIG_ROOT = csenv.CONFIG_ROOT
    RELEASED_ROOT = csenv.RELEASED_ROOT
    HISTORY_DIR = csenv.HISTORY_DIR
    LOG_DIR = csenv.LOG_DIR
    OUTPUT_DIR = str(get_output_directory_for_user(CURRENT_USER))
USERS_DB_PATH = os.path.join(CONFIG_ROOT, "users.sqlite")
USER_SETTINGS_DB_PATH = os.path.join(CONFIG_ROOT, "user_settings.sqlite")
RELEASED_DB_PATH = os.path.join(CONFIG_ROOT, "released.sqlite")
DEV_LAYOUT_PATH = Path(DEV_SETTINGS_PATH).with_name("dev_layout.json")

def make_long_path(path: str) -> str:
    """Return a Windows long-path-safe absolute path."""

    return csenv.make_long_path(path)


def get_current_username() -> str:
    """Return the current Windows username for authentication."""

    return csenv.get_current_username()


def ensure_server_directories() -> None:
    """Ensure all shared directories exist."""

    csenv.ensure_server_directories()


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


class LayoutEditFilter(QObject):
    """Lightweight event filter enabling drag moves for target widgets."""

    def __init__(self, window: QMainWindow, key: str):
        super().__init__(window)
        self.window = window
        self.key = key
        self._dragging = False
        self._offset = QPoint()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if not getattr(self.window, "layout_mode_enabled", False):
            return False

        if event.type() == QEvent.MouseButtonPress and getattr(event, "button", lambda: None)() == Qt.LeftButton:
            parent_origin = obj.parent().mapToGlobal(QPoint(0, 0)) if obj.parent() else QPoint(0, 0)
            self._offset = event.globalPosition().toPoint() - parent_origin - obj.pos()
            self._dragging = True
            obj.setCursor(Qt.SizeAllCursor)
            return True
        if event.type() == QEvent.MouseMove and self._dragging:
            parent_origin = obj.parent().mapToGlobal(QPoint(0, 0)) if obj.parent() else QPoint(0, 0)
            new_pos = event.globalPosition().toPoint() - parent_origin - self._offset
            obj.move(new_pos)
            return True
        if event.type() == QEvent.MouseButtonRelease:
            if self._dragging:
                obj.setCursor(Qt.ArrowCursor)
            self._dragging = False
            return False
        return False


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
        base_output_dir = Path(get_output_directory_for_user(username))
        self.user_results_dir = str(base_output_dir / username)
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

        # Mapping of widgets that can be styled or text-edited without touching code.
        self._editable_widgets: Dict[str, Dict[str, Union[QWidget, str, bool]]] = {}
        self._widget_defaults: Dict[str, Dict[str, Optional[str]]] = {}
        self._widget_overrides: Dict[str, Dict[str, str]] = {}
        self._geometry_overrides: Dict[str, Dict[str, int]] = {}
        self._widget_actions: Dict[str, Dict[str, str]] = {}
        self._dynamic_button_defs: Dict[str, Dict[str, Any]] = {}
        self._dynamic_buttons: Dict[str, QPushButton] = {}

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

        self.status_label = QLabel("Ready")
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

        self.resize(900, 620)
        central_widget = QWidget()
        central_widget.setObjectName("layout_canvas")
        central_widget.setLayout(None)
        central_widget.setMinimumSize(720, 520)
        central_widget.setAttribute(Qt.WA_StyledBackground, True)
        self.layout_canvas = central_widget
        self.layout_mode_enabled = False
        self._dev_features_active = False
        self._dev_unlocked = False
        self._developer_menu_initialized = False
        self._layout_targets: Dict[str, QWidget] = {}
        self._layout_filters: Dict[str, LayoutEditFilter] = {}
        self._default_layouts: Dict[str, QRect] = {}
        self._original_styles: Dict[str, str] = {}

        secret_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Shift+D"), self)
        secret_shortcut.activated.connect(self._prompt_dev_password)

        self.layout_indicator = QLabel("Layout Mode ON", central_widget)
        self.layout_indicator.setStyleSheet(
            "background-color: #fff4ce; color: #664d03; border: 1px dashed #f0ad4e; "
            "padding: 4px 8px; border-radius: 4px;"
        )
        self.layout_indicator.hide()

        file_layout = QGridLayout()
        self.old_label = QLabel("Old revision (PDF)")
        self.new_label = QLabel("New revision (PDF)")
        file_layout.addWidget(self.old_label, 0, 0)
        file_layout.addWidget(self.old_path_edit, 0, 1)
        file_layout.addWidget(self.old_browse_button, 0, 2)
        file_layout.addWidget(self.new_label, 1, 0)
        file_layout.addWidget(self.new_path_edit, 1, 1)
        file_layout.addWidget(self.new_browse_button, 1, 2)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.history_button)
        button_layout.addWidget(self.released_button)
        button_layout.addWidget(self.settings_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.compare_button)

        self.top_toolbar_frame = QFrame(central_widget)
        self.top_toolbar_frame.setObjectName("top_toolbar")
        top_layout = QVBoxLayout(self.top_toolbar_frame)
        top_layout.setContentsMargins(8, 8, 8, 8)
        top_layout.addLayout(file_layout)
        top_layout.addSpacing(8)
        top_layout.addLayout(button_layout)
        self.toolbar_dynamic_layout = QHBoxLayout()
        self.toolbar_dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_dynamic_layout.addStretch()
        top_layout.addSpacing(4)
        top_layout.addLayout(self.toolbar_dynamic_layout)

        self.progress_frame = QFrame(central_widget)
        self.progress_frame.setObjectName("progress_panel")
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(8, 8, 8, 8)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        self.progress_dynamic_layout = QHBoxLayout()
        self.progress_dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_dynamic_layout.addStretch()
        progress_layout.addSpacing(4)
        progress_layout.addLayout(self.progress_dynamic_layout)

        self.admin_frame = QFrame(central_widget)
        self.admin_frame.setObjectName("admin_panel")
        if self.role == "admin":
            self.admin_button = QPushButton("Administração")
            self.admin_button.clicked.connect(self.open_admin_dialog)
            admin_layout = QVBoxLayout(self.admin_frame)
            admin_layout.setContentsMargins(8, 8, 8, 8)
            admin_layout.addWidget(self.admin_button)
            admin_layout.addWidget(self.log_view)
            self.admin_dynamic_layout = QVBoxLayout()
            admin_layout.addLayout(self.admin_dynamic_layout)
        else:
            self.admin_frame.setVisible(False)

        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.addWidget(self.connection_status_label, 1)
        status_bar.addPermanentWidget(self.reload_button)

        self.setStatusBar(status_bar)
        self.apply_language_setting()
        self._register_editable_widget("old_label", self.old_label, display_name="Old PDF label", allow_geometry=True)
        self._register_editable_widget("new_label", self.new_label, display_name="New PDF label", allow_geometry=True)
        self._register_editable_widget(
            "old_path_edit", self.old_path_edit, display_name="Old path input", allow_style=True, allow_geometry=True, allow_text=True
        )
        self._register_editable_widget(
            "new_path_edit", self.new_path_edit, display_name="New path input", allow_style=True, allow_geometry=True, allow_text=True
        )
        self._register_editable_widget(
            "old_browse_button",
            self.old_browse_button,
            display_name="Old Browse button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "new_browse_button",
            self.new_browse_button,
            display_name="New Browse button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "compare_button",
            self.compare_button,
            display_name="Compare button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "cancel_button",
            self.cancel_button,
            display_name="Cancel button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "history_button",
            self.history_button,
            display_name="History button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "released_button",
            self.released_button,
            display_name="Released button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "settings_button",
            self.settings_button,
            display_name="Settings button",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "status_label", self.status_label, display_name="Status message", allow_style=True, allow_text=True
        )
        self._register_editable_widget(
            "connection_status", self.connection_status_label, display_name="Connection banner", allow_style=True
        )
        self._register_editable_widget(
            "progress_bar",
            self.progress_bar,
            display_name="Progress bar",
            allow_text=False,
            allow_style=True,
            allow_geometry=True,
        )
        self._register_editable_widget(
            "reload_button",
            self.reload_button,
            display_name="Reload connection",
            allow_icon=True,
            allow_action=True,
        )
        self._register_editable_widget(
            "log_view",
            self.log_view,
            display_name="Admin log",
            allow_text=False,
            allow_style=True,
            allow_geometry=True,
        )
        if self.admin_button is not None:
            self._register_editable_widget(
                "admin_button",
                self.admin_button,
                display_name="Admin button",
                allow_icon=True,
                allow_action=True,
            )
        self.setCentralWidget(central_widget)
        self._register_layout_target("top_toolbar", self.top_toolbar_frame)
        self._register_layout_target("progress_panel", self.progress_frame)
        if self.admin_frame.isVisible():
            self._register_layout_target("admin_panel", self.admin_frame)
        self._dynamic_parent_layouts = {
            "top_toolbar": self.toolbar_dynamic_layout,
            "progress_panel": self.progress_dynamic_layout,
            "admin_panel": getattr(self, "admin_dynamic_layout", None),
        }
        self._register_editable_widget(
            "top_toolbar",
            self.top_toolbar_frame,
            display_name="Toolbar panel",
            allow_text=False,
            allow_style=True,
            allow_geometry=True,
        )
        self._register_editable_widget(
            "progress_panel",
            self.progress_frame,
            display_name="Progress panel",
            allow_text=False,
            allow_style=True,
            allow_geometry=True,
        )
        if self.admin_frame.isVisible():
            self._register_editable_widget(
                "admin_panel",
                self.admin_frame,
                display_name="Admin panel",
                allow_text=False,
                allow_style=True,
                allow_geometry=True,
            )

        self._apply_default_layout_geometry()
        # Developer UI remains hidden until unlocked via the secret shortcut.
        # This prevents the Developer menu from appearing by default even when
        # dev_mode is enabled in the configuration.
        if self._is_developer_enabled():
            self._init_developer_menu()
            self.load_dev_layout()
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
        if self.current_language == "pt-BR":
            self.old_label.setText("Revisão antiga (PDF)")
            self.new_label.setText("Nova revisão (PDF)")
            self.old_browse_button.setText("Procurar…")
            self.new_browse_button.setText("Procurar…")
            self.compare_button.setText("Comparar")
            self.cancel_button.setText("Cancelar")
            self.history_button.setText("Meu histórico")
            self.released_button.setText("Liberados")
            self.settings_button.setText("Configurações")
            self.status_label.setText("Pronto")
        else:
            self.old_label.setText("Old revision (PDF)")
            self.new_label.setText("New revision (PDF)")
            self.old_browse_button.setText("Browse…")
            self.new_browse_button.setText("Browse…")
            self.compare_button.setText("Compare")
            self.cancel_button.setText("Cancel")
            self.history_button.setText("My History")
            self.released_button.setText("Released")
            self.settings_button.setText("Settings")
            self.status_label.setText("Ready")
        translations = self._connection_texts()
        self.reload_button.setText(translations["reload_label"])
        self.update_connection_banner()
        self._refresh_widget_defaults_for_language()
        self._reapply_widget_overrides()

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

        if SERVER_ONLINE or is_offline_tester(CURRENT_USER):
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

    def _register_editable_widget(
        self,
        key: str,
        widget: QWidget,
        *,
        display_name: Optional[str] = None,
        allow_text: bool = True,
        allow_style: bool = True,
        allow_geometry: bool = True,
        allow_icon: bool = False,
        allow_action: bool = False,
    ) -> None:
        """Mark a widget as editable inside the no-code layout designer."""

        self._editable_widgets[key] = {
            "widget": widget,
            "display_name": display_name or key,
            "allow_text": allow_text,
            "allow_style": allow_style,
            "allow_geometry": allow_geometry,
            "allow_icon": allow_icon,
            "allow_action": allow_action,
        }
        default_text = widget.text() if hasattr(widget, "text") else None
        self._widget_defaults[key] = {
            "text": default_text,
            "style": widget.styleSheet() or "",
            "icon": None,
            "action": None,
        }
        if allow_action and isinstance(widget, QPushButton):
            widget.clicked.connect(lambda checked=False, k=key: self._invoke_custom_action(k))

    def _refresh_widget_defaults_for_language(self) -> None:
        """Refresh baseline texts when the UI language changes."""

        for key, defaults in self._widget_defaults.items():
            if key in self._widget_overrides and self._widget_overrides[key].get("text"):
                continue
            widget = self._editable_widgets.get(key, {}).get("widget")
            if widget is None:
                continue
            if hasattr(widget, "text"):
                defaults["text"] = widget.text()

    def apply_widget_overrides(self, key: str, overrides: Dict[str, str]) -> None:
        """Apply persisted or in-flight overrides to a registered widget."""

        info = self._editable_widgets.get(key)
        if not info:
            return
        widget: QWidget = info.get("widget")  # type: ignore[assignment]
        defaults = self._widget_defaults.get(key, {"text": None, "style": ""})
        allow_text = bool(info.get("allow_text", True))
        allow_style = bool(info.get("allow_style", True))
        allow_icon = bool(info.get("allow_icon", False))
        allow_action = bool(info.get("allow_action", False))

        text_override = overrides.get("text") if allow_text else None
        style_override = overrides.get("style") if allow_style else None
        icon_override = overrides.get("icon") if allow_icon else None
        geometry_override = overrides.get("geometry") if info.get("allow_geometry", True) else None
        action_override = overrides.get("action") if allow_action else None

        text_value = text_override if text_override is not None else defaults.get("text")
        if allow_text and text_value is not None and hasattr(widget, "setText"):
            widget.setText(str(text_value))

        style_value = style_override if style_override is not None else defaults.get("style", "")
        if allow_style:
            widget.setStyleSheet(style_value or "")

        if allow_icon and isinstance(widget, QPushButton):
            if isinstance(icon_override, str) and icon_override:
                widget.setIcon(QIcon(icon_override))
            elif icon_override == "":
                widget.setIcon(QIcon())
            elif isinstance(defaults.get("icon"), str) and defaults.get("icon"):
                widget.setIcon(QIcon(str(defaults.get("icon"))))

        if geometry_override:
            self.apply_geometry_override(key, geometry_override)

        if allow_action:
            if isinstance(action_override, dict) and action_override.get("type"):
                self._widget_actions[key] = action_override
            elif action_override == {}:
                self._widget_actions.pop(key, None)

        cleaned: Dict[str, str] = {}
        if text_override is not None and text_override != defaults.get("text"):
            cleaned["text"] = str(text_override)
        if style_override is not None and style_override.strip() != (defaults.get("style") or "").strip():
            cleaned["style"] = str(style_override)
        if allow_icon and icon_override is not None:
            cleaned["icon"] = str(icon_override)
        if allow_action and isinstance(action_override, dict):
            cleaned["action"] = action_override
        if geometry_override:
            cleaned["geometry"] = geometry_override

        if cleaned:
            self._widget_overrides[key] = cleaned
        elif key in self._widget_overrides:
            del self._widget_overrides[key]

        if key in self._dynamic_button_defs:
            if allow_text and hasattr(widget, "text"):
                self._dynamic_button_defs[key]["text"] = widget.text()
            if allow_icon:
                self._dynamic_button_defs[key]["icon"] = str(icon_override or "")
            if allow_action and isinstance(action_override, dict):
                self._dynamic_button_defs[key]["action"] = action_override

    def _reapply_widget_overrides(self) -> None:
        for key, overrides in list(self._widget_overrides.items()):
            self.apply_widget_overrides(key, overrides)

    def _normalize_geometry(self, widget: QWidget, geometry_data: Dict[str, Any]) -> Optional[QRect]:
        try:
            x = int(geometry_data.get("x", widget.x()))
            y = int(geometry_data.get("y", widget.y()))
            w = int(geometry_data.get("width", widget.width()))
            h = int(geometry_data.get("height", widget.height()))
            rect = QRect(x, y, max(1, w), max(1, h))
        except Exception:
            return None
        if not self._is_reasonable_geometry(rect):
            return None
        return rect

    def apply_geometry_override(self, key: str, geometry_data: Dict[str, Any]) -> None:
        widget = self._editable_widgets.get(key, {}).get("widget") or self._layout_targets.get(key)
        if widget is None:
            return
        rect = self._normalize_geometry(widget, geometry_data)
        if rect is None:
            return
        widget.setGeometry(rect)
        widget.setMinimumSize(rect.width(), rect.height())
        self._geometry_overrides[key] = {
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        }
        if key in self._widget_overrides:
            self._widget_overrides[key]["geometry"] = self._geometry_overrides[key]
        else:
            self._widget_overrides[key] = {"geometry": self._geometry_overrides[key]}

        if key in self._dynamic_button_defs:
            self._dynamic_button_defs[key]["geometry"] = self._geometry_overrides[key]

    def _add_widget_to_layout(self, layout, widget: QWidget) -> None:
        if hasattr(layout, "insertWidget"):
            insert_at = max(layout.count() - 1, 0)
            layout.insertWidget(insert_at, widget)
        elif hasattr(layout, "addWidget"):
            layout.addWidget(widget)

    def _create_dynamic_button(self, definition: Dict[str, Any]) -> Optional[QPushButton]:
        parent_key = definition.get("parent", "top_toolbar")
        layout = self._dynamic_parent_layouts.get(parent_key)
        if layout is None:
            return None
        button_id = definition.get("id") or f"dynamic_{len(self._dynamic_button_defs) + 1}"
        button = QPushButton(definition.get("text") or "Novo botão")
        button.setObjectName(button_id)
        if definition.get("icon"):
            button.setIcon(QIcon(str(definition.get("icon"))))
        self._add_widget_to_layout(layout, button)
        button.show()
        if layout.parentWidget() is not None:
            layout.parentWidget().updateGeometry()
        definition["id"] = button_id
        definition.setdefault("display_name", definition.get("text") or button_id)
        self._dynamic_button_defs[button_id] = definition
        self._dynamic_buttons[button_id] = button
        self._register_editable_widget(
            button_id,
            button,
            display_name=definition.get("display_name", button_id),
            allow_icon=True,
            allow_action=True,
        )
        action_cfg = definition.get("action") if isinstance(definition.get("action"), dict) else None
        if action_cfg:
            self._widget_actions[button_id] = action_cfg
        if definition.get("geometry"):
            self.apply_geometry_override(button_id, definition.get("geometry", {}))
        return button

    def _clear_dynamic_buttons(self) -> None:
        for button in self._dynamic_buttons.values():
            button.setParent(None)
        self._dynamic_buttons.clear()
        for key in list(self._widget_overrides.keys()):
            if key.startswith("dynamic_") or key in self._dynamic_button_defs:
                self._widget_overrides.pop(key, None)
        self._dynamic_button_defs.clear()

    def _rebuild_dynamic_buttons(self, definitions: List[Dict[str, Any]]) -> None:
        self._clear_dynamic_buttons()
        for definition in definitions:
            if isinstance(definition, dict):
                self._create_dynamic_button(definition)

    def create_dynamic_button(self, definition: Dict[str, Any]) -> Optional[str]:
        button = self._create_dynamic_button(definition)
        return button.objectName() if button else None

    def get_dynamic_button_definitions(self) -> List[Dict[str, Any]]:
        return list(self._dynamic_button_defs.values())

    def get_dynamic_parents(self) -> List[str]:
        return [key for key, layout in self._dynamic_parent_layouts.items() if layout is not None]

    def _invoke_custom_action(self, key: str) -> None:
        action = self._widget_actions.get(key)
        if not action:
            return
        action_type = action.get("type")
        target = action.get("value") or action.get("target")
        try:
            if action_type == "url" and target:
                QDesktopServices.openUrl(QUrl(str(target)))
            elif action_type == "file" and target:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
            elif action_type in {"method", "dialog"} and target:
                func = getattr(self, str(target), None)
                if callable(func):
                    func()
            else:
                logger.info("Custom action ignored for %s", key)
        except Exception:
            logger.exception("Failed to execute custom action for %s", key)

    def get_editable_widget_catalog(self) -> Dict[str, Dict[str, Union[QWidget, str, bool]]]:
        """Expose editable widget metadata to the layout designer dialog."""

        return self._editable_widgets

    def get_widget_state(self, key: str) -> Dict[str, Any]:
        widget = self._editable_widgets.get(key, {}).get("widget") or self._layout_targets.get(key)
        return {
            "widget": widget,
            "defaults": self._widget_defaults.get(key, {}),
            "overrides": self._widget_overrides.get(key, {}),
            "geometry": self._geometry_overrides.get(key, {}),
            "action": self._widget_actions.get(key, {}),
        }

    def _register_layout_target(self, key: str, widget: QWidget) -> None:
        widget.setAttribute(Qt.WA_StyledBackground, True)
        self._layout_targets[key] = widget
        self._original_styles[key] = widget.styleSheet()
        handler = LayoutEditFilter(self, key)
        widget.installEventFilter(handler)
        self._layout_filters[key] = handler

    def _apply_default_layout_geometry(self) -> None:
        canvas_size: QSize = self.layout_canvas.size() or QSize(900, 620)
        width = max(640, canvas_size.width() - 20)
        y = 10
        for key in ("top_toolbar", "progress_panel", "admin_panel"):
            widget = self._layout_targets.get(key)
            if widget is None or not widget.isVisible():
                continue
            hint = widget.sizeHint() or QSize(width, 120)
            height = max(100 if key != "admin_panel" else 200, hint.height() + 16)
            widget.setGeometry(10, y, width, height)
            self._default_layouts[key] = widget.geometry()
            y += height + 10
        self.layout_indicator.move(16, 10)

    def _is_reasonable_geometry(self, rect: QRect) -> bool:
        canvas = self.layout_canvas.geometry()
        if rect.width() < 20 or rect.height() < 20:
            return False
        if rect.x() > canvas.width() * 2 or rect.y() > canvas.height() * 2:
            return False
        if rect.x() + rect.width() < -canvas.width() or rect.y() + rect.height() < -canvas.height():
            return False
        return True

    def _apply_saved_layout(self, layout_data: Dict[str, Dict[str, int]]) -> None:
        for key, geom in layout_data.items():
            widget = self._layout_targets.get(key)
            if widget is None:
                continue
            rect = self._normalize_geometry(widget, geom)
            if rect is None:
                continue
            widget.setGeometry(rect)

    def _apply_saved_widget_overrides(self, widget_data: Dict[str, Dict[str, str]]) -> None:
        self._widget_overrides = {}
        self._geometry_overrides = {}
        for key, overrides in widget_data.items():
            if not isinstance(overrides, dict):
                continue
            self.apply_widget_overrides(key, overrides)

    def reset_widget_overrides(self) -> None:
        self._widget_overrides = {}
        self._geometry_overrides = {}
        self._widget_actions = {}
        for key in self._editable_widgets:
            self.apply_widget_overrides(key, {})

    def _is_developer_enabled(self) -> bool:
        """Return True only when the developer UI has been explicitly unlocked."""

        return bool(self._dev_unlocked)

    def save_dev_layout(self) -> None:
        if not self._is_developer_enabled():
            return
        layout_data: Dict[str, Any] = {"frames": {}, "widgets": {}, "dynamic_buttons": []}
        for key, widget in self._layout_targets.items():
            geom = widget.geometry()
            layout_data["frames"][key] = {
                "x": geom.x(),
                "y": geom.y(),
                "width": geom.width(),
                "height": geom.height(),
            }
        for key in self._editable_widgets:
            overrides = dict(self._widget_overrides.get(key, {}))
            if key in self._geometry_overrides:
                overrides.setdefault("geometry", self._geometry_overrides[key])
            if overrides:
                layout_data["widgets"][key] = overrides
        if self._dynamic_button_defs:
            layout_data["dynamic_buttons"] = list(self._dynamic_button_defs.values())
        DEV_LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEV_LAYOUT_PATH, "w", encoding="utf-8") as handle:
            json.dump(layout_data, handle, indent=2)
        QMessageBox.information(self, "Layout", "Developer layout saved.")

    def load_dev_layout(self) -> None:
        if not self._is_developer_enabled():
            return
        if not DEV_LAYOUT_PATH.exists():
            return
        try:
            with open(DEV_LAYOUT_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("Layout file corrupted")
            frame_data = data.get("frames") if "frames" in data else data
            widget_data = data.get("widgets", {}) if isinstance(data.get("widgets", {}), dict) else {}
            geometry_data = data.get("widget_geometries", {}) if isinstance(data.get("widget_geometries", {}), dict) else {}
            dynamic_defs = data.get("dynamic_buttons", []) if isinstance(data.get("dynamic_buttons", []), list) else []
            self._clear_dynamic_buttons()
            if dynamic_defs:
                self._rebuild_dynamic_buttons(dynamic_defs)
            if isinstance(frame_data, dict):
                self._apply_saved_layout({k: v for k, v in frame_data.items() if isinstance(v, dict)})
            if widget_data:
                self._apply_saved_widget_overrides(widget_data)
            for key, geom in geometry_data.items():
                if isinstance(geom, dict):
                    self.apply_geometry_override(key, geom)
        except Exception:
            logger.warning("Unable to load developer layout file. Reverting to defaults.", exc_info=True)
            self.status_label.setText("Developer layout inválido. Usando padrão.")
            self._apply_default_layout_geometry()

    def reset_dev_layout(self) -> None:
        if DEV_LAYOUT_PATH.exists():
            try:
                DEV_LAYOUT_PATH.unlink()
            except Exception:
                pass
        self._clear_dynamic_buttons()
        self._apply_default_layout_geometry()
        self.reset_widget_overrides()
        QMessageBox.information(self, "Layout", "Layout reset to defaults.")

    def toggle_layout_mode(self, checked: Optional[bool] = None) -> None:
        if not self._is_developer_enabled():
            QMessageBox.information(
                self,
                "Layout",
                "Developer Layout Mode is only available when developer mode is enabled.",
            )
            return
        new_state = bool(checked) if checked is not None else not self.layout_mode_enabled
        self.layout_mode_enabled = new_state
        if hasattr(self, "layout_mode_action"):
            self.layout_mode_action.setChecked(new_state)
        self._update_layout_mode_visuals()

    def _update_layout_mode_visuals(self) -> None:
        self.layout_indicator.setVisible(self.layout_mode_enabled)
        for key, widget in self._layout_targets.items():
            base_style = self._original_styles.get(key, "")
            if self.layout_mode_enabled:
                border = "border: 1px dashed #0078d4;"
                widget.setStyleSheet(f"{base_style}\n{border}" if base_style else border)
                widget.raise_()
            else:
                widget.setStyleSheet(base_style)
        if self.layout_mode_enabled:
            self.layout_indicator.raise_()

    def _prompt_dev_password(self) -> None:
        if self._dev_unlocked:
            return
        password, ok = QInputDialog.getText(
            self,
            "Developer mode",
            "Enter developer password:",
            QLineEdit.Password,
        )
        if not ok:
            return
        if password != "doliveira12@CompareSet2025":
            QMessageBox.warning(self, "Developer mode", "Invalid password.")
            return
        self._dev_unlocked = True
        self._unlock_developer_mode()

    def _unlock_developer_mode(self) -> None:
        if not getattr(self, "_developer_menu_initialized", False):
            self._init_developer_menu()
        else:
            self._update_developer_menu_state()
        if is_dev_mode():
            self.load_dev_layout()
        QMessageBox.information(
            self,
            "Developer mode",
            "Developer mode unlocked for this session.",
        )

    def _init_developer_menu(self) -> None:
        if getattr(self, "_developer_menu_initialized", False):
            return
        menu_bar: QMenuBar = self.menuBar() or QMenuBar(self)
        dev_menu = QMenu("Developer", self)
        menu_bar.addMenu(dev_menu)

        tools_action = QAction("Developer Tools…", self)
        tools_action.triggered.connect(self.open_developer_tools)
        dev_menu.addAction(tools_action)

        self.layout_designer_action = QAction("Layout Designer…", self)
        self.layout_designer_action.triggered.connect(self.open_layout_designer)
        dev_menu.addAction(self.layout_designer_action)

        self.layout_mode_action = QAction("Layout Editor…", self)
        self.layout_mode_action.setCheckable(True)
        self.layout_mode_action.triggered.connect(self.toggle_layout_mode)
        dev_menu.addAction(self.layout_mode_action)

        self.save_layout_action = QAction("Save Layout", self)
        self.save_layout_action.triggered.connect(self.save_dev_layout)
        dev_menu.addAction(self.save_layout_action)

        self.reset_layout_action = QAction("Reset Layout to Default", self)
        self.reset_layout_action.triggered.connect(self.reset_dev_layout)
        dev_menu.addAction(self.reset_layout_action)

        self._developer_menu_initialized = True
        self._update_developer_menu_state()

    def _update_developer_menu_state(self) -> None:
        dev_enabled = self._is_developer_enabled()
        for action in (
            getattr(self, "layout_designer_action", None),
            getattr(self, "layout_mode_action", None),
            getattr(self, "save_layout_action", None),
            getattr(self, "reset_layout_action", None),
        ):
            if action is not None:
                action.setEnabled(dev_enabled)
        if not dev_enabled and self.layout_mode_enabled:
            self.layout_mode_enabled = False
            if hasattr(self, "layout_mode_action"):
                self.layout_mode_action.setChecked(False)
            self._update_layout_mode_visuals()
        if dev_enabled and not self._dev_features_active:
            self.load_dev_layout()
        self._dev_features_active = dev_enabled

    def open_developer_tools(self) -> None:
        dialog = DeveloperToolsDialog(
            self,
            get_dev_settings(),
            layout_mode_active=self.layout_mode_enabled,
            developer_enabled=self._is_developer_enabled(),
        )
        dialog.settings_applied.connect(self._update_developer_menu_state)
        dialog.layout_mode_toggled.connect(self.toggle_layout_mode)
        dialog.save_layout_requested.connect(self.save_dev_layout)
        dialog.reset_layout_requested.connect(self.reset_dev_layout)
        dialog.exec()

    def open_layout_designer(self) -> None:
        if not self._is_developer_enabled():
            QMessageBox.information(
                self,
                "Layout Designer",
                "O Designer de Layout só fica disponível quando o modo desenvolvedor está ativo.",
            )
            return
        dialog = LayoutDesignerDialog(self)
        dialog.exec()

def main() -> None:
    """Entry point for the application."""

    app = QApplication(sys.argv)
    initialize_environment()
    set_connection_state(csenv.SERVER_ONLINE)

    username = get_current_username()

    if not csenv.SERVER_ONLINE and not csenv.IS_TESTER:
        QMessageBox.critical(
            None,
            "CompareSet",
            "You are offline or the CompareSet server is not reachable.\n"
            "Please connect to GlobalProtect/VPN and try again.",
        )
        sys.exit(1)

    window_title_suffix = " [TEST MODE - OFFLINE]" if OFFLINE_MODE and csenv.IS_TESTER else ""

    ensure_server_directories()
    ensure_users_db_initialized()
    ensure_released_db_initialized()

    role = get_user_role(username)

    if is_super_admin(username):
        role = "admin"

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
    if window_title_suffix:
        window.setWindowTitle(f"CompareSet{window_title_suffix}")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
