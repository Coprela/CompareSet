import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pdf_diff import _remove_unchanged


def test_remove_unchanged_filters_duplicates():
    rem = [{"pagina": 0, "bbox": [0.0, 0.0, 1.0, 1.0]}]
    add = [{"pagina": 0, "bbox": [0.0, 0.0, 1.0, 1.0]}]
    r, a = _remove_unchanged(rem, add)
    assert r == []
    assert a == []


def test_remove_unchanged_keeps_different_boxes():
    rem = [{"pagina": 0, "bbox": [0.0, 0.0, 1.0, 1.0]}]
    add = [{"pagina": 0, "bbox": [1.0, 1.0, 2.0, 2.0]}]
    r, a = _remove_unchanged(rem, add)
    assert r == rem
    assert a == add
