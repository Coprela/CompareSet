from __future__ import annotations

import os
from PySide6.QtWidgets import QWidget, QFileDialog, QMessageBox
from PySide6.QtCore import Qt

from pdf_diff import comparar_pdfs, CancelledError
from pdf_highlighter import gerar_pdf_com_destaques

from .utils import load_ui

TRANSLATIONS = {
    "en": {
        "select_old": "Select old PDF",
        "select_new": "Select new PDF",
        "swap": "Swap",
        "compare": "Compare",
        "text": "Text",
        "geom": "Geometry",
    },
    "pt": {
        "select_old": "Selecionar PDF antigo",
        "select_new": "Selecionar PDF novo",
        "swap": "Inverter",
        "compare": "Comparar",
        "text": "Texto",
        "geom": "Elementos geom\u00e9tricos",
    },
}


class ComparePage(QWidget):
    def __init__(self, main: 'MainWindow') -> None:
        super().__init__(parent=main.stack)
        self.main = main
        ui_path = os.path.join(os.path.dirname(__file__), 'compare_page.ui')
        self.ui = load_ui(ui_path, self)
        layout = self.layout()  # layout from .ui
        self.edit_old = self.findChild(QWidget, 'editOld')
        self.btn_old = self.findChild(QWidget, 'btnOld')
        self.edit_new = self.findChild(QWidget, 'editNew')
        self.btn_new = self.findChild(QWidget, 'btnNew')
        self.btn_swap = self.findChild(QWidget, 'btnSwap')
        self.text_chk = self.findChild(QWidget, 'textChk')
        self.geom_chk = self.findChild(QWidget, 'geomChk')
        self.btn_compare = self.findChild(QWidget, 'btnCompare')
        self.progress = self.findChild(QWidget, 'progressBar')

        self.old_path = ''
        self.new_path = ''

        self.btn_old.clicked.connect(self.select_old)
        self.btn_new.clicked.connect(self.select_new)
        self.btn_swap.clicked.connect(self.swap_selection)
        self.btn_compare.clicked.connect(self.compare_pdfs)
        self.text_chk.stateChanged.connect(self._ensure_elements)
        self.geom_chk.stateChanged.connect(self._ensure_elements)

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
        path, _ = QFileDialog.getOpenFileName(self, 'Select old PDF', filter='PDF Files (*.pdf)')
        if path:
            self.old_path = path
            self.edit_old.setText(path)
            self._update_compare_state()

    def select_new(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select new PDF', filter='PDF Files (*.pdf)')
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

    def compare_pdfs(self):
        if not self.old_path or not self.new_path:
            QMessageBox.warning(self, 'Error', 'Select both PDFs for comparison')
            return
        out, _ = QFileDialog.getSaveFileName(self, 'Save comparison PDF', filter='PDF Files (*.pdf)')
        if not out:
            return
        try:
            result = comparar_pdfs(self.old_path, self.new_path)
            if not result['removidos'] and not result['adicionados']:
                QMessageBox.information(self, 'Result', 'No differences found')
                return
            gerar_pdf_com_destaques(
                self.old_path,
                self.new_path,
                result['removidos'],
                result['adicionados'],
                out,
            )
            QMessageBox.information(self, 'Result', f'Comparison PDF saved to: {out}')
        except CancelledError:
            QMessageBox.information(self, 'Result', 'Operation cancelled')
        except Exception as exc:
            QMessageBox.critical(self, 'Error', str(exc))

