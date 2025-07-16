import fitz  # PyMuPDF

COLOR_REMOVE_DEFAULT = (1, 0, 0)  # vermelho
COLOR_ADD_DEFAULT = (0, 0.8, 0)   # verde mais evidente
OPACITY_DEFAULT = 0.4


def gerar_pdf_com_destaques(
    pdf_old: str,
    pdf_new: str,
    removidos: list,
    adicionados: list,
    output_pdf: str,
    color_add: tuple = COLOR_ADD_DEFAULT,
    color_remove: tuple = COLOR_REMOVE_DEFAULT,
    opacity: float = OPACITY_DEFAULT,
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
    opacity : float, optional
        Fill transparency in the range ``0-1``.
    """
    doc_old = fitz.open(pdf_old)
    doc_new = fitz.open(pdf_new)
    final = fitz.open()

    # Página 1 - antigo com remoções
    for i, page in enumerate(doc_old):
        new_page = final.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(page.rect, doc_old, i)
        for item in removidos:
            if item["pagina"] == i:
                r = fitz.Rect(item["bbox"])
                new_page.draw_rect(r, fill=color_remove, width=0,
                                   fill_opacity=opacity)

    # Página 2 - novo com adições
    for i, page in enumerate(doc_new):
        new_page = final.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(page.rect, doc_new, i)
        for item in adicionados:
            if item["pagina"] == i:
                r = fitz.Rect(item["bbox"])
                new_page.draw_rect(r, fill=color_add, width=0,
                                   fill_opacity=opacity)

    final.save(output_pdf)
    print(f"PDF final com destaques salvo em: {output_pdf}")
