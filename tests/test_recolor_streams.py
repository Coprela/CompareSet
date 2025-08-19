import sys
from pathlib import Path

import fitz

# Ensure the package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compareset.core.pdf_edit import recolor_targets_in_pdf
from compareset.core.types import Target


def make_test_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    # first line
    page.draw_line((0, 0), (100, 100))
    # second line stays default colour
    page.draw_line((0, 100), (100, 200))
    doc.save(path)


def test_stroked_path_recolored(tmp_path: Path):
    in_pdf = tmp_path / "in.pdf"
    out_pdf = tmp_path / "out.pdf"
    make_test_pdf(in_pdf)

    target = Target(
        obj_id="p0_obj0",
        page_index=0,
        kind="path",
        diff="removed",
        paint_mode="stroke",
        stream_ref="page:0",
        ops_hint=(0, 0),
    )
    recolor_targets_in_pdf(str(in_pdf), str(out_pdf), {0: [target]})

    before_drawings = fitz.open(in_pdf)[0].get_drawings()
    after_drawings = fitz.open(out_pdf)[0].get_drawings()

    # First line is recoloured red
    assert after_drawings[0]["color"] == (1.0, 0.0, 0.0)
    # Second line untouched (still black)
    assert after_drawings[1]["color"] == before_drawings[1]["color"] == (0.0, 0.0, 0.0)
    # Geometry remains the same
    assert after_drawings[0]["rect"] == before_drawings[0]["rect"]
