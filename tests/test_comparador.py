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


def test_tiny_translation_ignored(tmp_path):
    import fitz

    doc1 = fitz.open()
    page = doc1.new_page()
    page.insert_text((50, 50), "hello")
    p1 = tmp_path / "a.pdf"
    doc1.save(p1)
    doc1.close()

    doc2 = fitz.open()
    page = doc2.new_page()
    page.insert_text((50.2, 50.3), "hello")  # shift under 0.5 pt
    p2 = tmp_path / "b.pdf"
    doc2.save(p2)
    doc2.close()

    result = comparar_pdfs(str(p1), str(p2), trans_tol=0.5)
    assert result == {"removidos": [], "adicionados": []}
