import fitz  # PyMuPDF

COLOR_REMOVE = (1, 0, 0)  # vermelho
COLOR_ADD = (0, 1, 0)     # verde
FILL_OPACITY = 0.2


def gerar_pdf_com_destaques(pdf_old: str, pdf_new: str,
                             removidos: list, adicionados: list,
                             output_pdf: str) -> None:
    """Create a PDF highlighting removed and added regions."""
    with fitz.open(pdf_old) as doc_old, fitz.open(pdf_new) as doc_new, fitz.open() as final:
        # Página 1 - antigo com remoções
        for i, page in enumerate(doc_old):
            new_page = final.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(page.rect, doc_old, i)
            for item in removidos:
                if item["pagina"] == i:
                    r = fitz.Rect(item["bbox"])
                    new_page.draw_rect(r, fill=COLOR_REMOVE, width=0,
                                       fill_opacity=FILL_OPACITY)

        # Página 2 - novo com adições
        for i, page in enumerate(doc_new):
            new_page = final.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(page.rect, doc_new, i)
            for item in adicionados:
                if item["pagina"] == i:
                    r = fitz.Rect(item["bbox"])
                    new_page.draw_rect(r, fill=COLOR_ADD, width=0,
                                       fill_opacity=FILL_OPACITY)

        final.save(output_pdf)
        print(f"PDF final com destaques salvo em: {output_pdf}")
