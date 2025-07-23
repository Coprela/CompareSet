import pytest

fitz = pytest.importorskip("fitz")

from pdf_highlighter import gerar_pdf_com_destaques


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
