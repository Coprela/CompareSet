import fitz  # PyMuPDF
from typing import Callable, Optional

COLOR_REMOVE_DEFAULT = (1, 0, 0)  # vermelho
COLOR_ADD_DEFAULT = (0, 0.8, 0)   # verde mais evidente
OPACITY_DEFAULT = 0.3


def gerar_pdf_com_destaques(
    pdf_old: str,
    pdf_new: str,
    removidos: list,
    adicionados: list,
    output_pdf: str,
    color_add: tuple = COLOR_ADD_DEFAULT,
    color_remove: tuple = COLOR_REMOVE_DEFAULT,
    progress_callback: Optional[Callable[[float], None]] = None,
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
    """
    with fitz.open(pdf_old) as doc_old, fitz.open(pdf_new) as doc_new, fitz.open() as final:
        total_steps = len(doc_old) + len(doc_new)
        done = 0

        max_pages = max(len(doc_old), len(doc_new))
        for i in range(max_pages):
            if i < len(doc_old):
                page = doc_old[i]
                new_page = final.new_page(width=page.rect.width, height=page.rect.height)
                new_page.show_pdf_page(page.rect, doc_old, i)
                for item in removidos:
                    if item["pagina"] == i:
                        r = fitz.Rect(item["bbox"])
                        new_page.draw_rect(
                            r,
                            fill=color_remove,
                            width=0,
                            fill_opacity=OPACITY_DEFAULT,
                        )
                done += 1
                if progress_callback:
                    progress_callback((done / total_steps) * 100)

            if i < len(doc_new):
                page = doc_new[i]
                new_page = final.new_page(width=page.rect.width, height=page.rect.height)
                new_page.show_pdf_page(page.rect, doc_new, i)
                for item in adicionados:
                    if item["pagina"] == i:
                        r = fitz.Rect(item["bbox"])
                        new_page.draw_rect(
                            r,
                            fill=color_add,
                            width=0,
                            fill_opacity=OPACITY_DEFAULT,
                        )
                done += 1
                if progress_callback:
                    progress_callback((done / total_steps) * 100)

        final.save(output_pdf)
        if progress_callback:
            progress_callback(100.0)
        print(f"PDF final com destaques salvo em: {output_pdf}")
        return
