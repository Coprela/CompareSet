import pytest

fitz = pytest.importorskip("fitz")
from pdf_diff import _extract_bboxes


def test_ignore_text_only(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello")
    boxes = _extract_bboxes(doc, ignore_text=True)
    assert boxes == [[]]
    doc.close()


def test_ignore_geometry_only(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(0, 0, 100, 100))
    boxes = _extract_bboxes(doc, ignore_geometry=True)
    assert boxes == [[]]
    doc.close()
