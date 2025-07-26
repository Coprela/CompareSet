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


def test_comparar_pdfs_no_resize(monkeypatch, tmp_path):
    fitz = pytest.importorskip("fitz")
    import pdf_diff

    old = fitz.open()
    old.new_page()
    old_path = tmp_path / "old.pdf"
    old.save(old_path)
    old.close()

    new = fitz.open()
    new.new_page()
    new_path = tmp_path / "new.pdf"
    new.save(new_path)
    new.close()

    loaded = []
    orig_loader = pdf_diff._load_pdf_without_signatures

    def loader(path):
        doc = orig_loader(path)
        loaded.append(doc)
        return doc

    monkeypatch.setattr(pdf_diff, "_load_pdf_without_signatures", loader)

    used = []
    orig_extract = pdf_diff._extract_bboxes

    def extract(doc, *args, **kwargs):
        used.append(doc)
        return orig_extract(doc, *args, **kwargs)

    monkeypatch.setattr(pdf_diff, "_extract_bboxes", extract)

    pdf_diff.comparar_pdfs(str(old_path), str(new_path))

    assert used[1] is loaded[1]
