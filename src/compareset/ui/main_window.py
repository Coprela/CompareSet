"""Graphical user interface entry point."""

from PySide6.QtWidgets import QApplication, QMainWindow


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CompareSet")
        # TODO: build the interface


def main() -> None:
    """Launch the GUI application."""
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
