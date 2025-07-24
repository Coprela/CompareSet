import pytest

fitz = pytest.importorskip("fitz")

from pdf_highlighter import gerar_pdf_com_destaques
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

    gerar_pdf_com_destaques(
        str(old),
        str(new),
        [],
        [],
        str(output),
    )

    assert output.exists()


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
        gerar_pdf_com_destaques(
            str(old),
            str(new),
            [],
            [],
            str(output),
        )
