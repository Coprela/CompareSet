import pytest

fitz = pytest.importorskip("fitz")

from pdf_diff import _resize_new_pdf


def test_resize_skips_zero_pages(tmp_path):
    doc_old = fitz.open()
    doc_old.new_page(width=100, height=100)

    doc_new = fitz.open()
    doc_new.new_page(width=0, height=100)

    resized = _resize_new_pdf(doc_old, doc_new, False)
    assert len(resized) == 1
    assert resized[0].rect.width == 100
    assert resized[0].rect.height == 100
    resized.close()
    doc_old.close()
    doc_new.close()
