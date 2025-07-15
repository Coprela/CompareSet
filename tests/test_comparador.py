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
