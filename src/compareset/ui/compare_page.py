from __future__ import annotations

import os
from PySide6.QtWidgets import (
    QWidget,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtGui import QDesktopServices

from pdf_diff import comparar_pdfs, CancelledError, InvalidDimensionsError
from pdf_highlighter import gerar_pdf_com_destaques

from .utils import load_ui, root_path


class ComparisonThread(QThread):
    """Background worker that performs the PDF comparison."""

    progress = Signal(float)
    finished = Signal(str, str)

    def __init__(
        self,
        old_pdf: str,
        new_pdf: str,
        output_pdf: str,
        ignore_geometry: bool,
        ignore_text: bool,
        overlay: bool,
    ) -> None:
        super().__init__()
        self.old_pdf = old_pdf
        self.new_pdf = new_pdf
        self.output_pdf = output_pdf
        self.ignore_geometry = ignore_geometry
        self.ignore_text = ignore_text
        self.overlay = overlay
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:  # pragma: no cover - tested via main_interface
        try:
            data = comparar_pdfs(
                self.old_pdf,
                self.new_pdf,
                adaptive=True,
                ignore_geometry=self.ignore_geometry,
                ignore_text=self.ignore_text,
                progress_callback=lambda p: self.progress.emit(p / 2),
                cancel_callback=self.is_cancelled,
            )
            if self.is_cancelled():
                self.finished.emit("cancelled", "")
                return
            if not data["removidos"] and not data["adicionados"]:
                self.progress.emit(100.0)
                self.finished.emit("no_diffs", "")
                return
            gerar_pdf_com_destaques(
                self.old_pdf,
                self.new_pdf,
                data["removidos"],
                data["adicionados"],
                self.output_pdf,
                overlay=self.overlay,
                progress_callback=lambda p: self.progress.emit(50 + p / 2),
                cancel_callback=self.is_cancelled,
            )
            if self.is_cancelled():
                self.finished.emit("cancelled", "")
            else:
                self.finished.emit("success", self.output_pdf)
        except CancelledError:
            self.finished.emit("cancelled", "")
        except Exception as exc:  # pragma: no cover - simplified
            self.finished.emit("error", str(exc))

TRANSLATIONS = {
    "en": {
        "select_old": "Select old PDF",
        "select_new": "Select new PDF",
        "swap": "Swap",
        "compare": "Compare",
        "text": "Text",
        "geom": "Geometry",
        "overlay": "Overlay pages",
        "license": "License",
        "not_found": "License file not found.",
    },
    "pt": {
        "select_old": "Selecionar PDF antigo",
        "select_new": "Selecionar PDF novo",
        "swap": "Inverter",
        "compare": "Comparar",
        "text": "Texto",
        "geom": "Elementos geom\u00e9tricos",
        "overlay": "Sobrepor páginas",
        "license": "Licença",
        "not_found": "Arquivo de licença não encontrado.",
    },
}


class ComparePage(QWidget):
    def __init__(self, main: "MainWindow") -> None:
        super().__init__(parent=main.stack)
        self.main = main
        ui_path = os.path.join(os.path.dirname(__file__), "compare_page.ui")
        self.ui = load_ui(ui_path, self)
        layout = self.layout()  # layout from .ui
        self.edit_old = self.findChild(QWidget, "editOld")
        self.btn_old = self.findChild(QWidget, "btnOld")
        self.edit_new = self.findChild(QWidget, "editNew")
        self.btn_new = self.findChild(QWidget, "btnNew")
        self.btn_swap = self.findChild(QWidget, "btnSwap")
        self.text_chk = self.findChild(QWidget, "textChk")
        self.geom_chk = self.findChild(QWidget, "geomChk")
        self.overlay_chk = self.findChild(QWidget, "overlayChk")
        self.btn_compare = self.findChild(QWidget, "btnCompare")
        self.progress = self.findChild(QWidget, "progressBar")
        self.label_status = self.findChild(QWidget, "labelStatus")
        self.btn_cancel = self.findChild(QWidget, "btnCancel")
        self.btn_view = self.findChild(QWidget, "btnView")
        self.btn_license = self.findChild(QWidget, "btnLicense")

        self.thread: ComparisonThread | None = None
        self.output_path = ""

        self.old_path = ""
        self.new_path = ""

        self.btn_old.clicked.connect(self.select_old)
        self.btn_new.clicked.connect(self.select_new)
        self.btn_swap.clicked.connect(self.swap_selection)
        self.btn_compare.clicked.connect(self.start_compare)
        self.btn_cancel.clicked.connect(self.cancel_compare)
        self.btn_view.clicked.connect(self.open_result)
        if self.btn_license:
            self.btn_license.clicked.connect(self.show_license)
            self.btn_license.setStyleSheet(
                "QPushButton{background:transparent;color:#888;border:none;padding:0px;}"
            )
        self.text_chk.stateChanged.connect(self._ensure_elements)
        self.geom_chk.stateChanged.connect(self._ensure_elements)

        if self.btn_cancel:
            self.btn_cancel.setStyleSheet(
                "QPushButton{background-color:#c0392b;color:white;font-weight:bold;padding:4px;border-radius:4px;}"
                "QPushButton:hover{background-color:#e74c3c;}"
                "QPushButton:disabled{background-color:#555555;color:white;}"
            )
            self.btn_cancel.setVisible(False)
        if self.btn_view:
            self.btn_view.setVisible(False)

        self.lang = "en"
        self.set_language(self.lang)

    def _ensure_elements(self):
        if not (self.text_chk.isChecked() or self.geom_chk.isChecked()):
            sender = self.sender()
            if sender == self.text_chk:
                self.text_chk.setChecked(True)
            else:
                self.geom_chk.setChecked(True)

    def select_old(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select old PDF", filter="PDF Files (*.pdf)"
        )
        if path:
            self.old_path = path
            self.edit_old.setText(path)
            self._update_compare_state()

    def select_new(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select new PDF", filter="PDF Files (*.pdf)"
        )
        if path:
            self.new_path = path
            self.edit_new.setText(path)
            self._update_compare_state()

    def swap_selection(self):
        self.old_path, self.new_path = self.new_path, self.old_path
        self.edit_old.setText(self.old_path)
        self.edit_new.setText(self.new_path)
        self._update_compare_state()

    def _update_compare_state(self):
        enabled = bool(self.old_path and self.new_path)
        self.btn_compare.setEnabled(enabled)

    def set_language(self, lang: str) -> None:
        """Update labels according to ``lang`` (``'en'`` or ``'pt'``)."""
        self.lang = lang if lang in TRANSLATIONS else "en"
        t = TRANSLATIONS[self.lang]
        self.btn_old.setText(t["select_old"])
        self.btn_new.setText(t["select_new"])
        self.btn_swap.setText(t["swap"])
        self.btn_compare.setText(t["compare"])
        self.text_chk.setText(t["text"])
        self.geom_chk.setText(t["geom"])
        self.overlay_chk.setText(t["overlay"])
        if self.btn_cancel:
            self.btn_cancel.setText("Cancel" if self.lang == "en" else "Cancelar")
        if self.btn_view:
            self.btn_view.setText("View result" if self.lang == "en" else "Ver resultado")
        if self.btn_license:
            self.btn_license.setText(t["license"])

    def compare_pdfs(self, resize: bool = True):
        if not self.old_path or not self.new_path:
            QMessageBox.warning(self, "Error", "Select both PDFs for comparison")
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Save comparison PDF", filter="PDF Files (*.pdf)"
        )
        if not out:
            return
        try:
            result = comparar_pdfs(
                self.old_path,
                self.new_path,
                resize=resize,
            )
            if not result["removidos"] and not result["adicionados"]:
                QMessageBox.information(self, "Result", "No differences found")
                return
            gerar_pdf_com_destaques(
                self.old_path,
                self.new_path,
                result["removidos"],
                result["adicionados"],
                out,
                overlay=self.overlay_chk.isChecked(),
            )
            QMessageBox.information(self, "Result", f"Comparison PDF saved to: {out}")
        except CancelledError:
            QMessageBox.information(self, "Result", "Operation cancelled")
        except InvalidDimensionsError:
            QMessageBox.warning(
                self,
                "Erro",
                "Não foi possível comparar as páginas. Verifique se ambos os PDFs "
                "possuem conteúdo visível e dimensões válidas.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # --- async interface used by the GUI ---
    def start_compare(self) -> None:
        if not self.old_path or not self.new_path:
            QMessageBox.warning(self, "Error", "Select both PDFs for comparison")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save comparison PDF", filter="PDF Files (*.pdf)")
        if not out:
            return
        self.output_path = out
        self.progress.setValue(0)
        if self.label_status:
            self.label_status.setText("Please wait")
        if self.btn_cancel:
            self.btn_cancel.setVisible(True)
            self.btn_cancel.setEnabled(True)
        self.btn_compare.setEnabled(False)
        self.thread = ComparisonThread(
            self.old_path,
            self.new_path,
            out,
            ignore_geometry=not self.geom_chk.isChecked(),
            ignore_text=not self.text_chk.isChecked(),
            overlay=self.overlay_chk.isChecked(),
        )
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.compare_finished)
        self.thread.start()

    def cancel_compare(self) -> None:
        if self.thread:
            self.thread.cancel()
            if self.btn_cancel:
                self.btn_cancel.setEnabled(False)
            if self.label_status:
                self.label_status.setText("Cancelling...")

    def update_progress(self, value: float) -> None:
        self.progress.setValue(int(value))

    def compare_finished(self, status: str, info: str) -> None:
        self.btn_compare.setEnabled(True)
        if self.btn_cancel:
            self.btn_cancel.setVisible(False)
        if status == "success":
            if self.label_status:
                self.label_status.setText("Done")
            if self.btn_view:
                self.btn_view.setVisible(True)
                self.btn_view.setEnabled(True)
        elif status == "no_diffs":
            QMessageBox.information(self, "Result", "No differences found")
            if self.label_status:
                self.label_status.setText("")
        elif status == "cancelled":
            QMessageBox.information(self, "Result", "Operation cancelled")
            if self.label_status:
                self.label_status.setText("")
        elif status == "error":
            QMessageBox.critical(self, "Error", info)
            if self.label_status:
                self.label_status.setText("")
        self.thread = None

    def open_result(self) -> None:
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))

    def show_license(self) -> None:
        t = TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])
        fname = "LICENSE_EN.txt" if self.main.lang == "en" else "LICENSE_PT.txt"
        path = root_path(fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            text = t.get("not_found", "License not found")
        QMessageBox.information(self, t.get("license", "License"), text)
