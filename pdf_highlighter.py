"""Generate annotated PDFs highlighting differences."""

from typing import Callable, Optional

import logging

logger = logging.getLogger(__name__)

from pdf_diff import CancelledError, _resize_new_pdf

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
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> None:
    """Create a PDF highlighting removed and added regions.

    The resulting document contains a single page for each pair of
    pages in the input PDFs. Old and new pages are drawn on top of
    each other and differences are indicated by re-drawing the text or
    bounding box in the specified colors.

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
        doc_new_resized = _resize_new_pdf(doc_old, doc_new, True)
        total_steps = len(doc_old) + len(doc_new_resized)
        done = 0

        max_pages = max(len(doc_old), len(doc_new_resized))
        for i in range(max_pages):
            if i < len(doc_old):
                base_page = doc_old[i]
            else:
                base_page = doc_new_resized[i]

            new_page = final.new_page(
                width=base_page.rect.width, height=base_page.rect.height
            )

            if i < len(doc_old):
                new_page.show_pdf_page(new_page.rect, doc_old, i)
            if i < len(doc_new_resized):
                new_page.show_pdf_page(new_page.rect, doc_new_resized, i, overlay=True)

            for item in removidos:
                if item["pagina"] == i:
                    r = fitz.Rect(item["bbox"])
                    r.x0 -= BBOX_MARGIN
                    r.y0 -= BBOX_MARGIN
                    r.x1 += BBOX_MARGIN
                    r.y1 += BBOX_MARGIN
                    texto = str(item.get("texto", "")).strip()
                    if texto:
                        new_page.insert_textbox(
                            r,
                            texto,
                            fontsize=TEXT_SIZE,
                            color=color_remove,
                            overlay=True,
                        )
                    else:
                        new_page.draw_rect(
                            r,
                            color=color_remove,
                            width=0.5,
                            fill_opacity=0,
                            overlay=True,
                        )

            for item in adicionados:
                if item["pagina"] == i:
                    r = fitz.Rect(item["bbox"])
                    r.x0 -= BBOX_MARGIN
                    r.y0 -= BBOX_MARGIN
                    r.x1 += BBOX_MARGIN
                    r.y1 += BBOX_MARGIN
                    texto = str(item.get("texto", "")).strip()
                    if texto:
                        new_page.insert_textbox(
                            r,
                            texto,
                            fontsize=TEXT_SIZE,
                            color=color_add,
                            overlay=True,
                        )
                    else:
                        new_page.draw_rect(
                            r,
                            color=color_add,
                            width=0.5,
                            fill_opacity=0,
                            overlay=True,
                        )

            done += 1
            if progress_callback:
                progress_callback((done / total_steps) * 100)
            if cancel_callback and cancel_callback():
                raise CancelledError()

        final.save(output_pdf)
        doc_new_resized.close()
        if progress_callback:
            progress_callback(100.0)
        logger.info("PDF with highlights saved to %s", output_pdf)
        return
