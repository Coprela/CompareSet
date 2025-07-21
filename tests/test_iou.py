import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest

from pdf_diff import _iou


def test_iou_perfect_overlap():
    a = (0, 0, 1, 1)
    b = (0, 0, 1, 1)
    assert _iou(a, b) == pytest.approx(1.0)


def test_iou_partial_overlap():
    a = (0, 0, 2, 2)
    b = (1, 1, 3, 3)
    expected = 1 / 7
    assert _iou(a, b) == pytest.approx(expected)


def test_iou_no_overlap():
    a = (0, 0, 1, 1)
    b = (2, 2, 3, 3)
    assert _iou(a, b) == 0.0
