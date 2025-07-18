import copy
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pdf_diff import _remove_moved_same_text


def test_remove_moved_same_text_word():
    removidos = [{"pagina": 0, "bbox": [0, 0, 10, 10], "texto": "A"}]
    adicionados = [{"pagina": 0, "bbox": [1, 0, 11, 10], "texto": "A"}]
    r, a = _remove_moved_same_text(copy.deepcopy(removidos), copy.deepcopy(adicionados), dist=2)
    assert r == []
    assert a == []


def test_remove_moved_same_text_shape():
    removidos = [{"pagina": 0, "bbox": [50, 50, 52, 52], "texto": ""}]
    adicionados = [{"pagina": 0, "bbox": [50.3, 50.2, 52.3, 52.2], "texto": ""}]
    r, a = _remove_moved_same_text(copy.deepcopy(removidos), copy.deepcopy(adicionados), dist=1)
    assert r == []
    assert a == []


def test_keep_different_text():
    removidos = [{"pagina": 0, "bbox": [0, 0, 10, 10], "texto": "A"}]
    adicionados = [{"pagina": 0, "bbox": [1, 0, 11, 10], "texto": "B"}]
    r, a = _remove_moved_same_text(copy.deepcopy(removidos), copy.deepcopy(adicionados), dist=2)
    assert r == removidos
    assert a == adicionados

