import pytest

fitz = pytest.importorskip("fitz")

from compareset.utils import normalize_pdf_to_reference


def test_normalize_basic(tmp_path):
    ref_path = tmp_path / "ref.pdf"
    tgt_path = tmp_path / "tgt.pdf"

    doc_ref = fitz.open()
    page = doc_ref.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(50, 50, 150, 150))
    doc_ref.save(ref_path)
    doc_ref.close()

    doc_tgt = fitz.open()
    page = doc_tgt.new_page(width=100, height=100)
    page.draw_rect(fitz.Rect(10, 10, 90, 90))
    doc_tgt.save(tgt_path)
    doc_tgt.close()

    with fitz.open(str(ref_path)) as doc_r, fitz.open(str(tgt_path)) as doc_t:
        result = normalize_pdf_to_reference(doc_r, doc_t)
    assert len(result.document) == 1
    assert pytest.approx(result.transforms[0].scale, rel=1e-3) == 1.25


def test_normalize_handles_missing_target_pages(tmp_path):
    ref_path = tmp_path / "ref.pdf"
    tgt_path = tmp_path / "tgt.pdf"

    doc_ref = fitz.open()
    doc_ref.new_page(width=200, height=200)
    doc_ref.new_page(width=200, height=200)
    doc_ref.save(ref_path)
    doc_ref.close()

    doc_tgt = fitz.open()
    page = doc_tgt.new_page(width=200, height=200)
    page.insert_text((72, 72), "a")
    doc_tgt.save(tgt_path)
    doc_tgt.close()

    result = normalize_pdf_to_reference(str(ref_path), str(tgt_path))
    assert len(result.document) == 2
    assert "a" in result.document[0].get_text()
    assert result.document[1].get_text().strip() == ""


def test_normalize_keeps_extra_target_pages(tmp_path):
    ref_path = tmp_path / "ref.pdf"
    tgt_path = tmp_path / "tgt.pdf"

    doc_ref = fitz.open()
    doc_ref.new_page(width=200, height=200)
    doc_ref.save(ref_path)
    doc_ref.close()

    doc_tgt = fitz.open()
    page = doc_tgt.new_page(width=200, height=200)
    page.insert_text((72, 72), "a")
    page = doc_tgt.new_page(width=200, height=200)
    page.insert_text((72, 72), "b")
    doc_tgt.save(tgt_path)
    doc_tgt.close()

    result = normalize_pdf_to_reference(str(ref_path), str(tgt_path))
    assert len(result.document) == 2
    assert "a" in result.document[0].get_text()
    assert "b" in result.document[1].get_text()
