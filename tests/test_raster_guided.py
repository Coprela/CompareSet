from pathlib import Path

import fitz

from src.compareset.compare import compare_pdfs
from src.compareset.presets import get_preset


def _make_pdf(path: Path, rectangles) -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    for rect in rectangles:
        page.draw_rect(fitz.Rect(*rect), color=(0, 0, 0), fill=None)
    doc.save(str(path))
    doc.close()


def test_compare_pdfs_detects_region(tmp_path):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _make_pdf(old_pdf, [(50, 50, 120, 120)])
    _make_pdf(new_pdf, [(50, 50, 120, 120), (130, 130, 170, 170)])

    preset = get_preset("loose")
    params = preset.params.copy(dpi=200)
    result = compare_pdfs(str(old_pdf), str(new_pdf), params=params)

    assert result.pages[0].regions, "Expected at least one detected region"
    change_types = {region.change_type for region in result.pages[0].regions}
    assert "added" in change_types
