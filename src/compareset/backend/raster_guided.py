from typing import Dict, Any, List, Tuple, Optional
import fitz
import numpy as np
from ..utils.image_ops import align_images, find_diff_regions, nms_merge
from ..utils.pdf_ops import rasterize_page, px_to_pdf_rects
from .exporters import draw_highlight_rects

RectPx = Tuple[int,int,int,int]

def compare_pdfs_all_pages_raster_guided(old_pdf: str, new_pdf: str, *,
                                         dpi: int = 300,
                                         method: str = "edges",
                                         diff_thresh: int = 25,
                                         dilate_px: int = 3,
                                         erode_px: int = 1,
                                         min_area_px: int = 128,
                                         nms_iou: float = 0.2,
                                         ignore_title_block: bool = False,
                                         ignore_title_rect_pts: Optional[tuple[float,float,float,float]] = None
                                         ) -> Dict[str, Any]:
    """
    Usa raster APENAS para detectar diferenças e aplica retângulos nos PDFs originais.
    Retorna dict com retângulos em pontos por página e estatísticas simples.
    """
    docA = fitz.open(old_pdf)
    docB = fitz.open(new_pdf)
    pages = min(len(docA), len(docB))

    rects_old: Dict[int, List[Tuple[float,float,float,float]]] = {}
    rects_new: Dict[int, List[Tuple[float,float,float,float]]] = {}
    stats: Dict[int, Dict[str, float]] = {}

    for i in range(pages):
        imgA, page_rectA = rasterize_page(old_pdf, i, dpi)
        imgB, page_rectB = rasterize_page(new_pdf, i, dpi)
        if imgA.shape != imgB.shape:
            imgB, page_rectB = rasterize_page(new_pdf, i, dpi)

        A_al, B_al, _ = align_images(imgA, imgB)

        rects_px = find_diff_regions(A_al, B_al, method=method,
                                     diff_thresh=diff_thresh,
                                     dilate_px=dilate_px, erode_px=erode_px,
                                     min_area_px=min_area_px)
        if nms_iou > 0:
            rects_px = nms_merge(rects_px, iou_thr=nms_iou)

        rects_pts = px_to_pdf_rects(rects_px, dpi, page_rectA)
        rects_old[i] = [tuple(r) for r in rects_pts]
        rects_new[i] = [tuple(r) for r in rects_pts]

        area_sum = float(sum((r[2]-r[0])*(r[3]-r[1]) for r in rects_pts))
        stats[i] = {"count": float(len(rects_pts)), "area_pts2": area_sum}

    return {
        "params": {
            "engine": "raster_guided",
            "dpi": dpi, "method": method, "diff_thresh": diff_thresh,
            "dilate_px": dilate_px, "erode_px": erode_px,
            "min_area_px": min_area_px, "nms_iou": nms_iou
        },
        "pages": pages,
        "rects_old": rects_old,
        "rects_new": rects_new,
        "stats": stats
    }

def export_marked_pdfs_all_pages(old_pdf: str, new_pdf: str,
                                 diff_result: Dict[str, Any],
                                 out_old: str, out_new: str,
                                 fill_opacity: float = 0.15, width: float = 0.8) -> None:
    by_page_old = {int(i): [fitz.Rect(*r) for r in rects]
                   for i, rects in diff_result["rects_old"].items()}
    by_page_new = {int(i): [fitz.Rect(*r) for r in rects]
                   for i, rects in diff_result["rects_new"].items()}
    draw_highlight_rects(old_pdf, by_page_old, color_rgb=(1,0,0),
                         out_path=out_old, fill_opacity=fill_opacity, width=width)
    draw_highlight_rects(new_pdf, by_page_new, color_rgb=(0,1,0),
                         out_path=out_new, fill_opacity=fill_opacity, width=width)

def save_diff_json(diff_result: Dict[str, Any], json_path: str) -> None:
    import json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diff_result, f, ensure_ascii=False, indent=2)
