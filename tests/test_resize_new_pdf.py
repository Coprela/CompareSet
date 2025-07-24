import pytest

fitz = pytest.importorskip("fitz")

from pdf_diff import _resize_new_pdf, InvalidDimensionsError


def test_resize_raises_on_invalid_page(tmp_path):
    doc_old = fitz.open()
    doc_old.new_page(width=100, height=100)

    doc_new = fitz.open()
    doc_new.new_page(width=0, height=100)

    with pytest.raises(InvalidDimensionsError):
        _resize_new_pdf(doc_old, doc_new, False)
    doc_old.close()
    doc_new.close()


def test_resize_raises_on_zero_scale(tmp_path):
    doc_old = fitz.open()
    doc_old.new_page(width=0, height=100)

    doc_new = fitz.open()
    doc_new.new_page(width=100, height=100)

    with pytest.raises(InvalidDimensionsError):
        _resize_new_pdf(doc_old, doc_new, False)
    doc_old.close()
    doc_new.close()
