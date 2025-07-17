from PySide6 import QtWidgets, QtGui, QtCore
import os
from pdf_diff import comparar_pdfs
from pdf_highlighter import gerar_pdf_com_destaques


def file_in_use(path: str) -> bool:
    try:
        with open(path, "rb+"):
            return False
    except Exception:
        return True


class ComparisonThread(QtCore.QThread):
    progress = QtCore.Signal(float)
    finished = QtCore.Signal(str, str)

    def __init__(self, old_pdf: str, new_pdf: str, output_pdf: str):
        super().__init__()
        self.old_pdf = old_pdf
        self.new_pdf = new_pdf
        self.output_pdf = output_pdf

    def run(self):
        try:
            dados = comparar_pdfs(
                self.old_pdf,
                self.new_pdf,
                progress_callback=lambda p: self.progress.emit(p / 2),
            )
            gerar_pdf_com_destaques(
                self.old_pdf,
                self.new_pdf,
                dados["removidos"],
                dados["adicionados"],
                self.output_pdf,
                progress_callback=lambda p: self.progress.emit(50 + p / 2),
            )
            self.finished.emit("success", self.output_pdf)
        except Exception as e:
            self.finished.emit("error", str(e))


class CompareSetQt(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CompareSet")
        self.setFixedSize(480, 280)
        icon_path = os.path.join(
            os.path.dirname(__file__), "Images", "Icon - CompareSet.ico"
        )
        icon = QtGui.QIcon(icon_path)
        icon.addFile(icon_path, QtCore.QSize(256, 256))
        self.setWindowIcon(icon)
        self.lang = "pt"
        self.translations = {
            "en": {
                "select_old": "Select old revision",
                "select_new": "Select new revision",
                "compare": "Compare Revisions",
                "developed_by": "Developed by DDT-FUE",
                "copyright": "\u00a9 CompareSet / TechnipFMC",
                "license": "License",
                "select_old_dialog": "Select old PDF",
                "select_new_dialog": "Select new PDF",
                "save_dialog": "Save comparison PDF",
                "error": "Error",
                "success": "Success",
                "select_both": "Select both PDFs for comparison.",
                "choose_diff": "Choose a different file name from the input PDF.",
                "file_in_use": "The PDF is open in another program.",
                "starting": "Starting...",
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
            },
            "pt": {
                "select_old": "Selecionar revis\u00e3o antiga",
                "select_new": "Selecionar nova revis\u00e3o",
                "compare": "Comparar Revis\u00f5es",
                "developed_by": "Desenvolvido por DDT-FUE",
                "copyright": "\u00a9 CompareSet / TechnipFMC",
                "license": "Licen\u00e7a",
                "select_old_dialog": "Selecione o PDF antigo",
                "select_new_dialog": "Selecione o PDF novo",
                "save_dialog": "Salvar PDF de compara\u00e7\u00e3o",
                "error": "Erro",
                "success": "Sucesso",
                "select_both": "Selecione ambos os PDFs para compara\u00e7\u00e3o.",
                "choose_diff": "Escolha um nome de arquivo diferente do PDF de entrada.",
                "file_in_use": "O PDF est\u00e1 aberto em outro programa.",
                "starting": "Iniciando...",
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
            },
        }
        self.old_path = ""
        self.new_path = ""
        self._setup_ui()
        self.thread: ComparisonThread | None = None

    def tr(self, key: str) -> str:
        return self.translations[self.lang].get(key, key)

    def set_language(self, lang: str):
        if lang in self.translations:
            self.lang = lang
        t = self.translations[self.lang]
        self.edit_old.setPlaceholderText("")
        self.btn_old.setText(t["select_old"])
        self.edit_new.setPlaceholderText("")
        self.btn_new.setText(t["select_new"])
        self.btn_compare.setText(t["compare"])
        self.lbl_credit.setText(t["developed_by"])
        self.lbl_copyright.setText(t["copyright"])
        self.btn_license.setText(t["license"])
        self.action_improve.setToolTip(t["improvement_tooltip"])
        self.action_help.setToolTip(t["help_tooltip"])
        self.action_settings.setToolTip(t["settings_tooltip"])

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)

        top.addStretch()

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setMovable(False)

        improve_icon = QtGui.QIcon(
            os.path.join(os.path.dirname(__file__), "Images", "Icon - Improvement.jpg")
        )
        help_icon = QtGui.QIcon(
            os.path.join(os.path.dirname(__file__), "Images", "Icon - Question Mark Help.jpg")
        )
        settings_icon = QtGui.QIcon(
            os.path.join(os.path.dirname(__file__), "Images", "Icon - Gear.jpg")
        )

        self.action_improve = self.toolbar.addAction(improve_icon, "")
        self.action_improve.setToolTip(self.tr("improvement_tooltip"))
        self.action_improve.triggered.connect(self.open_improvement_link)

        self.action_help = self.toolbar.addAction(help_icon, "")
        self.action_help.setToolTip(self.tr("help_tooltip"))
        self.action_help.triggered.connect(self.open_help)

        self.action_settings = self.toolbar.addAction(settings_icon, "")
        self.action_settings.setToolTip(self.tr("settings_tooltip"))
        self.action_settings.triggered.connect(self.open_settings)

        top.addWidget(self.toolbar)


        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        self.edit_old = QtWidgets.QLineEdit()
        self.edit_old.setReadOnly(True)
        self.edit_old.setFixedWidth(200)
        self.edit_old.setAlignment(QtCore.Qt.AlignCenter)
        self.btn_old = QtWidgets.QPushButton()
        self.btn_old.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;}"
            "QPushButton:disabled{background-color:#000000;color:white;}"
        )
        self.btn_old.clicked.connect(self.select_old)
        grid.addWidget(self.edit_old, 0, 0)
        grid.addWidget(self.btn_old, 0, 1)

        self.edit_new = QtWidgets.QLineEdit()
        self.edit_new.setReadOnly(True)
        self.edit_new.setFixedWidth(200)
        self.edit_new.setAlignment(QtCore.Qt.AlignCenter)
        self.btn_new = QtWidgets.QPushButton()
        self.btn_new.setStyleSheet(
            "QPushButton{background-color:#000000;color:white;}"
            "QPushButton:disabled{background-color:#000000;color:white;}"
        )
        self.btn_new.clicked.connect(self.select_new)
        grid.addWidget(self.edit_new, 1, 0)
        grid.addWidget(self.btn_new, 1, 1)

        self.btn_compare = QtWidgets.QPushButton()
        self.btn_compare.setStyleSheet(
            "QPushButton{background-color:#471F6F;color:white;}"
            "QPushButton:disabled{background-color:#471F6F;color:white;}"
        )
        self.btn_compare.clicked.connect(self.start_compare)
        layout.addWidget(self.btn_compare)

        layout.addSpacing(10)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)

        self._progress_placeholder = QtWidgets.QWidget()
        self._progress_placeholder.setFixedHeight(
            self.progress.sizeHint().height()
        )
        self._progress_stack = QtWidgets.QStackedLayout()
        self._progress_stack.addWidget(self.progress)
        self._progress_stack.addWidget(self._progress_placeholder)
        self._progress_stack.setCurrentIndex(1)
        layout.addLayout(self._progress_stack)

        self.label_status = QtWidgets.QLabel()
        self.label_status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.label_status)

        self.lbl_version = QtWidgets.QLabel("CompareSet – Version 2025.0.1 Beta")
        ver_font = self.lbl_version.font()
        ver_font.setPointSize(ver_font.pointSize() + 2)
        ver_font.setBold(True)
        self.lbl_version.setFont(ver_font)
        self.lbl_version.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_version.setStyleSheet("color:#471F6F")
        layout.addWidget(self.lbl_version)

        bottom = QtWidgets.QHBoxLayout()
        layout.addLayout(bottom)

        self.lbl_credit = QtWidgets.QLabel()
        self.lbl_credit.setStyleSheet("color: gray")
        bottom.addWidget(self.lbl_credit)

        bottom.addStretch()

        self.lbl_copyright = QtWidgets.QLabel()
        self.lbl_copyright.setStyleSheet("color: gray")
        bottom.addWidget(self.lbl_copyright)

        self.btn_license = QtWidgets.QPushButton()
        self.btn_license.setStyleSheet(
            "QPushButton{border:1px solid #471F6F;padding:3px;}"
        )
        font = self.btn_license.font()
        font.setBold(True)
        self.btn_license.setFont(font)
        self.btn_license.clicked.connect(self.show_license)
        bottom.addWidget(self.btn_license)

        self.set_language(self.lang)

    # slots
    def select_old(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("select_old_dialog"), filter="PDF Files (*.pdf)")
        if path:
            self.old_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self.edit_old.setText(name)

    def select_new(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("select_new_dialog"), filter="PDF Files (*.pdf)")
        if path:
            self.new_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self.edit_new.setText(name)

    def start_compare(self):
        old = self.old_path
        new = self.new_path
        if not old or not new:
            QtWidgets.QMessageBox.critical(self, self.tr("error"), self.tr("select_both"))
            return

        out, _ = QtWidgets.QFileDialog.getSaveFileName(self, self.tr("save_dialog"), filter="PDF Files (*.pdf)")
        if not out:
            return

        if out in (old, new):
            QtWidgets.QMessageBox.critical(self, self.tr("error"), self.tr("choose_diff"))
            return

        if os.path.exists(out) and file_in_use(out):
            QtWidgets.QMessageBox.warning(self, self.tr("error"), self.tr("file_in_use"))
            return

        self.progress.setValue(0)
        self._progress_stack.setCurrentIndex(0)
        self.label_status.setText(self.tr("starting"))
        self.btn_compare.setEnabled(False)

        self.thread = ComparisonThread(old, new, out)
        self.thread.progress.connect(self.progress.setValue)
        self.thread.progress.connect(self.update_status_label)
        self.thread.finished.connect(self.compare_finished)
        self.thread.start()

    def update_status_label(self, value: float):
        self.label_status.setText(f"{int(value)}%")

    def compare_finished(self, status: str, info: str):
        self.btn_compare.setEnabled(True)
        self._progress_stack.setCurrentIndex(1)
        self.label_status.clear()
        if status == "success":
            QtWidgets.QMessageBox.information(
                self, self.tr("success"), self.tr("pdf_saved").format(info)
            )
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tr("open_pdf_title"),
                self.tr("open_pdf_prompt"),
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(info)
                )
        else:
            QtWidgets.QMessageBox.critical(self, self.tr("error"), info)

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
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(
            "https://forms.office.com/pages/responsepage.aspx?id=UckECKCTXUCA5PqHx1UdaqDQL679cxJPq2yFoswL_2BUNVFZVFYzRFhVUzNaQzU0R0xYVEFNN1VXVi4u&route=shorturl"
        ))

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
        combo.currentIndexChanged.connect(lambda: self.set_language(combo.currentData()))
        layout.addWidget(combo)
        btn = QtWidgets.QPushButton("OK")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    win = CompareSetQt()
    win.show()
    app.exec()
