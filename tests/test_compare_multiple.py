import pytest

fitz = pytest.importorskip("fitz")

from pdf_diff import comparar_pdfs, compare_multiple_pdfs


def make_pdf(path: str, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_compare_multiple(tmp_path):
    pairs = []
    for idx, chars in enumerate([("a", "a"), ("a", "b")]):
        old = tmp_path / f"old{idx}.pdf"
        new = tmp_path / f"new{idx}.pdf"
        make_pdf(str(old), chars[0])
        make_pdf(str(new), chars[1])
        pairs.append((str(old), str(new)))

    progress = []

    def cb(p):
        progress.append(p)

    results = compare_multiple_pdfs(pairs, progress_callback=cb)

    assert len(results) == 2
    assert results[0]["removidos"] == [] and results[0]["adicionados"] == []
    diff_found = results[1]["removidos"] or results[1]["adicionados"]
    assert diff_found
    assert progress and progress[-1] == pytest.approx(100.0)
