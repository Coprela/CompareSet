from typing import Tuple, List
import fitz
import numpy as np

def rasterize_page(pdf_path: str, page_num: int, dpi: int) -> tuple[np.ndarray, fitz.Rect]:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pm = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
    rect = page.rect
    doc.close()
    return img, rect

def px_to_pdf_rects(rects_px: List[tuple[int,int,int,int]], dpi: int, page_rect_pts: fitz.Rect):
    scale = 72.0 / dpi
    out = []
    for (x0,y0,x1,y1) in rects_px:
        rx0 = max(page_rect_pts.x0, page_rect_pts.x0 + x0*scale)
        ry0 = max(page_rect_pts.y0, page_rect_pts.y0 + y0*scale)
        rx1 = min(page_rect_pts.x1, page_rect_pts.x0 + x1*scale)
        ry1 = min(page_rect_pts.y1, page_rect_pts.y0 + y1*scale)
        out.append((rx0, ry0, rx1, ry1))
    return out
