#!/usr/bin/env python3
#!/usr/bin/env python3
"""Qt application entry point for CompareSet.

This module hosts the GUI, settings, developer/test toggles, and main entry
point. It consumes :mod:`compareset_engine` for comparison work and
:mod:`compareset_env` for configuration and connectivity state.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from compareset_engine import ComparisonResult, run_comparison
import compareset_env as csenv
from compareset_env import (
    CONFIG_ROOT,
    CURRENT_USER,
    DEV_MODE,
    get_current_username,
    get_output_directory_for_user,
    is_server_available,
    is_super_admin,
    make_long_path,
    set_connection_state,
    set_dev_server_override,
)

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Translation utilities
# ----------------------------------------------------------------------------
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en-US": {
        "title": "CompareSet",
        "old_file": "Old PDF",
        "new_file": "New PDF",
        "browse": "Browse",
        "run": "Run Comparison",
        "settings": "Settings",
        "status_ready": "Ready",
        "status_offline": "Server unavailable. Enable dev mode to proceed offline.",
        "error_no_files": "Please choose both files before running a comparison.",
        "comparison_complete": "Comparison finished.",
        "comparison_failed": "Comparison failed: {error}",
        "settings_title": "Settings",
        "language": "Language",
        "theme": "Theme",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "save": "Save",
        "cancel": "Cancel",
        "dev_options": "Developer / Tester",
        "server_override": "Server connection",
        "server_auto": "Use real server state",
        "server_force_on": "Force online",
        "server_force_off": "Force offline",
        "role_override": "Role override",
        "role_none": "No override",
        "role_viewer": "Viewer",
        "role_user": "User",
        "role_admin": "Admin",
        "offline_block": "The server is not reachable. Contact IT or use the dev launcher for offline testing.",
        "open_old": "Select the old PDF",
        "open_new": "Select the new PDF",
    },
    "pt-BR": {
        "title": "CompareSet",
        "old_file": "PDF antigo",
        "new_file": "PDF novo",
        "browse": "Procurar",
        "run": "Executar comparação",
        "settings": "Configurações",
        "status_ready": "Pronto",
        "status_offline": "Servidor indisponível. Habilite modo de teste para seguir offline.",
        "error_no_files": "Selecione os dois arquivos antes de executar a comparação.",
        "comparison_complete": "Comparação concluída.",
        "comparison_failed": "Falha na comparação: {error}",
        "settings_title": "Configurações",
        "language": "Idioma",
        "theme": "Tema",
        "theme_light": "Claro",
        "theme_dark": "Escuro",
        "save": "Salvar",
        "cancel": "Cancelar",
        "dev_options": "Desenvolvedor / Teste",
        "server_override": "Conexão com servidor",
        "server_auto": "Usar estado real do servidor",
        "server_force_on": "Forçar online",
        "server_force_off": "Forçar offline",
        "role_override": "Substituir função",
        "role_none": "Sem substituição",
        "role_viewer": "Visualizador",
        "role_user": "Usuário",
        "role_admin": "Administrador",
        "offline_block": "O servidor não está acessível. Contate o suporte ou use o launcher de teste.",
        "open_old": "Selecionar PDF antigo",
        "open_new": "Selecionar PDF novo",
    },
}


class Translator:
    def __init__(self, language: str):
        self.language = language if language in TRANSLATIONS else "en-US"

    def set_language(self, language: str) -> None:
        self.language = language if language in TRANSLATIONS else "en-US"

    def tr(self, key: str) -> str:
        return TRANSLATIONS.get(self.language, TRANSLATIONS["en-US"]).get(key, key)


# ----------------------------------------------------------------------------
# Settings persistence
# ----------------------------------------------------------------------------
USERS_DB_PATH = os.path.join(CONFIG_ROOT, "users.sqlite")
USER_SETTINGS_DB_PATH = os.path.join(CONFIG_ROOT, "user_settings.sqlite")

def ensure_users_db() -> None:
    Path(CONFIG_ROOT).mkdir(parents=True, exist_ok=True)
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
        conn.commit()
    finally:
        conn.close()


def ensure_user_settings_db() -> None:
    Path(CONFIG_ROOT).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS UserSettings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                language TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                local_output_dir TEXT DEFAULT NULL,
                theme TEXT NOT NULL DEFAULT 'light',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(UserSettings)")}
        if "theme" not in columns:
            conn.execute("ALTER TABLE UserSettings ADD COLUMN theme TEXT NOT NULL DEFAULT 'light'")
        conn.commit()
    finally:
        conn.close()


def get_user_role(username: str) -> str:
    ensure_users_db()
    conn = sqlite3.connect(make_long_path(USERS_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT role, is_active FROM Users WHERE username = ?", (username,)
        ).fetchone()
        if row and row["is_active"]:
            return str(row["role"])
    finally:
        conn.close()
    return "viewer"


def get_user_settings(username: str) -> Dict[str, str]:
    ensure_user_settings_db()
    conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT username, language, theme FROM UserSettings WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            return {
                "username": row["username"],
                "language": row["language"],
                "theme": row["theme"],
            }
        conn.execute(
            "INSERT INTO UserSettings (username, language, email, theme, created_at, updated_at) VALUES (?, 'en-US', '', 'light', datetime('now'), datetime('now'))",
            (username,),
        )
        conn.commit()
        return {"username": username, "language": "en-US", "theme": "light"}
    finally:
        conn.close()


def update_user_settings(username: str, *, language: Optional[str] = None, theme: Optional[str] = None) -> None:
    ensure_user_settings_db()
    updates = {}
    if language:
        updates["language"] = language
    if theme:
        updates["theme"] = theme
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values())
    values.append(username)
    conn = sqlite3.connect(make_long_path(USER_SETTINGS_DB_PATH))
    try:
        conn.execute(
            f"UPDATE UserSettings SET {assignments}, updated_at = datetime('now') WHERE username = ?",
            tuple(values),
        )
        if conn.total_changes == 0:
            conn.execute(
                "INSERT INTO UserSettings (username, language, email, theme, created_at, updated_at) VALUES (?, ?, '', ?, datetime('now'), datetime('now'))",
                (username, updates.get("language", "en-US"), updates.get("theme", "light")),
            )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Theme application
# ----------------------------------------------------------------------------
LIGHT_STYLE = ""
DARK_STYLE = """
QWidget { background-color: #1f1f1f; color: #e6e6e6; }
QLineEdit, QComboBox, QPushButton { background-color: #2b2b2b; color: #e6e6e6; border: 1px solid #3a3a3a; }
QPushButton:hover { background-color: #3a3a3a; }
"""


def apply_theme(app: QApplication, theme: str) -> None:
    if theme == "dark":
        app.setStyleSheet(DARK_STYLE)
    else:
        app.setStyleSheet(LIGHT_STYLE)


# ----------------------------------------------------------------------------
# Settings dialog
# ----------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, translator: Translator, language: str, theme: str, parent: QWidget | None = None, *, dev_visible: bool, server_override: Optional[bool], role_override: Optional[str]):
        super().__init__(parent)
        self.translator = translator
        self.language = language
        self.theme = theme
        self.server_override = server_override
        self.role_override = role_override
        self.dev_visible = dev_visible
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle(self.translator.tr("settings_title"))
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English (en-US)", "en-US")
        self.language_combo.addItem("Português (pt-BR)", "pt-BR")
        idx = self.language_combo.findData(self.language)
        self.language_combo.setCurrentIndex(max(idx, 0))
        form.addRow(self.translator.tr("language"), self.language_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(self.translator.tr("theme_light"), "light")
        self.theme_combo.addItem(self.translator.tr("theme_dark"), "dark")
        idx = self.theme_combo.findData(self.theme)
        self.theme_combo.setCurrentIndex(max(idx, 0))
        form.addRow(self.translator.tr("theme"), self.theme_combo)

        layout.addLayout(form)

        if self.dev_visible:
            dev_group = QGroupBox(self.translator.tr("dev_options"))
            dev_layout = QFormLayout(dev_group)

            self.server_combo = QComboBox()
            self.server_combo.addItem(self.translator.tr("server_auto"), None)
            self.server_combo.addItem(self.translator.tr("server_force_on"), True)
            self.server_combo.addItem(self.translator.tr("server_force_off"), False)
            idx = self.server_combo.findData(self.server_override)
            self.server_combo.setCurrentIndex(max(idx, 0))
            dev_layout.addRow(self.translator.tr("server_override"), self.server_combo)

            self.role_combo = QComboBox()
            self.role_combo.addItem(self.translator.tr("role_none"), None)
            self.role_combo.addItem(self.translator.tr("role_viewer"), "viewer")
            self.role_combo.addItem(self.translator.tr("role_user"), "user")
            self.role_combo.addItem(self.translator.tr("role_admin"), "admin")
            idx = self.role_combo.findData(self.role_override)
            self.role_combo.setCurrentIndex(max(idx, 0))
            dev_layout.addRow(self.translator.tr("role_override"), self.role_combo)

            layout.addWidget(dev_group)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton(self.translator.tr("save"))
        self.cancel_btn = QPushButton(self.translator.tr("cancel"))
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_values(self) -> tuple[str, str, Optional[bool], Optional[str]]:
        language = self.language_combo.currentData()
        theme = self.theme_combo.currentData()
        server_override = self.server_combo.currentData() if self.dev_visible else None
        role_override = self.role_combo.currentData() if self.dev_visible else None
        return str(language), str(theme), server_override, role_override


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, app: QApplication, translator: Translator, settings: Dict[str, str]):
        super().__init__()
        self.app = app
        self.translator = translator
        self.language = settings.get("language", "en-US")
        self.theme = settings.get("theme", "light")
        self.server_override: Optional[bool] = None
        self.role_override: Optional[str] = None
        self.old_path: Optional[Path] = None
        self.new_path: Optional[Path] = None
        self.output_dir = get_output_directory_for_user(CURRENT_USER)

        apply_theme(self.app, self.theme)
        self._build_ui()
        self.refresh_texts()

    # Role logic -------------------------------------------------------------
    def effective_role(self) -> str:
        if self.role_override:
            return self.role_override
        username = get_current_username()
        if is_super_admin(username):
            return "admin"
        return get_user_role(username)

    # UI builders ------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        grid = QGridLayout()
        self.old_label = QLabel()
        self.old_line = QLineEdit()
        self.old_line.setReadOnly(True)
        self.old_btn = QPushButton()
        self.old_btn.clicked.connect(self.select_old)
        grid.addWidget(self.old_label, 0, 0)
        grid.addWidget(self.old_line, 0, 1)
        grid.addWidget(self.old_btn, 0, 2)

        self.new_label = QLabel()
        self.new_line = QLineEdit()
        self.new_line.setReadOnly(True)
        self.new_btn = QPushButton()
        self.new_btn.clicked.connect(self.select_new)
        grid.addWidget(self.new_label, 1, 0)
        grid.addWidget(self.new_line, 1, 1)
        grid.addWidget(self.new_btn, 1, 2)

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton()
        self.run_btn.clicked.connect(self.run_comparison)
        self.settings_btn = QPushButton()
        self.settings_btn.clicked.connect(self.open_settings)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.settings_btn)
        layout.addLayout(btn_row)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.setCentralWidget(central)

    # Text refresh -----------------------------------------------------------
    def refresh_texts(self) -> None:
        self.setWindowTitle(self.translator.tr("title"))
        self.old_label.setText(self.translator.tr("old_file"))
        self.new_label.setText(self.translator.tr("new_file"))
        self.old_btn.setText(self.translator.tr("browse"))
        self.new_btn.setText(self.translator.tr("browse"))
        self.run_btn.setText(self.translator.tr("run"))
        self.settings_btn.setText(self.translator.tr("settings"))
        if csenv.OFFLINE_MODE and not DEV_MODE:
            self.status.showMessage(self.translator.tr("status_offline"))
        else:
            self.status.showMessage(self.translator.tr("status_ready"))

    # File selection ---------------------------------------------------------
    def select_old(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.translator.tr("open_old"), str(Path.home()), "PDF (*.pdf)")
        if path:
            self.old_path = Path(path)
            self.old_line.setText(path)

    def select_new(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.translator.tr("open_new"), str(Path.home()), "PDF (*.pdf)")
        if path:
            self.new_path = Path(path)
            self.new_line.setText(path)

    # Comparison -------------------------------------------------------------
    def run_comparison(self) -> None:
        if not self.old_path or not self.new_path:
            QMessageBox.warning(self, self.translator.tr("title"), self.translator.tr("error_no_files"))
            return
        try:
            result: ComparisonResult = run_comparison(
                str(self.old_path), str(self.new_path), output_dir=str(self.output_dir)
            )
            logger.info("Comparison finished: %s", result)
            QMessageBox.information(self, self.translator.tr("title"), self.translator.tr("comparison_complete"))
        except Exception as exc:  # pragma: no cover - surfaced in UI
            logger.exception("Comparison failed")
            QMessageBox.critical(
                self,
                self.translator.tr("title"),
                self.translator.tr("comparison_failed").format(error=exc),
            )

    # Settings dialog -------------------------------------------------------
    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.translator,
            self.language,
            self.theme,
            self,
            dev_visible=DEV_MODE,
            server_override=self.server_override,
            role_override=self.role_override,
        )
        if dialog.exec() == QDialog.Accepted:
            language, theme, server_override, role_override = dialog.get_values()
            self.language = language
            self.theme = theme
            self.server_override = server_override
            self.role_override = role_override
            self.translator.set_language(language)
            update_user_settings(CURRENT_USER, language=language, theme=theme)
            set_dev_server_override(server_override)
            set_connection_state(is_server_available(csenv.SERVER_ROOT))
            apply_theme(self.app, theme)
            self.refresh_texts()


# ----------------------------------------------------------------------------
# Startup helpers
# ----------------------------------------------------------------------------
def require_server_or_exit(app: QApplication, translator: Translator) -> None:
    if not DEV_MODE and csenv.OFFLINE_MODE:
        QMessageBox.critical(None, translator.tr("title"), translator.tr("offline_block"))
        sys.exit(1)


def main() -> None:
    csenv.ensure_directories()
    app = QApplication(sys.argv)
    username = get_current_username()
    settings = get_user_settings(username)
    translator = Translator(settings.get("language", "en-US"))
    apply_theme(app, settings.get("theme", "light"))

    require_server_or_exit(app, translator)

    window = MainWindow(app, translator, settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
