import os
import pytest

pytest.importorskip("fitz")

from comparador import comparar_pdfs


def test_comparar_pdfs_bounding_boxes():
    result = comparar_pdfs(os.path.join("PDFs for test", "R0.pdf"),
                           os.path.join("PDFs for test", "R1.pdf"))

    assert isinstance(result, dict)
    assert "removidos" in result
    assert "adicionados" in result

    for item in result["removidos"] + result["adicionados"]:
        assert isinstance(item, dict)
        assert set(item.keys()) == {"pagina", "bbox"}
        bbox = item["bbox"]
        assert isinstance(bbox, list)
        assert len(bbox) == 4
        for value in bbox:
            assert isinstance(value, float)


def _make_simple_pdf(path, width, height):
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.insert_text((50, 50), "test")
    doc.save(path)


def test_similar_page_sizes(tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"

    _make_simple_pdf(old, 100, 100)
    # 1 pt difference (~0.35 mm) should be ignored
    _make_simple_pdf(new, 101, 101)

    result = comparar_pdfs(str(old), str(new))

    assert result == {"removidos": [], "adicionados": []}
