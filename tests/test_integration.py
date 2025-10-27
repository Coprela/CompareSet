import fitz
from src.compareset.backend.raster_guided import compare_pdfs_all_pages_raster_guided, export_marked_pdfs_all_pages


def test_export_marked(tmp_path):
    old_p = tmp_path/"a.pdf"
    new_p = tmp_path/"b.pdf"
    for p in (old_p, new_p):
        d = fitz.open(); pg = d.new_page(width=200, height=200)
        pg.draw_rect(fitz.Rect(50,50,100,100))
        d.save(str(p)); d.close()
    d = fitz.open(str(new_p)); pg = d[0]
    pg.draw_rect(fitz.Rect(120,120,160,160)); d.save(str(new_p)); d.close()

    res = compare_pdfs_all_pages_raster_guided(str(old_p), str(new_p), dpi=150, min_area_px=16)
    out_old = tmp_path/"old_marked.pdf"
    out_new = tmp_path/"new_marked.pdf"
    export_marked_pdfs_all_pages(str(old_p), str(new_p), res, str(out_old), str(out_new))
    assert out_old.exists() and out_new.exists()
