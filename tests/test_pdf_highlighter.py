import pytest

fitz = pytest.importorskip("fitz")

import pdf_highlighter
from pdf_highlighter import compare_pdfs
from pdf_diff import InvalidDimensionsError


def test_generate_highlights(tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"
    output = tmp_path / "out.pdf"

    for path, text in [(old, "a"), (new, "b")]:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        doc.save(path)
        doc.close()

    compare_pdfs(str(old), str(new), output_path=str(output))

    assert output.exists()


def test_generate_highlights_separate(tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"
    output = tmp_path / "out.pdf"

    for path, text in [(old, "a"), (new, "b")]:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        doc.save(path)
        doc.close()

    compare_pdfs(str(old), str(new), mode="split", output_path=str(output))

    doc_out = fitz.open(str(output))
    assert len(doc_out) == 2
    doc_out.close()


def test_highlighter_invalid_dimensions(tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"
    output = tmp_path / "out.pdf"

    doc_old = fitz.open()
    doc_old.new_page(width=0, height=100)
    doc_old.save(old)
    doc_old.close()

    doc_new = fitz.open()
    doc_new.new_page(width=100, height=100)
    doc_new.save(new)
    doc_new.close()

    with pytest.raises(InvalidDimensionsError):
        compare_pdfs(str(old), str(new), output_path=str(output))


def test_extract_vectors_handles_none_width(monkeypatch, tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"
    out = tmp_path / "out.pdf"

    for path in [old, new]:
        doc = fitz.open()
        page = doc.new_page()
        page.draw_rect(fitz.Rect(0, 0, 50, 50))
        doc.save(path)
        doc.close()

    original = fitz.Page.get_drawings

    def fake_get_drawings(self, *args, **kwargs):
        drawings = original(self, *args, **kwargs)
        for d in drawings:
            d["width"] = None
        return drawings

    monkeypatch.setattr(fitz.Page, "get_drawings", fake_get_drawings)

    compare_pdfs(str(old), str(new), output_path=str(out))


def test_vectors_equal_handles_points():
    vec1 = pdf_highlighter.Vector(
        items=[("l", fitz.Point(0, 0))],
        rect=fitz.Rect(0, 0, 1, 1),
        width=1.0,
        stroke=None,
        fill=None,
        even_odd=False,
    )

    vec2 = pdf_highlighter.Vector(
        items=[("l", (0, 0))],
        rect=fitz.Rect(0, 0, 1, 1),
        width=1.0,
        stroke=None,
        fill=None,
        even_odd=False,
    )

    assert pdf_highlighter._vectors_equal(vec1, vec2)


def test_param_to_list_handles_quad():
    q = fitz.Quad(0, 0, 1, 0, 1, 1, 0, 1)
    assert pdf_highlighter._param_to_list(q) == [0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
