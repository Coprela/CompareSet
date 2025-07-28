import pytest

fitz = pytest.importorskip("fitz")

from pdf_highlighter import compare_pdfs


def test_compare_pdfs_char_level(tmp_path):
    old_path = tmp_path / "old.pdf"
    new_path = tmp_path / "new.pdf"

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((72, 72), "ASTM A36")
    doc.save(old_path)
    doc.close()

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((72, 72), "ASTM A32")
    doc.save(new_path)
    doc.close()

    diffs, _ = compare_pdfs(
        str(old_path), str(new_path), char_level=True, compare_geom=False
    )
    statuses = {d["status"] for d in diffs.get(0, [])}
    assert "added" in statuses and "removed" in statuses
