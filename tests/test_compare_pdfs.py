import pytest

fitz = pytest.importorskip("fitz")

from pdf_highlighter import compare_pdfs


def test_compare_pdfs_detects_rectangle(tmp_path):
    old_path = tmp_path / "old.pdf"
    new_path = tmp_path / "new.pdf"

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(50, 50, 100, 100))
    doc.save(old_path)
    doc.close()

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(50, 50, 100, 100))
    page.draw_rect(fitz.Rect(120, 120, 160, 160))
    doc.save(new_path)
    doc.close()

    diffs, _ = compare_pdfs(
        str(old_path), str(new_path), compare_geom=True, compare_text=False
    )
    assert any(d["status"] == "added" for d in diffs.get(0, []))
