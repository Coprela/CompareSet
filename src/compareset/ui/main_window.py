"""Graphical user interface entry point."""

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from pdf_diff import comparar_pdfs, CancelledError
from pdf_highlighter import gerar_pdf_com_destaques


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CompareSet")
        central = QWidget()
        layout = QVBoxLayout(central)

        self.label_old = QLabel("No old PDF selected")
        self.label_new = QLabel("No new PDF selected")

        btn_old = QPushButton("Select Old PDF")
        btn_new = QPushButton("Select New PDF")
        btn_compare = QPushButton("Compare PDFs")

        layout.addWidget(btn_old)
        layout.addWidget(self.label_old)
        layout.addWidget(btn_new)
        layout.addWidget(self.label_new)
        layout.addWidget(btn_compare)

        btn_old.clicked.connect(self.select_old)
        btn_new.clicked.connect(self.select_new)
        btn_compare.clicked.connect(self.compare_pdfs)

        self.old_path = ""
        self.new_path = ""

        self.setCentralWidget(central)

    # slots
    def select_old(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select old PDF", filter="PDF Files (*.pdf)"
        )
        if path:
            self.old_path = path
            self.label_old.setText(path)

    def select_new(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select new PDF", filter="PDF Files (*.pdf)"
        )
        if path:
            self.new_path = path
            self.label_new.setText(path)

    def compare_pdfs(self) -> None:
        if not self.old_path or not self.new_path:
            QMessageBox.warning(self, "Error", "Select both PDFs for comparison")
            return

        out, _ = QFileDialog.getSaveFileName(
            self, "Save comparison PDF", filter="PDF Files (*.pdf)"
        )
        if not out:
            return

        try:
            result = comparar_pdfs(self.old_path, self.new_path)
            if not result["removidos"] and not result["adicionados"]:
                QMessageBox.information(self, "Result", "No differences found")
                return
            gerar_pdf_com_destaques(
                self.old_path,
                self.new_path,
                result["removidos"],
                result["adicionados"],
                out,
            )
            QMessageBox.information(self, "Result", f"Comparison PDF saved to: {out}")
        except CancelledError:
            QMessageBox.information(self, "Result", "Operation cancelled")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


def main() -> None:
    """Launch the GUI application."""
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
