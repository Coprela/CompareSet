# CompareSet

Comparação de PDFs técnicos com **detecção raster** e **destaque vetorial**.

## Visão geral
O CompareSet realiza comparação de PDFs por um motor **raster-guided**:
rasteriza as páginas **apenas para detectar visualmente as diferenças**
e aplica **retângulos de destaque diretamente nos PDFs originais** (vetoriais),
preservando a nitidez e o conteúdo original. Não “entramos” no PDF para ler texto/vetor.

## Quick start
```
pip install -r requirements.txt
python run_app.py
```

## Como funciona (resumo)
1. Rasteriza páginas A/B no mesmo DPI.
2. Alinha A↔B (corrige deslocamento/rotação pequenos).
3. Detecta regiões alteradas (bordas/absdiff) e gera **bounding boxes**.
4. Converte **pixels → pontos PDF** (1pt = 1/72 in).
5. **Aplica retângulos transparentes** diretamente no PDF original (vetor intacto).

## Estrutura do projeto
```
CompareSet/
├─ src/compareset/
│  ├─ main.py
│  ├─ frontend/
│  │  └─ widgets/
│  ├─ backend/
│  │  ├─ compare_engine.py
│  │  ├─ raster_guided.py
│  │  └─ exporters.py
│  └─ utils/
│     ├─ image_ops.py
│     ├─ pdf_ops.py
│     ├─ version_check.py
│     └─ github_json_manager.py
├─ resources/
│  ├─ icons/
│  ├─ styles/
│  └─ config.json
├─ output/
├─ docs/
│  └─ ARCHITECTURE.md
├─ tests/
│  ├─ test_raster_guided.py
│  └─ test_integration.py
├─ run_app.py
├─ requirements.txt
└─ README.md
```

## Packaging
Siga o script existente `build_package.py` e os requisitos do projeto.
