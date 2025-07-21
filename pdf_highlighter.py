from typing import Callable, Optional

from pdf_diff import CancelledError

import fitz  # PyMuPDF

COLOR_REMOVE_DEFAULT = (1, 0, 0)  # vermelho
COLOR_ADD_DEFAULT = (0, 0.8, 0)  # verde mais evidente
OPACITY_DEFAULT = 0.3
BBOX_MARGIN = 0.5  # increase highlight thickness (points)


def gerar_pdf_com_destaques(
    pdf_old: str,
    pdf_new: str,
    removidos: list,
    adicionados: list,
    output_pdf: str,
    color_add: tuple = COLOR_ADD_DEFAULT,
    color_remove: tuple = COLOR_REMOVE_DEFAULT,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> None:
    """Create a PDF highlighting removed and added regions.

    Parameters
    ----------
    pdf_old, pdf_new : str
        Paths to the PDFs being compared.
    removidos, adicionados : list
        Bounding boxes returned by :func:`comparar_pdfs`.
    output_pdf : str
        File path where the annotated PDF will be saved.
    color_add, color_remove : tuple, optional
        RGB colors in the range ``0-1`` for additions and removals.
        The highlight opacity is fixed at ``0.3``.
    cancel_callback : callable, optional
        Function returning ``True`` to abort the operation.
    """
    with fitz.open(pdf_old) as doc_old, fitz.open(
        pdf_new
    ) as doc_new, fitz.open() as final:
        total_steps = len(doc_old) + len(doc_new)
        done = 0

        max_pages = max(len(doc_old), len(doc_new))
        for i in range(max_pages):
            if i < len(doc_old):
                page = doc_old[i]
                new_page = final.new_page(
                    width=page.rect.width, height=page.rect.height
                )
                new_page.show_pdf_page(page.rect, doc_old, i)
                for item in removidos:
                    if item["pagina"] == i:
                        r = fitz.Rect(item["bbox"])
                        r.x0 -= BBOX_MARGIN
                        r.y0 -= BBOX_MARGIN
                        r.x1 += BBOX_MARGIN
                        r.y1 += BBOX_MARGIN
                        new_page.draw_rect(
                            r,
                            fill=color_remove,
                            width=0,
                            fill_opacity=OPACITY_DEFAULT,
                        )
                done += 1
                if progress_callback:
                    progress_callback((done / total_steps) * 100)
                if cancel_callback and cancel_callback():
                    raise CancelledError()

            if i < len(doc_new):
                page = doc_new[i]
                new_page = final.new_page(
                    width=page.rect.width, height=page.rect.height
                )
                new_page.show_pdf_page(page.rect, doc_new, i)

                # compute transform mapping coordinates from the old PDF to the
                # current page of the new PDF
                if i < len(doc_old):
                    rect_old = doc_old[i].rect
                else:
                    rect_old = page.rect
                rect_new = page.rect
                width_diff = abs(rect_old.width - rect_new.width)
                height_diff = abs(rect_old.height - rect_new.height)
                tolerance_pt = 72 / 25.4
                if width_diff <= tolerance_pt and height_diff <= tolerance_pt:
                    s = 1.0
                    tx = ty = 0.0
                else:
                    sx = rect_old.width / rect_new.width
                    sy = rect_old.height / rect_new.height
                    s = min(sx, sy)
                    tx = (rect_old.width - rect_new.width * s) / 2.0
                    ty = (rect_old.height - rect_new.height * s) / 2.0

                for item in adicionados:
                    if item["pagina"] == i:
                        r_old = fitz.Rect(item["bbox"])
                        # convert from old PDF coordinates into the new page
                        r = fitz.Rect(
                            (r_old.x0 - tx) / s,
                            (r_old.y0 - ty) / s,
                            (r_old.x1 - tx) / s,
                            (r_old.y1 - ty) / s,
                        )
                        r.x0 -= BBOX_MARGIN
                        r.y0 -= BBOX_MARGIN
                        r.x1 += BBOX_MARGIN
                        r.y1 += BBOX_MARGIN
                        new_page.draw_rect(
                            r,
                            fill=color_add,
                            width=0,
                            fill_opacity=OPACITY_DEFAULT,
                        )
                done += 1
                if progress_callback:
                    progress_callback((done / total_steps) * 100)
                if cancel_callback and cancel_callback():
                    raise CancelledError()

        final.save(output_pdf)
        if progress_callback:
            progress_callback(100.0)
        print(f"PDF final com destaques salvo em: {output_pdf}")
        return
