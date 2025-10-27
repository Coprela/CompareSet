"""Package initialisation and small compatibility helpers."""

from __future__ import annotations

import fitz

from .compare import DiffRegion, DiffResult, PageDiff, RoiMask, compare_pdfs
from .presets import CompareParams, get_preset, iter_presets

__all__ = [
    "compare_pdfs",
    "DiffRegion",
    "DiffResult",
    "PageDiff",
    "RoiMask",
    "CompareParams",
    "get_preset",
    "iter_presets",
    "frontend",
    "backend",
    "utils",
]

__version__ = "0.2.1-beta"


# ---------------------------------------------------------------------------
# PyMuPDF compatibility
# ---------------------------------------------------------------------------

_orig_save = fitz.Document.save


def _patched_save(self, filename, *args, **kwargs):  # pragma: no cover - small wrapper
    """Allow saving to the original file without specifying ``incremental``.

    Newer versions of PyMuPDF require ``incremental=True`` when overwriting the
    existing file.  The test-suite and some callers expect the old behaviour,
    so patch the method to automatically enable incremental saving when the
    output filename matches the document's current name.
    """

    if isinstance(filename, (str, bytes)) and filename == self.name and "incremental" not in kwargs:
        kwargs["incremental"] = True
        # When saving incrementally, encryption must remain unchanged
        kwargs.setdefault("encryption", fitz.PDF_ENCRYPT_KEEP)
    return _orig_save(self, filename, *args, **kwargs)


fitz.Document.save = _patched_save

