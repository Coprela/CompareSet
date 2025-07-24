import pytest

fitz = pytest.importorskip("fitz")
from pdf_diff import _extract_bboxes  # noqa: E402


def test_extract_bboxes_invalid_transform_length(tmp_path):
    doc = fitz.open()
    doc.new_page()
    invalid = [(1.0, 1.0, 0.0)]
    with pytest.raises(ValueError):
        _extract_bboxes(doc, invalid)
    doc.close()


def test_extract_bboxes_invalid_transform_type(tmp_path):
    doc = fitz.open()
    doc.new_page()
    invalid = [(1.0, 1.0, 0.0, 0.0, "a")]
    with pytest.raises(TypeError):
        _extract_bboxes(doc, invalid)
    doc.close()


def test_extract_bboxes_zero_scale(tmp_path):
    doc = fitz.open()
    doc.new_page()
    invalid = [(0.0, 1.0, 0.0, 0.0)]
    with pytest.raises(ValueError):
        _extract_bboxes(doc, invalid)
    doc.close()


def test_extract_bboxes_matrix_transform(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(0, 0, 10, 10))
    # translation by (5, 5)
    transforms = [(1.0, 0.0, 0.0, 1.0, 5.0, 5.0)]
    boxes = _extract_bboxes(doc, transforms)
    assert boxes[0] == [(5.0, 5.0, 15.0, 15.0, "")]
    doc.close()


def test_extract_bboxes_error_uses_page_index(monkeypatch):
    doc = fitz.open()
    for _ in range(3):
        doc.new_page()

    transforms = [
        (1.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (1.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (1.0, 1.0, 0.0, 0.0, 0.0, 0.0),
    ]

    original_matrix = fitz.Matrix
    call_count = 0

    def fake_matrix(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("boom")
        return original_matrix(*args, **kwargs)

    monkeypatch.setattr(fitz, "Matrix", fake_matrix)

    with pytest.raises(ValueError) as excinfo:
        _extract_bboxes(doc, transforms)

    assert "Transform 1" in str(excinfo.value)
    doc.close()
