from typing import Optional, Dict, Any
from .raster_guided import compare_pdfs_all_pages_raster_guided

def compare_pdfs_all_pages(old_pdf: str,
                           new_pdf: str,
                           *,
                           engine: str = "raster_guided",
                           dpi: int = 300,
                           method: str = "edges",
                           diff_thresh: int = 25,
                           dilate_px: int = 3,
                           erode_px: int = 1,
                           min_area_px: int = 128,
                           nms_iou: float = 0.2,
                           ignore_title_block: bool = False,
                           ignore_title_rect_pts: Optional[tuple[float,float,float,float]] = None) -> Dict[str, Any]:
    """
    Fachada. Mantém assinatura estável para o frontend.
    engine DEFAULT = "raster_guided".
    """
    if engine == "raster_guided":
        return compare_pdfs_all_pages_raster_guided(
            old_pdf, new_pdf,
            dpi=dpi, method=method, diff_thresh=diff_thresh,
            dilate_px=dilate_px, erode_px=erode_px,
            min_area_px=min_area_px, nms_iou=nms_iou,
            ignore_title_block=ignore_title_block,
            ignore_title_rect_pts=ignore_title_rect_pts
        )
    else:
        raise ValueError(f"Engine desconhecida: {engine}")
