"""Legacy single-file interface (deprecated).

This module contains the original Qt implementation bundled with logic and
translations.  The project now provides a modular interface under
``src/compareset/ui`` which should be used instead.  This file is kept only for
reference and will be removed in a future release.
"""

import os
import time
import getpass

from dotenv import load_dotenv

from user_check import (
    load_users,
    save_users,
    load_user_records,
    save_user_records,
    is_admin,
    load_admins,
)

from version_check import (
    CURRENT_VERSION,
    check_for_update,
    fetch_latest_version,
    LATEST_VERSION_FILE,
)

from PySide6 import QtCore, QtGui, QtWidgets

from pdf_diff import comparar_pdfs, CancelledError
from pdf_highlighter import gerar_pdf_com_destaques

load_dotenv()

# application version string
VERSION = CURRENT_VERSION
# File name containing the latest version information
VERSION_FILE = os.getenv("LATEST_VERSION_FILE", LATEST_VERSION_FILE)
# download page for the application
DOWNLOAD_URL = (
    "https://digicorner.sharepoint.com/sites/ddt/DDTFUE/Softwares/CompareSet/"
)

# make version easily available to other modules
__all__ = ["VERSION", "CompareSetQt"]


def file_in_use(path: str) -> bool:
    try:
        with open(path, "rb+"):
            return False
    except Exception:
        return True


class ComparisonThread(QtCore.QThread):
    progress = QtCore.Signal(float)
    finished = QtCore.Signal(str, str)

    def __init__(
        self,
        old_pdf: str,
        new_pdf: str,
        output_pdf: str,
        ignore_geometry: bool,
        ignore_text: bool,
    ):
        super().__init__()
        self.old_pdf = old_pdf
        self.new_pdf = new_pdf
        self.output_pdf = output_pdf
        self.ignore_geometry = ignore_geometry
        self.ignore_text = ignore_text
        self._cancelled = False
        self.elements_checked = 0
        self.diff_count = 0

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self):
        try:
            dados = comparar_pdfs(
                self.old_pdf,
                self.new_pdf,
                adaptive=True,
                ignore_geometry=self.ignore_geometry,
                ignore_text=self.ignore_text,
                progress_callback=lambda p: self.progress.emit(p / 2),
                cancel_callback=self.is_cancelled,
            )
            self.elements_checked = dados.get("verificados", 0)
            self.diff_count = len(dados.get("removidos", [])) + len(
                dados.get("adicionados", [])
            )
            if self.is_cancelled():
                self.finished.emit("cancelled", "")
                return
            if not dados["removidos"] and not dados["adicionados"]:
                self.progress.emit(100.0)
                self.finished.emit("no_diffs", "")
                return
            gerar_pdf_com_destaques(
                self.old_pdf,
                self.new_pdf,
                dados["removidos"],
                dados["adicionados"],
                self.output_pdf,
                progress_callback=lambda p: self.progress.emit(50 + p / 2),
                cancel_callback=self.is_cancelled,
            )
            if self.is_cancelled():
                self.finished.emit("cancelled", "")
            else:
                self.finished.emit("success", self.output_pdf)
        except CancelledError:
            self.finished.emit("cancelled", "")
        except Exception as e:
            self.finished.emit("error", str(e))


class VersionCheckThread(QtCore.QThread):
    """Thread that checks for a newer application version."""

    finished = QtCore.Signal(str)

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename

    def run(self):
        latest = fetch_latest_version(self.filename)
        self.finished.emit(latest)


