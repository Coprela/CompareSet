# CompareSet

CompareSet – Desktop tool for technical PDF revision comparison.

## Features

- Automated alignment with affine, Euclidean, and phase correlation fallbacks to minimize false positives.
- Two-pass raster diff with optional SSIM refinement for higher precision.
- Ink-aware masking to separate removed content (red) from new content (green).
- Automatic padding, region merging, and vector annotations rendered directly into the PDF output.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python compare_set_gui.py
```

1. Select the old revision PDF and the new revision PDF.
2. Click **Compare** to start the analysis.
3. When the comparison completes, choose where to save the annotated result.

## Output

The application produces a 2-page PDF for each compared page pair: the old revision with red boxes marking removed/changed content, followed by the new revision with green boxes marking added/changed content.
