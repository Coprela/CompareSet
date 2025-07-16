import os
import sys
import types
import importlib
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if "fitz" not in sys.modules:
    sys.modules["fitz"] = types.ModuleType("fitz")

comparador = importlib.import_module("comparador")
from comparador import comparar_pdfs


def test_normalize_text():
    assert comparador.normalize_text("  Olá, Mundo!  ") == "olá mundo"


def test_thr_parameter_passed(monkeypatch):
    calls = {}

    def fake_extract(_):
        return [[(0.0, 0.0, 1.0, 1.0, "a")]]

    def fake_compare(old, new, thr):
        calls["thr"] = thr
        return [], []

    monkeypatch.setattr(comparador, "_extract_bboxes", fake_extract)
    monkeypatch.setattr(comparador, "_compare_page", fake_compare)

    comparador.comparar_pdfs("old.pdf", "new.pdf", thr=0.5)
    assert calls.get("thr") == 0.5


def test_comparar_pdfs_bounding_boxes():
    fitz = pytest.importorskip("fitz")
    if not hasattr(fitz, "open"):
        pytest.skip("PyMuPDF not installed")
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
