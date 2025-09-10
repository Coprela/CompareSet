import fitz
from src.compareset.backend.raster_guided import compare_pdfs_all_pages_raster_guided


def test_compare_runs_smoke(tmp_path):
    p_old = tmp_path/"old.pdf"
    p_new = tmp_path/"new.pdf"
    for p in (p_old, p_new):
        d = fitz.open(); pg = d.new_page(width=200, height=200)
        pg.draw_rect(fitz.Rect(50,50,150,150))
        d.save(str(p)); d.close()
    res = compare_pdfs_all_pages_raster_guided(str(p_old), str(p_new), dpi=150, min_area_px=16)
    assert res["pages"] == 1
    assert list(res["stats"].values())[0]["count"] == 0.0
