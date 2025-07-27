import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QWidget

from compareset.ui.compare_page import ComparePage
import compareset.ui.compare_page as compare_page
import main_interface


class DummyMain:
    def __init__(self):
        self.stack = QWidget()


def test_compare_page_overlay(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    page = ComparePage(DummyMain())
    page.old_path = "old.pdf"
    page.new_path = "new.pdf"
    monkeypatch.setattr(
        compare_page,
        "comparar_pdfs",
        lambda *a, **k: {"removidos": [1], "adicionados": []},
    )
    overlay = {}

    def fake_save(*args, **kwargs):
        overlay["value"] = kwargs.get("mode", "overlay") == "overlay"

    monkeypatch.setattr(compare_page, "compare_pdfs", fake_save)
    monkeypatch.setattr(
        compare_page.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(tmp_path / "out.pdf"), ""),
    )
    monkeypatch.setattr(compare_page.QMessageBox, "information", lambda *a, **k: None)

    page.overlay_chk.setChecked(False)
    page.compare_pdfs()
    assert overlay["value"] is False

    page.overlay_chk.setChecked(True)
    page.compare_pdfs()
    assert overlay["value"] is True


def test_comparison_thread_overlay(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main_interface,
        "comparar_pdfs",
        lambda *a, **k: {"removidos": [1], "adicionados": []},
    )
    captured = {}

    def fake_highlight(*args, **kwargs):
        captured["overlay"] = kwargs.get("mode", "overlay") == "overlay"

    monkeypatch.setattr(main_interface, "compare_pdfs", fake_highlight)
    thread = main_interface.ComparisonThread(
        "old.pdf",
        "new.pdf",
        str(tmp_path / "out.pdf"),
        False,
        False,
        overlay=False,
    )
    thread.run()
    assert captured["overlay"] is False
