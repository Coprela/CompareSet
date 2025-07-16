from PySide6 import QtWidgets, QtGui, QtCore
import os
from comparador import comparar_pdfs
from pdf_marker import gerar_pdf_com_destaques


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
        self.resize(500, 300)
        self._setup_ui()
        self.thread: ComparisonThread | None = None

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        logo_path = os.path.join(os.path.dirname(__file__), "Imagem", "logo.png")
        if os.path.exists(logo_path):
            pix = QtGui.QPixmap(logo_path).scaledToWidth(200)
            lbl_logo = QtWidgets.QLabel()
            lbl_logo.setPixmap(pix)
            lbl_logo.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(lbl_logo)

        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        self.edit_old = QtWidgets.QLineEdit()
        self.edit_old.setPlaceholderText("Revis\u00e3o antiga")
        self.edit_old.setReadOnly(True)
        btn_old = QtWidgets.QPushButton("Selecionar revis\u00e3o antiga")
        btn_old.clicked.connect(self.select_old)
        grid.addWidget(self.edit_old, 0, 0)
        grid.addWidget(btn_old, 0, 1)

        self.edit_new = QtWidgets.QLineEdit()
        self.edit_new.setPlaceholderText("Nova revis\u00e3o")
        self.edit_new.setReadOnly(True)
        btn_new = QtWidgets.QPushButton("Selecionar nova revis\u00e3o")
        btn_new.clicked.connect(self.select_new)
        grid.addWidget(self.edit_new, 1, 0)
        grid.addWidget(btn_new, 1, 1)

        self.btn_compare = QtWidgets.QPushButton("Comparar Revis\u00f5es")
        self.btn_compare.clicked.connect(self.start_compare)
        layout.addWidget(self.btn_compare)

        self.progress = QtWidgets.QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)

        self.label_status = QtWidgets.QLabel()
        self.label_status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.label_status)

        bottom = QtWidgets.QHBoxLayout()
        layout.addLayout(bottom)

        lbl_credit = QtWidgets.QLabel("Desenvolvido por DDT-FUE")
        lbl_credit.setStyleSheet("color: gray")
        bottom.addWidget(lbl_credit)

        bottom.addStretch()

        lbl_version = QtWidgets.QLabel("Vers\u00e3o 2025.0.1 [Beta]")
        lbl_version.setStyleSheet("color: gray")
        bottom.addWidget(lbl_version)

        btn_license = QtWidgets.QPushButton("Licen\u00e7a")
        btn_license.setFlat(True)
        btn_license.clicked.connect(self.show_license)
        bottom.addWidget(btn_license)

    # slots
    def select_old(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Selecione o PDF antigo", filter="PDF Files (*.pdf)")
        if path:
            self.edit_old.setText(path)

    def select_new(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Selecione o PDF novo", filter="PDF Files (*.pdf)")
        if path:
            self.edit_new.setText(path)

    def start_compare(self):
        old = self.edit_old.text()
        new = self.edit_new.text()
        if not old or not new:
            QtWidgets.QMessageBox.critical(self, "Erro", "Selecione ambos os PDFs para compara\u00e7\u00e3o.")
            return

        out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salvar PDF de compara\u00e7\u00e3o", filter="PDF Files (*.pdf)")
        if not out:
            return

        if out in (old, new):
            QtWidgets.QMessageBox.critical(self, "Erro", "Escolha um nome de arquivo diferente do PDF de entrada.")
            return

        if os.path.exists(out) and not os.access(out, os.W_OK):
            QtWidgets.QMessageBox.warning(self, "Arquivo em uso", "O PDF est\u00e1 aberto em outro programa.")
            return

        self.progress.setValue(0)
        self.progress.show()
        self.label_status.setText("Iniciando...")
        self.btn_compare.setEnabled(False)

        self.thread = ComparisonThread(old, new, out)
        self.thread.progress.connect(self.progress.setValue)
        self.thread.finished.connect(self.compare_finished)
        self.thread.start()

    def compare_finished(self, status: str, info: str):
        self.btn_compare.setEnabled(True)
        self.progress.hide()
        if status == "success":
            QtWidgets.QMessageBox.information(self, "Sucesso", f"PDF salvo em: {info}")
        else:
            QtWidgets.QMessageBox.critical(self, "Erro", info)

    def show_license(self):
        license_path = os.path.join(os.path.dirname(__file__), "LICENSE")
        try:
            with open(license_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            text = "Arquivo de licen\u00e7a n\u00e3o encontrado."
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle("Licen\u00e7a")
        dlg.setText(text)
        dlg.exec()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    win = CompareSetQt()
    win.show()
    app.exec()
