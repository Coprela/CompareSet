# CompareSet

Hybrid PDF comparison pipeline combining raster detection with vector overlays.

## Features
- Rasterises both PDFs at matched DPI using PyMuPDF.
- Combines absolute difference, SSIM, and directional masks to classify **added**,
  **removed**, and **modified** regions.
- Applies translucent vector rectangles on top of the **new** PDF without
  touching the original content streams.
- Emits optional JSON reports with per-page metadata ready for downstream
  tooling.
- Preset-driven tuning (strict / balanced / loose) with the ability to override
  thresholds, DPI, and highlight colours.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
pip install -r requirements.txt
```

## CLI quick start
```bash
python -m compareset --old old.pdf --new new.pdf --out diff.pdf --json diff.json \
    --preset balanced --dpi 300
```

### Common options
- `--preset {strict,balanced,loose}`: select sensitivity bundle.
- `--dpi`: override raster DPI.
- `--absdiff-threshold`, `--ssim-threshold`: fine tune detection.
- `--min-area`, `--padding`, `--merge-iou`: control post processing.
- `--ignore-roi "p1:50,50,500,200"`: ignore a rectangle (points) on page 1.
- `--added-color`, `--removed-color`, `--modified-color`: custom overlay colours.
- `--no-legend`, `--no-bookmarks`: disable additional decorations.

Outputs include bookmarks per affected page and a legend on the first page that
summarises colour usage and key parameters.

## Python API
```python
from compareset import compare_pdfs, get_preset

preset = get_preset("balanced")
result = compare_pdfs("old.pdf", "new.pdf", params=preset.params)
for page in result.pages:
    for region in page.regions:
        print(page.index, region.change_type, region.bbox_pdf)
```

## Performance notes
- Rasterisation scales linearly with DPI. Start with `--preset balanced`
  (300 DPI) and raise only when text-sized changes are missed.
- For large engineering drawings consider `--preset loose` with a custom
  `--min-area` to keep runtimes manageable.
- GPU acceleration is not required; OpenCV is used for morphology only.

## Known limitations
- Large page size mismatches are not auto-aligned; pre-register documents first.
- Scanned or low-quality raster sources can trigger noise despite the presets.
- Transparency interactions rely on PyMuPDF draw commands; complex blend modes
  in the source document remain untouched but may visually stack.
- `--fade-unchanged` is not implemented yet.

## Roadmap
- Alignment helper for significant translations/rotations.
- Split overlays for added vs removed content with per-layer toggles.
- Tiled rasterisation for A0/A1 construction sheets.
- Bookmarks grouped by semantic change category.
- Optional thumbnails and Power BI friendly JSON schema.
- Investigate native acceleration and optional vector recolouring support.
