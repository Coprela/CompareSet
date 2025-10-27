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

## Frontend interface

The CompareSet web interface lives in `frontend/` and mirrors the original
CompareSet Viewer experience with responsive side-by-side previews, overlay
mode, progress feedback, and a persistent light/dark theme toggle.

### Prerequisites

- Node.js 18+
- npm 9+

### Run locally

```bash
cd frontend
npm install
npm start
```

The development server launches on [http://localhost:5173](http://localhost:5173)
and automatically opens the viewer. Use `VITE_COMPARESET_API` in a `.env` file
within `frontend/` (or export the variable before running `npm start`) to point
the UI at a custom backend. By default it targets
`http://localhost:5000/api/compare`.

### Using the viewer

1. Upload the **old** and **new** PDF revisions.
2. Click **Compare** to send both files to the hybrid backend. The UI displays
   upload/processing progress and renders the annotated PDF returned either as a
   binary stream or Base64 payload.
3. Use the **Download result** button to save the annotated PDF to disk.
4. Toggle between **Side-by-side** and **Overlay** preview modes to review the
   originals or the generated result. Theme selection persists via
   `localStorage`.
5. Click **Run Mock Comparison** to quickly load bundled sample PDFs without
   calling the backend. This is ideal for validating the layout or demonstrating
   the UI offline.

### Backend expectations

The viewer POSTs both PDFs as `multipart/form-data` to
`<API_BASE>/api/compare`. The response can be either an `application/pdf` blob
or JSON of the form:

```json
{ "result": "<base64-encoded-pdf>" }
```

Configure your hybrid raster/vector comparison service accordingly. The default
backend URL (`http://localhost:5000`) aligns with `run_app.py`.

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
