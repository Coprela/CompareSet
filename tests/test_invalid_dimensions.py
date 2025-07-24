import pytest

fitz = pytest.importorskip("fitz")
from pdf_diff import comparar_pdfs, InvalidDimensionsError


def test_invalid_dimensions_all_zero(tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"

    doc_old = fitz.open()
    doc_old.new_page(width=0, height=0)
    doc_old.save(old)
    doc_old.close()

    doc_new = fitz.open()
    doc_new.new_page(width=0, height=0)
    doc_new.save(new)
    doc_new.close()

    with pytest.raises(InvalidDimensionsError):
        comparar_pdfs(str(old), str(new))

