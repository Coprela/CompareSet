"""Generate annotated PDFs highlighting differences."""

from typing import Callable, Optional

import logging

logger = logging.getLogger(__name__)

from pdf_diff import CancelledError, InvalidDimensionsError
from compareset.utils import normalize_pdf_to_reference

import fitz  # PyMuPDF

COLOR_REMOVE_DEFAULT = (1, 0, 0)  # vermelho
COLOR_ADD_DEFAULT = (0, 0.8, 0)  # verde mais evidente
OPACITY_DEFAULT = 0.3
BBOX_MARGIN = 0.5  # increase highlight thickness (points)
TEXT_SIZE = 8  # default font size for difference labels


def gerar_pdf_com_destaques(
    pdf_old: str,
    pdf_new: str,
    removidos: list[dict],
    adicionados: list[dict],
    output_pdf: str,
    color_add: tuple = COLOR_ADD_DEFAULT,
    color_remove: tuple = COLOR_REMOVE_DEFAULT,
    overlay: bool = True,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> None:
    """Create a PDF highlighting removed and added regions.

    When ``overlay`` is ``True`` (default) the resulting document
    contains a single page for each pair of pages in the input PDFs,
    with old and new pages drawn on top of each other. When ``overlay``
    is ``False`` each pair of pages generates two output pages,
    one for the old PDF and another for the new PDF.

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
    overlay : bool, optional
        If ``True`` overlay old and new pages on the same output page.
        Otherwise generate two pages for each pair.
    cancel_callback : callable, optional
        Function returning ``True`` to abort the operation.
    """
with fitz.open(pdf_old) as doc_old, fitz.open(pdf_new) as doc_new, fitz.open() as final:
    normalized = normalize_pdf_to_reference(doc_old, doc_new)

        doc_new_resized = normalized.document
        try:
            if overlay:
                total_steps = max(len(doc_old), len(doc_new_resized))
            else:
                total_steps = len(doc_old) + len(doc_new_resized)
            done = 0

            max_pages = max(len(doc_old), len(doc_new_resized))
            for i in range(max_pages):
                if overlay:
                    if i < len(doc_old):
                        base_page = doc_old[i]
                    else:
                        base_page = doc_new_resized[i]

                    if base_page.rect.width == 0 or base_page.rect.height == 0:
                        raise InvalidDimensionsError(
                            f"page {i} has invalid size ({base_page.rect.width} x {base_page.rect.height})"
                        )

                    page_out = final.new_page(
                        width=base_page.rect.width, height=base_page.rect.height
                    )

                    if i < len(doc_old):
                        page_out.show_pdf_page(page_out.rect, doc_old, i)
                    if i < len(doc_new_resized):
                        page_out.show_pdf_page(
                            page_out.rect, doc_new_resized, i, overlay=True
                        )

                    rem_pages = [page_out]
                    add_pages = [page_out]
                    done += 1
                    if progress_callback:
                        progress_callback((done / total_steps) * 100)
                    if cancel_callback and cancel_callback():
                        raise CancelledError()
            else:
                rem_pages = []
                add_pages = []
                if i < len(doc_old):
                    old_page = doc_old[i]
                    if old_page.rect.width == 0 or old_page.rect.height == 0:
                        raise InvalidDimensionsError(
                            f"page {i} has invalid size ({old_page.rect.width} x {old_page.rect.height})"
                        )
                    page_rem = final.new_page(
                        width=old_page.rect.width, height=old_page.rect.height
                    )
                    page_rem.show_pdf_page(page_rem.rect, doc_old, i)
                    rem_pages.append(page_rem)
                    done += 1
                    if progress_callback:
                        progress_callback((done / total_steps) * 100)
                    if cancel_callback and cancel_callback():
                        raise CancelledError()

                if i < len(doc_new_resized):
                    new_page_src = doc_new_resized[i]
                    if new_page_src.rect.width == 0 or new_page_src.rect.height == 0:
                        raise InvalidDimensionsError(
                            f"page {i} has invalid size ({new_page_src.rect.width} x {new_page_src.rect.height})"
                        )
                    page_add = final.new_page(
                        width=new_page_src.rect.width, height=new_page_src.rect.height
                    )
                    page_add.show_pdf_page(page_add.rect, doc_new_resized, i)
                    add_pages.append(page_add)
                    done += 1
                    if progress_callback:
                        progress_callback((done / total_steps) * 100)
                    if cancel_callback and cancel_callback():
                        raise CancelledError()

            for page_ref, items, color in [
                (p, removidos, color_remove) for p in rem_pages
            ] + [(p, adicionados, color_add) for p in add_pages]:
                for item in items:
                    if item["pagina"] == i:
                        r = fitz.Rect(item["bbox"])
                        r.x0 -= BBOX_MARGIN
                        r.y0 -= BBOX_MARGIN
                        r.x1 += BBOX_MARGIN
                        r.y1 += BBOX_MARGIN
                        texto = str(item.get("texto", "")).strip()
                        if texto:
                            page_ref.insert_textbox(
                                r,
                                texto,
                                fontsize=TEXT_SIZE,
                                color=color,
                                overlay=True,
                            )
                        else:
                            page_ref.draw_rect(
                                r,
                                color=color,
                                width=0.5,
                                fill_opacity=0,
                                overlay=True,
                            )

            final.save(output_pdf)
            if progress_callback:
                progress_callback(100.0)
            logger.info("PDF with highlights saved to %s", output_pdf)
        finally:
            doc_new_resized.close()
        return
