import fitz
from typing import Dict, List, Tuple

def draw_highlight_rects(pdf_in_path: str,
                         rects_by_page: Dict[int, List[fitz.Rect]],
                         color_rgb: Tuple[float,float,float],
                         out_path: str,
                         *,
                         fill_opacity: float = 0.15,
                         width: float = 0.8) -> None:
    """
    Aplica retângulos diretamente nas páginas do PDF original (sem rasterizar a saída).
    """
    doc = fitz.open(pdf_in_path)
    for i, rects in rects_by_page.items():
        if 0 <= i < len(doc):
            page = doc[i]
            for r in rects:
                page.draw_rect(r, color=color_rgb, fill=color_rgb,
                               fill_opacity=fill_opacity, width=width)
    doc.save(out_path)
    doc.close()
