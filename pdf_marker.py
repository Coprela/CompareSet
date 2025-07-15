import fitz  # PyMuPDF

COLOR_REMOVE = (1, 0, 0)  # vermelho
COLOR_ADD = (0, 1, 0)     # verde
FILL_OPACITY = 0.2

def gerar_pdf_com_destaques(pdf_old, pdf_new, json_data, output_pdf):
    doc_old = fitz.open(pdf_old)
    doc_new = fitz.open(pdf_new)
    final = fitz.open()

    # === Página 1: PDF antigo com destaques vermelhos (removidos) ===
    for i, page in enumerate(doc_old):
        nova_pagina = final.new_page(width=page.rect.width, height=page.rect.height)
        nova_pagina.show_pdf_page(page.rect, doc_old, i)
        for item in json_data.get("alteracoes_texto", []):
            if item["pagina"] == i:
                r = fitz.Rect(item["bbox"])
                nova_pagina.draw_rect(r, fill=COLOR_REMOVE, width=0, fill_opacity=FILL_OPACITY)

    # === Página 2: PDF novo com destaques verdes (adicionados) ===
    for i, page in enumerate(doc_new):
        nova_pagina = final.new_page(width=page.rect.width, height=page.rect.height)
        nova_pagina.show_pdf_page(page.rect, doc_new, i)
        for item in json_data.get("alteracoes_texto", []):
            if item["pagina"] == i:
                r = fitz.Rect(item["bbox"])
                nova_pagina.draw_rect(r, fill=COLOR_ADD, width=0, fill_opacity=FILL_OPACITY)

    final.save(output_pdf)
    print(f"PDF final com destaques salvo em: {output_pdf}")
