import os
import time
import math
import urllib.request

from PySide6 import QtCore, QtGui, QtWidgets

from pdf_diff import comparar_pdfs, CancelledError
from pdf_highlighter import gerar_pdf_com_destaques

# application version string
VERSION = "0.2.1"

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
    ):
        super().__init__()
        self.old_pdf = old_pdf
        self.new_pdf = new_pdf
        self.output_pdf = output_pdf
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
                progress_callback=lambda p: self.progress.emit(p / 2),
                cancel_callback=self.is_cancelled,
            )
            self.elements_checked = dados.get("verificados", 0)
            self.diff_count = len(dados.get("removidos", [])) + len(dados.get("adicionados", []))
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


class CompareSetQt(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CompareSet")
        # allow slightly taller window for additional spacing
        self.setFixedSize(500, 360)
        icons_dir = os.path.join(os.path.dirname(__file__), "Images")
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
                "improvement_tooltip": "Suggest improvement",
                "help_tooltip": "Coming soon",
                "language": "Language:",
                "settings_tooltip": "Settings",
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
                "view_details": "View details",
                "details_title": "Details",
                "date": "Date:",
                "output_file": "Output file:",
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
                "improvement_tooltip": "Sugerir melhoria",
                "help_tooltip": "Em breve",
                "language": "Idioma:",
                "settings_tooltip": "Configura\u00e7\u00f5es",
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
                "view_details": "Ver detalhes",
                "details_title": "Detalhes",
                "date": "Data:",
                "output_file": "Arquivo:",
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
        self._setup_ui()
        self.check_for_updates()

    def tr(self, key: str) -> str:
        return self.translations[self.lang].get(key, key)

    def set_language(self, lang: str):
        if lang in self.translations:
            self.lang = lang
        t = self.translations[self.lang]
        self.edit_old.setPlaceholderText(t["no_file"])
        self.btn_old.setText(t["select_old"])
        self.edit_new.setPlaceholderText(t["no_file"])
        self.btn_new.setText(t["select_new"])
        self.btn_compare.setText(t["compare"])
        # keep actions without tooltip popups
        self.action_improve.setToolTip("")
        self.action_help.setToolTip("")
        self.action_settings.setToolTip("")
        self.action_history.setToolTip("")
        self.action_improve.setText(t["improve_label"])
        self.action_help.setText(t["help_label"])
        self.action_settings.setText(t["settings_label"])
        self.action_history.setText(t["history"])
        if hasattr(self, "lbl_license"):
            self.lbl_license.setText(f'<a href="#">{t["license"]}</a>')
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
        layout.addSpacing(10)

        top.addStretch()

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        improve_icon = QtGui.QIcon(
            os.path.join(os.path.dirname(__file__), "Images", "Icon - Improvement.png")
        )
        help_icon = QtGui.QIcon(
            os.path.join(
                os.path.dirname(__file__), "Images", "Icon - Question Mark Help.png"
            )
        )
        settings_icon = QtGui.QIcon(
            os.path.join(os.path.dirname(__file__), "Images", "Icon - Gear.png")
        )

        history_icon = QtGui.QIcon(
            os.path.join(os.path.dirname(__file__), "Images", "Icon - History.png")
        )
        self.action_history = self.toolbar.addAction(history_icon, "")
        self.action_history.setToolTip("")
        self.action_history.triggered.connect(self.open_history)
        self.action_history.setVisible(False)

        self.history_sep = self.toolbar.addSeparator()
        self.history_sep.setVisible(False)

        self.action_improve = self.toolbar.addAction(improve_icon, "")
        # disable tooltip popups for cleaner hover behaviour
        self.action_improve.setToolTip("")
        self.action_improve.triggered.connect(self.open_improvement_link)

        self.toolbar.addSeparator()

        self.action_help = self.toolbar.addAction(help_icon, "")
        self.action_help.setToolTip("")
        self.action_help.triggered.connect(self.open_help)

        self.toolbar.addSeparator()

        self.action_settings = self.toolbar.addAction(settings_icon, "")
        self.action_settings.setToolTip("")
        self.action_settings.triggered.connect(self.open_settings)

        # subtle hover effect for toolbar buttons
        self.toolbar.setStyleSheet(
            "QToolButton{background:transparent;border-radius:2px;padding:2px;}"
            "QToolButton:hover{background:#d0d0d0;}"
        )

        top.addWidget(self.toolbar)


        grid = QtWidgets.QGridLayout()
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
        self.btn_old.setFixedHeight(self.edit_old.sizeHint().height())
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
        self.btn_new = QtWidgets.QPushButton()
        self.btn_new.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;padding:4px;border-radius:4px;}"
            "QPushButton:hover{background-color:#333333;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        self.btn_new.setFixedHeight(self.edit_new.sizeHint().height())
        self.btn_new.setEnabled(True)
        self.btn_new.clicked.connect(self.select_new)
        grid.addWidget(self.edit_new, 1, 0)
        grid.addWidget(self.btn_new, 1, 1, alignment=QtCore.Qt.AlignVCenter)

        self.btn_compare = QtWidgets.QPushButton()
        self.btn_compare.setStyleSheet(
            "QPushButton{background-color:#471F6F;color:white;padding:6px;border-radius:4px;}"
            "QPushButton:hover{background-color:#5c2c88;}"
            "QPushButton:disabled{background-color:#555555;color:white;}"
        )
        self.btn_compare.setEnabled(True)
        self.btn_compare.clicked.connect(self.start_compare)
        layout.addWidget(self.btn_compare)

        layout.addSpacing(10)

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
        self.btn_cancel.clicked.connect(self.cancel_compare)
        self.btn_cancel.hide()
        progress_group.addWidget(self.btn_cancel, alignment=QtCore.Qt.AlignCenter)
        # more spacing so the status information and buttons don't feel cramped
        progress_group.setSpacing(8)

        self.btn_view = QtWidgets.QPushButton(self.tr("view_result"))
        self.btn_view.setStyleSheet(
            "QPushButton{background-color:#471F6F;color:white;padding:6px;border-radius:4px;}"
            "QPushButton:hover{background-color:#5c2c88;}"
        )
        self.btn_view.clicked.connect(self.open_result)
        self.btn_view.hide()
        progress_group.addWidget(self.btn_view, alignment=QtCore.Qt.AlignCenter)

        layout.addWidget(self.progress_frame)
        layout.addSpacing(10)

        self.separator = QtWidgets.QFrame()
        self.separator.setFrameShape(QtWidgets.QFrame.HLine)
        self.separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.separator.setStyleSheet("color:#999999")
        layout.addWidget(self.separator)

        self.lbl_version = QtWidgets.QLabel()
        self.lbl_version.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_version.setStyleSheet("color:#666666")

        self.lbl_license = QtWidgets.QLabel()
        self.lbl_license.setAlignment(QtCore.Qt.AlignRight)
        self.lbl_license.setStyleSheet("color:#666666")
        self.lbl_license.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.lbl_license.setOpenExternalLinks(False)
        self.lbl_license.linkActivated.connect(lambda _: self.show_license())

        bottom = QtWidgets.QHBoxLayout()
        # keep the separator close to the version and license labels
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)
        bottom.addWidget(self.lbl_version, stretch=1)
        bottom.addWidget(self.lbl_license)
        layout.addLayout(bottom)

        self.stack.addWidget(self.main_page)
        self.history_page = QtWidgets.QWidget()
        self.history_layout = QtWidgets.QVBoxLayout(self.history_page)
        self.history_layout.setContentsMargins(10, 10, 10, 10)
        self.stack.addWidget(self.history_page)
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

    def select_new(self):
        self.clear_results()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("select_new_dialog"), filter="PDF Files (*.pdf)"
        )
        if path:
            self.new_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self.edit_new.setText(name)

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
        self.lbl_license.setEnabled(False)
        self.action_improve.setEnabled(False)
        self.action_help.setEnabled(False)
        self.action_settings.setEnabled(False)
        self.action_history.setEnabled(False)
        self.history_sep.setVisible(True)

        self.thread = ComparisonThread(
            old,
            new,
            out,
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
        self.lbl_license.setEnabled(True)
        self.action_improve.setEnabled(True)
        self.action_help.setEnabled(True)
        self.action_settings.setEnabled(True)
        self.action_history.setEnabled(True)
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
                self, self.tr("success"), self.tr("pdf_saved").format(info)
            )
            self.view_path = info
            self.btn_view.show()
            self.history.append(
                {
                    "old": os.path.splitext(os.path.basename(self.old_path))[0],
                    "new": os.path.splitext(os.path.basename(self.new_path))[0],
                    "output": info,
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
        dlg.exec()

    def open_improvement_link(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl(
                "https://forms.office.com/pages/responsepage.aspx?id=UckECKCTXUCA5PqHx1UdaqDQL679cxJPq2yFoswL_2BUNVFZVFYzRFhVUzNaQzU0R0xYVEFNN1VXVi4u&route=shorturl"
            )
        )

    def open_help(self):
        QtWidgets.QMessageBox.information(
            self, self.tr("help_tooltip"), self.tr("help_tooltip")
        )

    def open_settings(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("settings_title"))
        layout = QtWidgets.QVBoxLayout(dlg)
        lbl = QtWidgets.QLabel(self.tr("language"))
        layout.addWidget(lbl)
        combo = QtWidgets.QComboBox()
        combo.addItem("English (US)", "en")
        combo.addItem("Portugu\u00eas (Brasil)", "pt")
        combo.setCurrentIndex(0 if self.lang == "en" else 1)
        combo.currentIndexChanged.connect(
            lambda: self.set_language(combo.currentData())
        )
        layout.addWidget(combo)
        btn = QtWidgets.QPushButton("OK")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()

    def open_history(self):
        self.clear_results()
        # rebuild history layout
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        for entry in reversed(self.history):
            row = QtWidgets.QHBoxLayout()
            name = f"{entry['old']} \u2192 {entry['new']} ({os.path.basename(entry['output'])})"
            name_label = QtWidgets.QLabel(name)
            row.addWidget(name_label)
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get('timestamp', entry.get('mtime', 0))))
            date_lbl = QtWidgets.QLabel(date_str)
            date_lbl.setStyleSheet("color:#666666")
            row.addWidget(date_lbl)
            row.addStretch()
            btn = QtWidgets.QPushButton(self.tr("view_details"))
            btn.setStyleSheet(
                "QPushButton{background-color:#471F6F;color:white;padding:4px;border-radius:4px;}"
                "QPushButton:hover{background-color:#5c2c88;}"
            )
            btn.clicked.connect(lambda _, e=entry: self.show_details(e))
            row.addWidget(btn)
            self.history_layout.addLayout(row)
        if not self.history:
            self.history_layout.addWidget(QtWidgets.QLabel("-"))
        self.history_layout.addStretch()
        back_btn = QtWidgets.QPushButton(self.tr("back"))
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.main_page))
        version_lbl = QtWidgets.QLabel(f"v{VERSION}")
        version_lbl.setStyleSheet("color:#666666")
        bottom = QtWidgets.QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addWidget(back_btn)
        bottom.addStretch()
        bottom.addWidget(version_lbl)
        self.history_layout.addLayout(bottom)
        self.stack.setCurrentWidget(self.history_page)

    def show_details(self, entry: dict):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self.tr("details_title"))
        layout = QtWidgets.QVBoxLayout(dlg)

        title = QtWidgets.QLabel(f"{entry['old']} \u2192 {entry['new']}")
        layout.addWidget(title)

        stats = entry.get("stats")
        if stats:
            layout.addWidget(QtWidgets.QLabel(self.tr("stats").format(*stats)))

        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get('timestamp', entry.get('mtime', 0))))
        layout.addWidget(QtWidgets.QLabel(f"{self.tr('date')} {date_str}"))

        layout.addWidget(QtWidgets.QLabel(f"{self.tr('output_file')} {os.path.basename(entry['output'])}"))

        exists = os.path.exists(entry['output'])
        mtime_same = exists and os.path.getmtime(entry['output']) == entry.get('mtime')
        if not exists:
            layout.addWidget(QtWidgets.QLabel(self.tr('file_missing')))
        elif not mtime_same:
            layout.addWidget(QtWidgets.QLabel(self.tr('file_replaced')))

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        view_btn = QtWidgets.QPushButton(self.tr("view_result"))
        if exists and mtime_same:
            view_btn.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(entry['output'])))
        else:
            view_btn.setEnabled(False)
        btn_row.addWidget(view_btn)
        close_btn = QtWidgets.QPushButton(self.tr("back"))
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def open_result(self):
        if hasattr(self, "view_path"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.view_path))

    def check_for_updates(self):
        url = (
            "https://raw.githubusercontent.com/example/CompareSet/main/latest_version.txt"
        )
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                latest = resp.read().decode("utf-8").strip()
            if latest and latest != VERSION:
                QtWidgets.QMessageBox.information(
                    self,
                    self.tr("update_title"),
                    self.tr("update_msg").format(latest),
                )
        except Exception:
            pass


if __name__ == "__main__":
    # enable high DPI scaling so icons look crisp on high-resolution screens
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])
    win = CompareSetQt()
    win.show()
    app.exec()
