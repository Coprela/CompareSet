import fitz
import pytest
from pdf_diff import _extract_bboxes

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
