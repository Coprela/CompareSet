import pytest

pytest.importorskip("fitz")
from pdf_diff import (
    _get_standard_label,
    _page_orientation,
    _iou,
    _remove_unchanged,
    _remove_moved_same_text,
    _remove_contained,
    _round,
)


class DummyRect:
    def __init__(self, width, height):
        self.width = width
        self.height = height


def test_page_orientation():
    assert _page_orientation(DummyRect(200, 100)) == "landscape"
    assert _page_orientation(DummyRect(100, 200)) == "portrait"


def test_get_standard_label():
    # A4 size 210 x 297 mm -> convert to points
    mm_per_pt = 25.4 / 72
    width_pt = 210 / mm_per_pt
    height_pt = 297 / mm_per_pt
    assert _get_standard_label(width_pt, height_pt) == "A4"
    # Unknown size
    assert _get_standard_label(100, 100) == ""


def test_iou():
    a = (0, 0, 10, 10)
    b = (5, 5, 15, 15)
    assert _iou(a, b) == 25 / 175
    # no intersection
    c = (20, 20, 30, 30)
    assert _iou(a, c) == 0.0


def test_round():
    assert _round(1.2345, 2) == 1.23
    assert _round(1.2355, 2) == 1.24


def test_remove_unchanged():
    rem = [{"pagina": 1, "bbox": [0, 0, 1, 1], "texto": "a"}]
    add = [{"pagina": 1, "bbox": [0, 0, 1, 1], "texto": "a"}]
    r, a = _remove_unchanged(rem, add)
    assert r == []
    assert a == []


def test_remove_moved_same_text():
    rem = [{"pagina": 1, "bbox": [0, 0, 1, 1], "texto": "a"}]
    add = [{"pagina": 1, "bbox": [0.1, 0.1, 1.1, 1.1], "texto": "a"}]
    r, a = _remove_moved_same_text(rem, add, dist=2)
    assert r == []
    assert a == []


def test_remove_contained():
    boxes = [
        {"pagina": 1, "bbox": [0, 0, 10, 10]},
        {"pagina": 1, "bbox": [2, 2, 8, 8]},
    ]
    filtered = _remove_contained(boxes)
    assert filtered == [boxes[0]]
