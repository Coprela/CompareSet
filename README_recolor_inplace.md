# In-place PDF Recoloring (MVP)

This directory contains a minimal proof of concept for recolouring
specific graphic objects directly inside PDF content streams.  The goal
is to highlight differences between two revisions of a document without
rasterisation or overlays.  The initial implementation supports only
stroked paths drawn directly in page streams.

## Modules

- `compareset.core.types` – dataclasses describing graphic objects and
  recoloring targets.
- `compareset.core.extraction` – utilities built on top of PyMuPDF to
  extract path information.
- `compareset.core.diff_bridge` – helpers converting diff information to
  recolor targets.
- `compareset.core.pdf_edit` – low level editing functions using
  `pikepdf` to inject colour operators.
- `compareset.pipeline.apply_recolor` – convenience wrapper that ties the
  pieces together.

## Limitations

The code focuses purely on recolouring strokes of path objects in page
content streams.  Fills, text, form XObjects and complex colour spaces are
left for future work.
