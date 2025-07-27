import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QWidget

from compareset.ui.compare_page import ComparePage, ComparisonThread
import compareset.ui.compare_page as compare_page


class DummyMain:
    def __init__(self):
        self.stack = QWidget()


def test_compare_page_overlay(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    page = ComparePage(DummyMain())
    page.old_path = "old.pdf"
    page.new_path = "new.pdf"
    overlay = {}

    def fake_save(*args, **kwargs):
        overlay["value"] = kwargs.get("mode", "overlay") == "overlay"
        overlay["text"] = kwargs.get("compare_text", False)
        overlay["geom"] = kwargs.get("compare_geom", False)

    monkeypatch.setattr(compare_page, "generate_colored_comparison", fake_save)
    monkeypatch.setattr(
        compare_page.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(tmp_path / "out.pdf"), ""),
    )
    monkeypatch.setattr(compare_page.QMessageBox, "information", lambda *a, **k: None)

    page.overlay_chk.setChecked(False)
    page.compare_pdfs()
    assert overlay["value"] is False
    assert overlay["text"] is True
    assert overlay["geom"] is True

    page.overlay_chk.setChecked(True)
    page.compare_pdfs()
    assert overlay["value"] is True


def test_comparison_thread_overlay(monkeypatch, tmp_path):
    captured = {}

    def fake_highlight(*args, **kwargs):
        captured["overlay"] = kwargs.get("mode", "overlay") == "overlay"

    monkeypatch.setattr(compare_page, "generate_colored_comparison", fake_highlight)
    thread = ComparisonThread(
        "old.pdf",
        "new.pdf",
        str(tmp_path / "out.pdf"),
        overlay=False,
        compare_text=True,
        compare_geom=True,
        iou_threshold=0.6,
    )
    thread.run()
    assert captured["overlay"] is False