class CompareSetQt(QtWidgets.QWidget):
    def __init__(self, is_admin: bool = False):
        super().__init__()
        self.is_admin = is_admin
        self.setWindowTitle("CompareSet")
        # start with a smaller window for low resolutions
        self.small_size = QtCore.QSize(500, 360)
        self.large_size = QtCore.QSize(700, 500)
        self.setFixedSize(self.small_size)
        # application icons were moved to assets/icons in the project root
        icons_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        icon_path = os.path.join(icons_dir, "Icon - CompareSet.ico")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.lang = "pt"
        self.translations = {
            "en": {
                "select_old": "Select old revision",
                "select_new": "Select new revision",
                "compare": "Compare Revisions",
                "license": "License",
                "improve_label": "Ideas",
                "help_label": "Help",
                "settings_label": "Settings",
                "no_file": "no file selected",
                "view_result": "View result",
                "select_old_dialog": "Select old PDF",
                "select_new_dialog": "Select new PDF",
                "save_dialog": "Save comparison PDF",
                "error": "Error",
                "success": "Success",
                "select_both": "Select both PDFs for comparison.",
                "choose_diff": "Choose a different file name from the input PDF.",
                "file_in_use": "The PDF is open in another program.",
                "starting": "Starting...",
                "waiting": "Please wait",
                "cancelling": "Cancelling...",
                "pdf_saved": "PDF saved to: {}",
                "open_pdf_title": "Open PDF",
                "open_pdf_prompt": "Open generated PDF?",
                "license_missing": "License file not found.",
                "license_title": "License",
                "improvement_tooltip": "Send improvement suggestion",
                "help_tooltip": "Access help",
                "language": "Language:",
                "settings_tooltip": "Open settings",
                "settings_title": "Settings",
                "no_diffs_title": "No differences",
                "no_diffs_msg": "The PDF comparison found no differences.",
                "cancel": "Cancel",
                "cancelled_title": "Cancelled",
                "cancelled_msg": "Comparison cancelled.",
                "stats": "Elements checked: {}\nDifferences found: {}",
                "history": "History",
                "file_missing": "File not found at saved location",
                "file_replaced": "File replaced",
                "unavailable": "Unavailable",
                "back": "Back",
                "update_title": "Update available",
                "update_msg": "A new version ({}) is available.",
                "update_download": "New version available for download",
                "update_available": "New version available",
                "view_details": "View details",
                "details_title": "Details",
                "date": "Date:",
                "output_file": "Output file:",
                "comparison_success": "Comparison completed successfully!",
                "file_missing_hint": "File not found. Please regenerate.",
                "sort_recent": "Most recent",
                "sort_alpha": "Alphabetical",
                "manage_users": "Manage users",
                "add_user": "Add user",
                "remove_user": "Remove user",
                "restore_user": "Restore user",
                "user_save_failed": "Failed to update user list",
                "admin": "Administration",
                "search_users": "Search users",
                "username": "Username",
                "real_name": "Name",
                "email": "Email",
                "status": "Status",
                "active": "Active",
                "removed": "Removed",
                "admin_role": "Admin",
                "added_on": "Added on:",
                "swap": "Swap",
                "swap_tooltip": "Swap selected PDFs",
                "elements_label": "Select elements to compare:",
                "text_option": "Text",
                "text_tip": "Compares changes in words, numbers, and annotations.",
                "geom_option": "Geometric elements",
                "geom_tip": "Compares changes in visual elements such as lines, shapes, charts, and vectors.",
                "silent_option": "Silent mode",
                "coming_soon": "Coming soon",
            },
            "pt": {
                "select_old": "Selecionar revis\u00e3o antiga",
                "select_new": "Selecionar nova revis\u00e3o",
                "compare": "Comparar Revis\u00f5es",
                "license": "Licen\u00e7a",
                "improve_label": "Ideias",
                "help_label": "Ajuda",
                "settings_label": "Configura\u00e7\u00f5es",
                "no_file": "nenhum arquivo selecionado",
                "view_result": "Visualizar resultado",
                "select_old_dialog": "Selecione o PDF antigo",
                "select_new_dialog": "Selecione o PDF novo",
                "save_dialog": "Salvar PDF de compara\u00e7\u00e3o",
                "error": "Erro",
                "success": "Sucesso",
                "select_both": "Selecione ambos os PDFs para compara\u00e7\u00e3o.",
                "choose_diff": "Escolha um nome de arquivo diferente do PDF de entrada.",
                "file_in_use": "O PDF est\u00e1 aberto em outro programa.",
                "starting": "Iniciando...",
                "waiting": "Aguarde",
                "cancelling": "Cancelando...",
                "pdf_saved": "PDF salvo em: {}",
                "open_pdf_title": "Abrir PDF",
                "open_pdf_prompt": "Abrir o PDF gerado?",
                "license_missing": "Arquivo de licen\u00e7a n\u00e3o encontrado.",
                "license_title": "Licen\u00e7a",
                "improvement_tooltip": "Enviar sugest\u00e3o ou melhoria",
                "help_tooltip": "Acessar ajuda",
                "language": "Idioma:",
                "settings_tooltip": "Abrir configura\u00e7\u00f5es",
                "settings_title": "Configura\u00e7\u00f5es",
                "no_diffs_title": "Sem diferen\u00e7as",
                "no_diffs_msg": "A compara\u00e7\u00e3o de PDFs n\u00e3o resultou em nenhuma diferen\u00e7a.",
                "cancel": "Cancelar",
                "cancelled_title": "Cancelado",
                "cancelled_msg": "Compara\u00e7\u00e3o cancelada.",
                "stats": "Elementos verificados: {}\nDiferen\u00e7as encontradas: {}",
                "history": "Hist\u00f3rico",
                "file_missing": "Arquivo n\u00e3o encontrado no local de origem",
                "file_replaced": "Arquivo substitu\u00eddo",
                "unavailable": "Indispon\u00edvel",
                "back": "Voltar",
                "update_title": "Atualiza\u00e7\u00e3o dispon\u00edvel",
                "update_msg": "Uma nova vers\u00e3o ({}) est\u00e1 dispon\u00edvel.",
                "update_download": "Nova vers\u00e3o dispon\u00edvel para download",
                "update_available": "Nova vers\u00e3o dispon\u00edvel",
                "view_details": "Ver detalhes",
                "details_title": "Detalhes",
                "date": "Data:",
                "output_file": "Arquivo:",
                "comparison_success": "Comparação realizada com sucesso!",
                "file_missing_hint": "Arquivo não encontrado. Gere novamente.",
                "sort_recent": "Mais recente",
                "sort_alpha": "Ordem alfabética",
                "manage_users": "Gerenciar usuários",
                "add_user": "Adicionar usuário",
                "remove_user": "Remover usuário",
                "restore_user": "Restaurar usuário",
                "user_save_failed": "Erro ao atualizar lista de usuários",
                "admin": "Administração",
                "search_users": "Pesquisar usuários",
                "username": "Usuário",
                "real_name": "Nome",
                "email": "Email",
                "status": "Status",
                "active": "Ativo",
                "removed": "Removido",
                "admin_role": "Administrador",
                "added_on": "Cadastrado em:",
                "swap": "Inverter seleção",
                "swap_tooltip": "Inverter arquivos selecionados",
                "elements_label": "Selecionar elementos para comparar:",
                "text_option": "Texto",
                "text_tip": "Compara alterações em palavras, números e anotações.",
                "geom_option": "Elementos geométricos",
                "geom_tip": "Compara alterações em elementos visuais como linhas, formas, gráficos e vetores.",
                "silent_option": "Modo silencioso",
                "coming_soon": "Em breve",
            },
        }
        self.old_path = ""
        self.new_path = ""
        self.thread: ComparisonThread | None = None
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_remaining_time)
        self.start_time: float | None = None
        self.estimated_total: float | None = None
        self.cancelling = False
        self.last_stats: tuple[int, int] | None = None
        self.history: list[dict] = []
        self.blink_timer = QtCore.QTimer(self)
        self.blink_timer.timeout.connect(self._blink_version)
        self._blink_state = False
        self._setup_ui()
        if self.is_admin:
            self.action_admin.setVisible(True)
            self.admin_sep.setVisible(True)
        QtCore.QTimer.singleShot(0, self._start_update_check)
        self._update_compare_button()

    def tr(self, key: str) -> str:
        return self.translations[self.lang].get(key, key)

    def _format_datetime(self, ts: float) -> str:
        fmt = "%m-%d-%Y - %H:%M" if self.lang == "en" else "%d-%m-%Y - %H:%M"
        return time.strftime(fmt, time.localtime(ts))

    def _set_fixed_size_centered(self, size: QtCore.QSize):
        """Resize the window keeping its center position."""
        center = self.frameGeometry().center()
        self.setFixedSize(size)
        geo = self.frameGeometry()
        geo.moveCenter(center)
        self.move(geo.topLeft())

    def set_language(self, lang: str):
        if lang in self.translations:
            self.lang = lang
        t = self.translations[self.lang]
        self.edit_old.setPlaceholderText(t["no_file"])
        self.btn_old.setText(t["select_old"])
        self.edit_new.setPlaceholderText(t["no_file"])
        self.btn_new.setText(t["select_new"])
        self.btn_compare.setText(t["compare"])
        self.action_improve.setToolTip(t["improvement_tooltip"])
        self.action_help.setToolTip(t["coming_soon"])
        self.action_help.setEnabled(False)
        self.action_settings.setToolTip(t["settings_tooltip"])
        self.action_history.setToolTip("")
        self.action_admin.setToolTip("")
        self.action_improve.setText(t["improve_label"])
        self.action_help.setText(t["help_label"])
        self.action_settings.setText(t["settings_label"])
        self.action_history.setText(t["history"])
        self.action_admin.setText(t["admin"])
        if hasattr(self, "btn_swap"):
            self.btn_swap.setText(t["swap"])
            self.btn_swap.setToolTip(t["swap_tooltip"])
        if hasattr(self, "filter_admin_chk"):
            self.filter_admin_chk.setText(t["admin_role"])
        if hasattr(self, "elements_label"):
            self.elements_label.setText(t["elements_label"])
            self.text_chk.setText(t["text_option"])
            self.text_chk.setToolTip(t["text_tip"])
            self.geom_chk.setText(t["geom_option"])
            self.geom_chk.setToolTip(t["geom_tip"])
            self.silent_chk.setText(t["silent_option"])
        if hasattr(self, "btn_cancel"):
            self.btn_cancel.setText(t["cancel"])
        if hasattr(self, "btn_view"):
            self.btn_view.setText(t["view_result"])
        self.lbl_version.setText(f"v{VERSION}")
        if hasattr(self, "label_status") and self.last_stats:
            self.label_status.setText(t["stats"].format(*self.last_stats))

    def _setup_ui(self):
        self.stack = QtWidgets.QStackedLayout(self)

        self.main_page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.main_page)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)
        # add breathing room between the toolbar and the file selectors
        layout.addSpacing(15)

        top.addStretch()

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        icons_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")

        improve_icon = QtGui.QIcon(os.path.join(icons_dir, "Icon - Improvement.png"))
        help_icon = QtGui.QIcon(
            os.path.join(icons_dir, "Icon - Question Mark Help.png")
        )
        settings_icon = QtGui.QIcon(os.path.join(icons_dir, "Icon - Gear.png"))

        history_icon = QtGui.QIcon(os.path.join(icons_dir, "Icon - History.png"))
        self.action_history = self.toolbar.addAction(history_icon, "")
        self.action_history.setToolTip("")
        self.action_history.triggered.connect(self.open_history)
        self.action_history.setVisible(False)

        admin_path = os.path.join(icons_dir, "Icon - Administration.png")
        if not os.path.exists(admin_path):
            admin_path = os.path.join(icons_dir, "Icon - Gear.png")
        admin_icon = QtGui.QIcon(admin_path)
        self.action_admin = self.toolbar.addAction(admin_icon, "")
        self.action_admin.setToolTip("")
        self.action_admin.triggered.connect(self.open_admin_page)
        self.action_admin.setVisible(False)

        self.admin_sep = self.toolbar.addSeparator()
        self.admin_sep.setVisible(False)

        self.history_sep = self.toolbar.addSeparator()
        self.history_sep.setVisible(False)

        self.action_improve = self.toolbar.addAction(improve_icon, "")
        self.action_improve.setToolTip("")
        self.action_improve.triggered.connect(self.open_improvement_link)

        self.toolbar.addSeparator()

        self.action_help = self.toolbar.addAction(help_icon, "")
        self.action_help.setToolTip("")
        self.action_help.setEnabled(False)
        self.action_help.triggered.connect(self.open_help)

        self.toolbar.addSeparator()

        self.action_settings = self.toolbar.addAction(settings_icon, "")
        self.action_settings.setToolTip("")
        self.action_settings.triggered.connect(self.open_settings)

        # subtle hover effect for toolbar buttons
        self.toolbar.setStyleSheet(
            "QToolBar{spacing:0px;}"
            "QToolBar::separator{width:1px;margin:0px;}"
            "QToolButton{background:transparent;border-radius:2px;padding:0px;margin:0px;}"
            "QToolButton:hover{background:#d0d0d0;}"
        )

        top.addWidget(self.toolbar)

        grid = QtWidgets.QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setAlignment(QtCore.Qt.AlignCenter)
        layout.addLayout(grid)

        self.edit_old = QtWidgets.QLineEdit()
        self.edit_old.setReadOnly(True)
        self.edit_old.setFocusPolicy(QtCore.Qt.NoFocus)
        # QLineEdit does not implement setTextInteractionFlags; disable
        # editing via the read-only and focus settings instead
        self.edit_old.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.edit_old.setMinimumWidth(200)
        self.edit_old.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.edit_old.setAlignment(QtCore.Qt.AlignCenter)
        self.edit_old.setStyleSheet(
            "QLineEdit{background:#eeeeee;border:1px solid #cccccc;}"
            "QLineEdit:hover{background:#dddddd;}"
        )
        self.btn_old = QtWidgets.QPushButton()
        self.btn_old.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#333333;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        self.btn_height = int(self.edit_old.sizeHint().height() * 1.2)
        self.edit_old.setFixedHeight(self.btn_height)
        self.btn_font = self.edit_old.font()
        self.edit_old.setFont(self.btn_font)
        self.btn_old.setFixedHeight(self.btn_height)
        self.btn_old.setFont(self.btn_font)
        self.btn_old.setEnabled(True)
        self.btn_old.clicked.connect(self.select_old)
        grid.addWidget(self.edit_old, 0, 0)
        grid.addWidget(self.btn_old, 0, 1, alignment=QtCore.Qt.AlignVCenter)

        self.edit_new = QtWidgets.QLineEdit()
        self.edit_new.setReadOnly(True)
        self.edit_new.setFocusPolicy(QtCore.Qt.NoFocus)
        # setTextInteractionFlags is not available on QLineEdit
        self.edit_new.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.edit_new.setMinimumWidth(200)
        self.edit_new.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.edit_new.setAlignment(QtCore.Qt.AlignCenter)
        self.edit_new.setStyleSheet(
            "QLineEdit{background:#eeeeee;border:1px solid #cccccc;}"
            "QLineEdit:hover{background:#dddddd;}"
        )
        self.edit_new.setFont(self.btn_font)
        self.edit_new.setFixedHeight(self.btn_height)
        self.btn_new = QtWidgets.QPushButton()
        self.btn_new.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#333333;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        self.btn_new.setFixedHeight(self.btn_height)
        self.btn_new.setFont(self.btn_font)
        self.btn_new.setEnabled(True)
        self.btn_new.clicked.connect(self.select_new)
        grid.addWidget(self.edit_new, 1, 0)
        grid.addWidget(self.btn_new, 1, 1, alignment=QtCore.Qt.AlignVCenter)

        self.btn_swap = QtWidgets.QPushButton()
        self.btn_swap.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#333333;}"
        )
        self.btn_swap.setFixedHeight(self.btn_height)
        self.btn_swap.setFont(self.btn_font)
        self.btn_swap.clicked.connect(self.swap_selection)
        grid.addWidget(self.btn_swap, 2, 0, 1, 2, alignment=QtCore.Qt.AlignCenter)

        self.elements_label = QtWidgets.QLabel()
        layout.addWidget(self.elements_label)
        elements_row = QtWidgets.QHBoxLayout()
        elements_row.setSpacing(10)
        elements_row.setAlignment(QtCore.Qt.AlignCenter)
        self.text_chk = QtWidgets.QCheckBox()
        self.text_chk.setChecked(True)
        self.geom_chk = QtWidgets.QCheckBox()
        self.geom_chk.setChecked(True)
        self.text_chk.stateChanged.connect(self._enforce_element_selection)
        self.geom_chk.stateChanged.connect(self._enforce_element_selection)
        elements_row.addWidget(self.text_chk)
        elements_row.addWidget(self.geom_chk)
        self.silent_chk = QtWidgets.QCheckBox()
        elements_row.addWidget(self.silent_chk)
        layout.addLayout(elements_row)

        self.btn_compare = QtWidgets.QPushButton()
        self.btn_compare.setStyleSheet(
            "QPushButton{background-color:#471F6F;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#5c2c88;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        self.btn_compare.setFixedHeight(self.btn_height)
        self.btn_compare.setFont(self.btn_font)
        self._update_compare_button()
        self.btn_compare.clicked.connect(self.start_compare)
        layout.addWidget(self.btn_compare)

        layout.addSpacing(15)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setOrientation(QtCore.Qt.Horizontal)
        self.progress.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        progress_height = max(8, int(self.progress.sizeHint().height() * 1.0))
        self.progress.setFixedHeight(progress_height)

        self._progress_placeholder = QtWidgets.QWidget()
        self._progress_placeholder.setFixedHeight(progress_height)
        self._progress_stack = QtWidgets.QStackedLayout()
        self._progress_stack.addWidget(self.progress)
        self._progress_stack.addWidget(self._progress_placeholder)
        self._progress_stack.setCurrentIndex(1)

        self.progress_frame = QtWidgets.QFrame()
        # remove the white background so the frame blends with the window
        self.progress_frame.setStyleSheet("")
        progress_group = QtWidgets.QVBoxLayout(self.progress_frame)
        progress_group.addLayout(self._progress_stack)

        status_row = QtWidgets.QHBoxLayout()
        status_row.setAlignment(QtCore.Qt.AlignCenter)
        status_row.setSpacing(8)
        self.spinner = QtWidgets.QLabel()
        self.spinner_base = self._create_spinner_pixmap()
        self.spinner.setPixmap(self.spinner_base)
        self.spinner.setFixedSize(self.spinner_base.size())
        self.spinner.setScaledContents(True)
        self.spinner.hide()
        status_row.addWidget(self.spinner)
        self.spinner_timer = QtCore.QTimer(self)
        self.spinner_timer.timeout.connect(self._rotate_spinner)
        self.spinner_angle = 0
        self.label_status = QtWidgets.QLabel()
        self.label_status.setAlignment(QtCore.Qt.AlignCenter)
        status_row.addWidget(self.label_status)
        progress_group.addLayout(status_row)
        self.btn_cancel = QtWidgets.QPushButton(self.tr("cancel"))
        self.btn_cancel.setStyleSheet(
            "QPushButton{background-color:#c0392b;color:white;font-weight:bold;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#e74c3c;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        self.btn_cancel.setFixedWidth(80)
        self.btn_cancel.setFixedHeight(self.btn_height)
        self.btn_cancel.setFont(self.btn_font)
        self.btn_cancel.clicked.connect(self.cancel_compare)
        self.btn_cancel.hide()
        progress_group.addWidget(self.btn_cancel, alignment=QtCore.Qt.AlignCenter)
        # more spacing so the status information and buttons don't feel cramped
        progress_group.setSpacing(8)

        self.btn_view = QtWidgets.QPushButton(self.tr("view_result"))
        self.btn_view.setStyleSheet(
            "QPushButton{background-color:#471F6F;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#5c2c88;}"
        )
        self.btn_view.setFixedHeight(self.btn_height)
        self.btn_view.setFont(self.btn_font)
        self.btn_view.clicked.connect(self.open_result)
        self.btn_view.hide()
        progress_group.addWidget(self.btn_view, alignment=QtCore.Qt.AlignCenter)

        layout.addWidget(self.progress_frame)
        layout.addStretch()

        self.lbl_version = QtWidgets.QLabel()
        self.lbl_version.setAlignment(QtCore.Qt.AlignRight)
        self.lbl_version.setStyleSheet("color:#666666")
        self.lbl_version.setFont(self.btn_font)

        # label that indicates an update is available
        self.lbl_update = QtWidgets.QLabel()
        self.lbl_update.setAlignment(QtCore.Qt.AlignLeft)
        self.lbl_update.setStyleSheet("color:red")
        self.lbl_update.setFont(self.btn_font)
        self.lbl_update.hide()

        bottom = QtWidgets.QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)
        self.license_link = QtWidgets.QLabel(f'<a href="#">{self.tr("license")}</a>')
        self.license_link.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.license_link.linkActivated.connect(lambda _: self.show_license())
        bottom.addWidget(self.license_link)
        bottom.addStretch()
        bottom.addWidget(self.lbl_update)
        bottom.addWidget(self.lbl_version)
        layout.addLayout(bottom)

        self.stack.addWidget(self.main_page)
        self.history_page = QtWidgets.QWidget()
        self.history_layout = QtWidgets.QVBoxLayout(self.history_page)
        self.history_layout.setContentsMargins(10, 10, 10, 10)
        self.stack.addWidget(self.history_page)
        self.admin_page = QtWidgets.QWidget()
        self.admin_layout = QtWidgets.QVBoxLayout(self.admin_page)
        self.admin_layout.setContentsMargins(10, 10, 10, 10)
        self.stack.addWidget(self.admin_page)
        self.stack.setCurrentWidget(self.main_page)

        self.set_language(self.lang)
        # ensure no line edit starts focused so placeholders remain visible
        self.btn_compare.setFocus()

    def clear_results(self):
        if hasattr(self, "label_status"):
            self.label_status.setText("")
        if hasattr(self, "btn_view"):
            self.btn_view.hide()
        self.last_stats = None
        if hasattr(self, "btn_compare"):
            self._update_compare_button()

    def _clear_layout(self, layout: QtWidgets.QLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _create_spinner_pixmap(self) -> QtGui.QPixmap:
        size = 20
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("#999999"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        rect = QtCore.QRectF(2, 2, size - 4, size - 4)
        # draw a partial circle with a gap to mimic the Windows spinner
        painter.drawArc(rect, 60 * 16, 300 * 16)
        painter.end()
        return pm

    def _update_compare_button(self):
        filled = bool(self.old_path and self.new_path)
        if filled:
            style = (
                "QPushButton{background-color:#471F6F;color:white;padding:4px;border-radius:4px;}"
                "QPushButton:hover{background-color:#5c2c88;}"
                "QPushButton:disabled{background-color:#555555;color:white;}"
            )
        else:
            style = (
                "QPushButton{background-color:#555555;color:white;padding:4px;border-radius:4px;}"
                "QPushButton:disabled{background-color:#555555;color:white;}"
            )
        self.btn_compare.setStyleSheet(style)
        self.btn_compare.setEnabled(filled)

    def _enforce_element_selection(self):
        if not self.text_chk.isChecked() and not self.geom_chk.isChecked():
            sender = self.sender()
            if isinstance(sender, QtWidgets.QCheckBox):
                sender.setChecked(True)

    # slots
    def select_old(self):
        self.clear_results()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("select_old_dialog"), filter="PDF Files (*.pdf)"
        )
        if path:
            self.old_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self.edit_old.setText(name)
        self._update_compare_button()

    def select_new(self):
        self.clear_results()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("select_new_dialog"), filter="PDF Files (*.pdf)"
        )
        if path:
            self.new_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self.edit_new.setText(name)
        self._update_compare_button()

    def swap_selection(self):
        self.old_path, self.new_path = self.new_path, self.old_path
        old_name = (
            os.path.splitext(os.path.basename(self.old_path))[0]
            if self.old_path
            else ""
        )
        new_name = (
            os.path.splitext(os.path.basename(self.new_path))[0]
            if self.new_path
            else ""
        )
        self.edit_old.setText(old_name)
        self.edit_new.setText(new_name)
        self._update_compare_button()

    def start_compare(self):
        old = self.old_path
        new = self.new_path
        if not old or not new:
            QtWidgets.QMessageBox.critical(
                self, self.tr("error"), self.tr("select_both")
            )
            return

        if os.path.abspath(old) == os.path.abspath(new):
            QtWidgets.QMessageBox.information(
                self, self.tr("no_diffs_title"), self.tr("no_diffs_msg")
            )
            return

        out, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self.tr("save_dialog"), filter="PDF Files (*.pdf)"
        )
        if not out:
            return

        if out in (old, new):
            QtWidgets.QMessageBox.critical(
                self, self.tr("error"), self.tr("choose_diff")
            )
            return

        if os.path.exists(out) and file_in_use(out):
            QtWidgets.QMessageBox.warning(
                self, self.tr("error"), self.tr("file_in_use")
            )
            return

        self.progress.setValue(0)
        self._progress_stack.setCurrentIndex(1)
        self.edit_old.clearFocus()
        self.edit_new.clearFocus()
        self.label_status.setText(f"{self.tr('waiting')} --:--")
        self.spinner_angle = 0
        self.spinner.show()
        self.spinner_timer.start(80)
        self.start_time = time.perf_counter()
        self.estimated_total = None
        self.cancelling = False
        self.timer.start(1000)
        self.btn_view.hide()
        self.btn_cancel.show()
        self.btn_cancel.setEnabled(True)
        self.btn_compare.setEnabled(False)
        self.btn_old.setEnabled(False)
        self.btn_new.setEnabled(False)
        self.edit_old.setEnabled(False)
        self.edit_new.setEnabled(False)
        self.action_improve.setEnabled(False)
        self.action_help.setEnabled(False)
        self.action_settings.setEnabled(False)
        self.action_history.setEnabled(False)
        self.action_admin.setEnabled(False)
        self.history_sep.setVisible(True)

        ignore_geometry = not self.geom_chk.isChecked()
        ignore_text = not self.text_chk.isChecked()

        self.thread = ComparisonThread(
            old,
            new,
            out,
            ignore_geometry,
            ignore_text,
        )
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.compare_finished)
        self.thread.start()

    def cancel_compare(self):
        if self.thread:
            self.thread.cancel()
            self.btn_cancel.setEnabled(False)
            self.cancelling = True
            self.label_status.setText(f"{self.tr('cancelling')} --:--")
            self.spinner_timer.stop()
            self.spinner.hide()

    def update_progress(self, value: float):
        self.progress.setValue(value)
        if self.start_time is None:
            return
        elapsed = time.perf_counter() - self.start_time
        if value > 0:
            self.estimated_total = elapsed / (value / 100)
        self.update_remaining_time()

    def update_remaining_time(self):
        if self.start_time is None or self.estimated_total is None:
            return
        elapsed = time.perf_counter() - self.start_time
        remaining = max(self.estimated_total - elapsed, 0)
        m, s = divmod(int(remaining + 0.999), 60)
        msg = self.tr("cancelling") if self.cancelling else self.tr("waiting")
        self.label_status.setText(f"{msg} {m:02d}:{s:02d}")

    def _rotate_spinner(self):
        size = self.spinner_base.size()
        pm = QtGui.QPixmap(size)
        pm.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.translate(size.width() / 2, size.height() / 2)
        painter.rotate(self.spinner_angle)
        painter.translate(-size.width() / 2, -size.height() / 2)
        painter.drawPixmap(0, 0, self.spinner_base)
        painter.end()
        self.spinner.setPixmap(pm)
        self.spinner_angle = (self.spinner_angle + 30) % 360

    def _blink_version(self):
        self._blink_state = not self._blink_state
        if self._blink_state:
            self.lbl_update.setStyleSheet("color:red")
        else:
            self.lbl_update.setStyleSheet("color:gray")

    def compare_finished(self, status: str, info: str):
        self.timer.stop()
        self.start_time = None
        self.estimated_total = None
        self.cancelling = False
        self.btn_compare.setEnabled(True)
        self.btn_old.setEnabled(True)
        self.btn_new.setEnabled(True)
        self.edit_old.setEnabled(True)
        self.edit_new.setEnabled(True)
        self.action_improve.setEnabled(True)
        self.action_help.setEnabled(True)
        self.action_settings.setEnabled(True)
        self.action_history.setEnabled(True)
        self.action_admin.setEnabled(True)
        self.btn_cancel.hide()
        self._progress_stack.setCurrentIndex(1)
        self.spinner_timer.stop()
        self.spinner.hide()
        if status == "cancelled":
            QtWidgets.QMessageBox.information(
                self, self.tr("cancelled_title"), self.tr("cancelled_msg")
            )
        elif status == "no_diffs":
            QtWidgets.QMessageBox.information(
                self, self.tr("no_diffs_title"), self.tr("no_diffs_msg")
            )
        elif status == "success":
            QtWidgets.QMessageBox.information(
                self,
                self.tr("success"),
                f"{self.tr('comparison_success')}\n{self.tr('pdf_saved').format(info)}",
            )
            self.view_path = info
            self.btn_view.show()
            self.history.append(
                {
                    "old": os.path.splitext(os.path.basename(self.old_path))[0],
                    "new": os.path.splitext(os.path.basename(self.new_path))[0],
                    "output": info,
                    "old_path": self.old_path,
                    "new_path": self.new_path,
                    "mtime": os.path.getmtime(info),
                    "timestamp": time.time(),
                    "stats": (
                        self.thread.elements_checked,
                        self.thread.diff_count,
                    ),
                }
            )
            self.action_history.setVisible(True)
            self.history_sep.setVisible(True)
        elif status == "error":
            QtWidgets.QMessageBox.critical(self, self.tr("error"), info)
            self.btn_view.hide()
        else:
            self.btn_view.hide()

        if self.thread and status not in ("error", "cancelled"):
            self.last_stats = (
                self.thread.elements_checked,
                self.thread.diff_count,
            )
            stats = self.tr("stats").format(*self.last_stats)
            self.label_status.setText(stats)
        else:
            self.last_stats = None
            self.label_status.setText("")
        if self.history:
            self.action_history.setVisible(True)
            self.history_sep.setVisible(True)
        else:
            self.action_history.setVisible(False)
            self.history_sep.setVisible(False)

    def show_license(self):
        fname = "LICENSE_EN.txt" if self.lang == "en" else "LICENSE_PT.txt"
        license_path = os.path.join(os.path.dirname(__file__), fname)
        try:
            with open(license_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            text = self.tr("license_missing")
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle(self.tr("license_title"))
        dlg.setText(text)
        dlg.setMinimumSize(500, 350)
        dlg.show()
        dlg.move(self.geometry().center() - dlg.rect().center())
        dlg.exec()

    def open_improvement_link(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl(
                "https://forms.office.com/pages/responsepage.aspx?id=UckECKCTXUCA5PqHx1UdaqDQL679cxJPq2yFoswL_2BUNVFZVFYzRFhVUzNaQzU0R0xYVEFNN1VXVi4u&route=shorturl"
            )
        )

    def open_help(self):
        QtWidgets.QMessageBox.information(
            self,
            self.tr("help_label"),
            self.tr("coming_soon"),
        )

    def open_settings(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("settings_title"))
        dlg.resize(200, 100)
        layout = QtWidgets.QVBoxLayout(dlg)
        lbl = QtWidgets.QLabel(self.tr("language"))
        layout.addWidget(lbl)
        combo = QtWidgets.QComboBox()
        combo.addItem("English (US)", "en")
        combo.addItem("Portugu\u00eas (Brasil)", "pt")
        combo.setCurrentIndex(0 if self.lang == "en" else 1)
        layout.addWidget(combo)

        if os.getenv("ADMIN_MODE") == "1":
            manage_btn = QtWidgets.QPushButton(self.tr("manage_users"))
            manage_btn.clicked.connect(self.open_user_admin)
            layout.addWidget(manage_btn)

        btn = QtWidgets.QPushButton("OK")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.set_language(combo.currentData())

    def open_user_admin(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("manage_users"))
        dlg.resize(400, 300)
        layout = QtWidgets.QVBoxLayout(dlg)
        listw = QtWidgets.QListWidget()
        try:
            user_list = load_users()
        except RuntimeError as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        for u in user_list:
            listw.addItem(u)
        layout.addWidget(listw)

        edit = QtWidgets.QLineEdit()
        edit.setPlaceholderText(self.tr("add_user"))
        layout.addWidget(edit)

        buttons = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton(self.tr("add_user"))
        rm_btn = QtWidgets.QPushButton(self.tr("remove_user"))
        buttons.addWidget(add_btn)
        buttons.addWidget(rm_btn)
        layout.addLayout(buttons)

        def add_user():
            name = edit.text().strip()
            if not name:
                return
            for i in range(listw.count()):
                if listw.item(i).text() == name:
                    return
            listw.addItem(name)
            edit.clear()

        def remove_user():
            for item in listw.selectedItems():
                listw.takeItem(listw.row(item))

        add_btn.clicked.connect(add_user)
        rm_btn.clicked.connect(remove_user)

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout.addWidget(box)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)

        if dlg.exec() == QtWidgets.QDialog.Accepted:
            users = [listw.item(i).text() for i in range(listw.count())]
            if not save_users(users):
                QtWidgets.QMessageBox.critical(
                    self, self.tr("error"), self.tr("user_save_failed")
                )

    def open_history(self):
        self.clear_results()
        self._build_history()
        self.stack.setCurrentWidget(self.history_page)
        self._set_fixed_size_centered(self.large_size)

    def open_admin_page(self):
        self.clear_results()
        self._build_admin_page()
        self.stack.setCurrentWidget(self.admin_page)
        self._set_fixed_size_centered(self.large_size)

    def _build_history(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        data = sorted(
            self.history,
            key=lambda e: e.get("timestamp", e.get("mtime", 0)),
            reverse=True,
        )

        table = QtWidgets.QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            [
                self.tr("output_file"),
                self.tr("date"),
                self.tr("status"),
                "",
            ]
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionsClickable(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            "QHeaderView::section{background-color:#000000;color:white;border-bottom:1px solid #cccccc;}"
            "QTableWidget{alternate-background-color:#f0f0f0;}"
        )
        table.setRowCount(len(data))
        for row, entry in enumerate(data):
            name = f"{entry['old']} \u2192 {entry['new']} ({os.path.basename(entry['output'])})"
            item = QtWidgets.QTableWidgetItem(name)
            if os.path.exists(entry["output"]):
                item.setToolTip(entry["output"])
            else:
                item.setToolTip(self.tr("file_missing_hint"))
            table.setItem(row, 0, item)
            date_str = self._format_datetime(
                entry.get("timestamp", entry.get("mtime", 0))
            )
            date_item = QtWidgets.QTableWidgetItem(date_str)
            date_item.setForeground(QtGui.QColor("#666666"))
            table.setItem(row, 1, date_item)
            exists = os.path.exists(entry["output"])
            mtime_same = exists and os.path.getmtime(entry["output"]) == entry.get(
                "mtime"
            )
            if not exists:
                status = self.tr("file_missing")
            elif not mtime_same:
                status = self.tr("file_replaced")
            else:
                status = ""
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(status))
            if exists and mtime_same:
                btn = QtWidgets.QPushButton(self.tr("view_details"))
                btn.setStyleSheet(
                    "QPushButton{background-color:#471F6F;color:white;padding:4px;border-radius:4px;}"
                    "QPushButton:hover{background-color:#5c2c88;}"
                )
                btn.setFixedHeight(self.btn_height)
                btn.setFont(self.btn_font)
                btn.clicked.connect(lambda _, e=entry: self.show_details(e))
                table.setCellWidget(row, 3, btn)
        if not data:
            table.setRowCount(1)
            table.setItem(0, 0, QtWidgets.QTableWidgetItem("-"))
        table.resizeColumnsToContents()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.history_layout.addWidget(table)
        back_btn = QtWidgets.QPushButton(self.tr("back"))
        back_btn.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#333333;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        back_btn.setFixedHeight(self.btn_height)
        back_btn.setFont(self.btn_font)
        back_btn.clicked.connect(
            lambda: (
                self.stack.setCurrentWidget(self.main_page),
                self._set_fixed_size_centered(self.small_size),
            )
        )
        bottom = QtWidgets.QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)
        bottom.addWidget(back_btn)
        bottom.addStretch()
        self.history_layout.addLayout(bottom)

    def _build_admin_page(self):
        while self.admin_layout.count():
            item = self.admin_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("search_users"))
        search_row.addWidget(self.search_edit)
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItem(self.tr("sort_recent"), "recent")
        self.sort_combo.addItem(self.tr("sort_alpha"), "alpha")
        search_row.addWidget(self.sort_combo)
        self.filter_admin_chk = QtWidgets.QCheckBox(self.tr("admin_role"))
        search_row.addWidget(self.filter_admin_chk)
        add_btn = QtWidgets.QPushButton(self.tr("add_user"))
        add_btn.clicked.connect(self._add_user_dialog)
        search_row.addWidget(add_btn)
        self.admin_layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("username"),
                self.tr("real_name"),
                self.tr("email"),
                self.tr("status"),
                "",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(4, 24)
        self.table.horizontalHeader().setSectionResizeMode(
            4, QtWidgets.QHeaderView.Fixed
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QHeaderView::section{background-color:#000000;color:white;border-bottom:1px solid #cccccc;}"
            "QTableWidget{alternate-background-color:#f0f0f0;}"
        )
        self.admin_layout.addWidget(self.table)

        btn_back = QtWidgets.QPushButton(self.tr("back"))
        btn_back.setFixedHeight(self.btn_height)
        btn_back.setFont(self.btn_font)
        btn_back.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#333333;}"
        )
        btn_back.clicked.connect(
            lambda: (
                self.stack.setCurrentWidget(self.main_page),
                self._set_fixed_size_centered(self.small_size),
            )
        )
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(btn_back)
        bottom.addStretch()
        self.admin_layout.addLayout(bottom)

        # cache records to avoid reloading on every search keystroke
        self._user_records = load_user_records()
        self._admins = load_admins()
        self._populate_admin_table()
        self.search_edit.textChanged.connect(self._populate_admin_table)
        self.sort_combo.currentIndexChanged.connect(self._populate_admin_table)
        self.filter_admin_chk.stateChanged.connect(self._populate_admin_table)

    def _populate_admin_table(self):
        records = list(self._user_records)
        query = self.search_edit.text().lower()
        if self.sort_combo.currentData() == "alpha":
            records.sort(key=lambda r: r.get("username", "").lower())
        else:
            records.sort(key=lambda r: r.get("added", 0), reverse=True)
        filtered = [
            r
            for r in records
            if query in r.get("username", "").lower()
            or query in r.get("name", "").lower()
            or query in r.get("email", "").lower()
        ]
        if self.filter_admin_chk.isChecked():
            filtered = [r for r in filtered if r.get("username") in self._admins]
        self.table.setRowCount(len(filtered))
        icons_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        pencil_path = os.path.join(icons_dir, "Icon - Pencil.png")
        if os.path.exists(pencil_path):
            pencil = QtGui.QIcon(pencil_path)
        else:
            pencil = self.style().standardIcon(
                QtWidgets.QStyle.SP_FileDialogDetailedView
            )
        for row, rec in enumerate(filtered):
            for col, key in enumerate(["username", "name", "email"]):
                item = QtWidgets.QTableWidgetItem(rec.get(key, ""))
                self.table.setItem(row, col, item)
            if rec.get("username") in self._admins:
                status = self.tr("admin_role")
                item = QtWidgets.QTableWidgetItem(status)
                item.setForeground(QtGui.QColor("blue"))
            else:
                status = (
                    self.tr("active") if rec.get("active", True) else self.tr("removed")
                )
                item = QtWidgets.QTableWidgetItem(status)
                color = QtGui.QColor(
                    "#b1f2b1" if rec.get("active", True) else "#f8b2b2"
                )
                item.setBackground(color)
            self.table.setItem(row, 3, item)
            btn = QtWidgets.QPushButton()
            btn.setIcon(pencil)
            btn.setIconSize(QtCore.QSize(16, 16))
            btn.setProperty("username", rec.get("username"))
            btn.clicked.connect(self._edit_user_dialog)
            self.table.setCellWidget(row, 4, btn)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.resizeColumnsToContents()
        for i in range(self.table.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Fixed)

    def _add_user_dialog(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("add_user"))
        dlg.resize(400, 150)
        lay = QtWidgets.QFormLayout(dlg)
        user_edit = QtWidgets.QLineEdit()
        name_edit = QtWidgets.QLineEdit()
        email_edit = QtWidgets.QLineEdit()
        lay.addRow(self.tr("username"), user_edit)
        lay.addRow(self.tr("real_name"), name_edit)
        lay.addRow(self.tr("email"), email_edit)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        lay.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            recs = list(self._user_records)
            new_rec = {
                "username": user_edit.text().strip(),
                "name": name_edit.text().strip(),
                "email": email_edit.text().strip(),
                "active": True,
                "added": time.time(),
            }
            if new_rec["username"]:
                names = [r["username"] for r in recs]
                if new_rec["username"] not in names:
                    recs.append(new_rec)
                    save_user_records(recs)
                    self._user_records = recs
            self._populate_admin_table()

    def _edit_user_dialog(self):
        btn = self.sender()
        if not isinstance(btn, QtWidgets.QPushButton):
            return
        username = btn.property("username")
        recs = list(self._user_records)
        admins = list(self._admins)
        rec = next((r for r in recs if r.get("username") == username), None)
        if rec is None:
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("real_name"))
        dlg.resize(400, 200)
        form = QtWidgets.QFormLayout(dlg)

        user_edit = QtWidgets.QLineEdit(rec.get("username", ""))
        name_edit = QtWidgets.QLineEdit(rec.get("name", ""))
        email_edit = QtWidgets.QLineEdit(rec.get("email", ""))
        active_chk = QtWidgets.QCheckBox(self.tr("active"))
        active_chk.setChecked(rec.get("active", True))
        admin_chk = QtWidgets.QCheckBox(self.tr("admin_role"))
        admin_chk.setChecked(username in admins)

        form.addRow(self.tr("username"), user_edit)
        form.addRow(self.tr("real_name"), name_edit)
        form.addRow(self.tr("email"), email_edit)
        date_str = self._format_datetime(rec.get("added", 0))
        form.addRow(self.tr("added_on"), QtWidgets.QLabel(date_str))
        form.addRow(self.tr("status"), active_chk)
        form.addRow(self.tr("admin_role"), admin_chk)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() == QtWidgets.QDialog.Accepted:
            rec["username"] = user_edit.text().strip()
            rec["name"] = name_edit.text().strip()
            rec["email"] = email_edit.text().strip()
            rec["active"] = active_chk.isChecked()

            if admin_chk.isChecked() and rec["username"] not in admins:
                admins.append(rec["username"])
            elif not admin_chk.isChecked() and rec["username"] in admins:
                admins.remove(rec["username"])

            save_user_records(recs, admins)
            self._user_records = recs
            self._admins = admins
            self._populate_admin_table()

    def show_details(self, entry: dict):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("details_title"))
        dlg.resize(200, 150)
        layout = QtWidgets.QVBoxLayout(dlg)

        title = QtWidgets.QLabel(f"{entry['old']} \u2192 {entry['new']}")
        layout.addWidget(title)

        stats = entry.get("stats")
        if stats:
            layout.addWidget(QtWidgets.QLabel(self.tr("stats").format(*stats)))

        date_str = self._format_datetime(entry.get("timestamp", entry.get("mtime", 0)))
        layout.addWidget(QtWidgets.QLabel(f"{self.tr('date')} {date_str}"))

        layout.addWidget(
            QtWidgets.QLabel(
                f"{self.tr('output_file')} {os.path.basename(entry['output'])}"
            )
        )

        exists = os.path.exists(entry["output"])
        mtime_same = exists and os.path.getmtime(entry["output"]) == entry.get("mtime")
        if not exists:
            layout.addWidget(QtWidgets.QLabel(self.tr("file_missing")))
        elif not mtime_same:
            layout.addWidget(QtWidgets.QLabel(self.tr("file_replaced")))

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        view_btn = QtWidgets.QPushButton(self.tr("view_result"))
        view_btn.setStyleSheet(
            "QPushButton{background-color:#471F6F;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#5c2c88;}"
        )
        view_btn.setFixedHeight(self.btn_height)
        view_btn.setFont(self.btn_font)
        if exists and mtime_same:
            view_btn.clicked.connect(
                lambda: QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(entry["output"])
                )
            )
        else:
            view_btn.setEnabled(False)
        btn_row.addWidget(view_btn)
        layout.addLayout(btn_row)
        dlg.setModal(True)
        dlg.exec()

    def open_result(self):
        if hasattr(self, "view_path"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.view_path))
            self.clear_results()

    def _start_update_check(self):
        """Begin asynchronous check for a newer version."""
        self._version_thread = VersionCheckThread(VERSION_FILE)
        self._version_thread.finished.connect(self.check_for_updates)
        self._version_thread.start()

    def check_for_updates(self, latest: str):
        if latest and latest != VERSION:
            self.lbl_version.setStyleSheet("color:#666666")
            self.lbl_version.setText(f"v{VERSION}")
            msg = self.tr("update_available")
            self.lbl_update.setText(msg)
            self.lbl_update.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            self.lbl_update.show()
            self.blink_timer.start(500)
        else:
            self.blink_timer.stop()
            self.lbl_update.hide()
            self.lbl_version.setStyleSheet("color:#666666")
            self.lbl_version.setText(f"v{VERSION}")
            self.lbl_version.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)


if __name__ == "__main__":
    check_for_update()
    # enable high DPI scaling so icons look crisp on high-resolution screens
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])

    user = getpass.getuser()
    try:
        users = load_users()
    except RuntimeError as e:
        QtWidgets.QMessageBox.critical(None, "Error", str(e))
        raise SystemExit(1)

    if user not in users:
        lang = "pt" if os.getenv("LANG", "").startswith("pt") else "en"
        if lang == "pt":
            title = "Acesso negado"
            msg = "Acesso n\u00e3o liberado. Usu\u00e1rio sem cadastro."
        else:
            title = "Access denied"
            msg = "Access not allowed. User not registered."
        QtWidgets.QMessageBox.critical(None, title, msg)
        raise SystemExit(1)

    win = CompareSetQt(is_admin(user))
    win.show()
    app.exec()
