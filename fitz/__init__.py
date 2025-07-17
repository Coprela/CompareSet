"""Minimal stub for the :mod:`fitz` package used in tests.

If the real PyMuPDF library is installed this module will import and expose it
instead of the lightweight test stub.  This allows the application code to work
normally when PyMuPDF is available while still providing the bare minimum for
unit tests when it isn't.
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _load_real_fitz():
    """Load the actual PyMuPDF package if it is installed."""

    current_dir = os.path.dirname(__file__)
    search_paths = [p for p in sys.path if os.path.abspath(p) != os.path.abspath(current_dir)]
    spec = importlib.util.find_spec("fitz", search_paths)
    if spec and spec.origin and os.path.abspath(spec.origin) != os.path.abspath(__file__):
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)
        return module
    return None


real_fitz = _load_real_fitz()
if real_fitz is not None:
    globals().update(real_fitz.__dict__)
else:
    class Rect:
        def __init__(self, x0=0, y0=0, x1=0, y1=0):
            self.x0 = x0
            self.y0 = y0
            self.x1 = x1
            self.y1 = y1

        @property
        def width(self):
            return self.x1 - self.x0

        @property
        def height(self):
            return self.y1 - self.y0


    class Document:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass


    class Pixmap:
        """Minimal stand in for :class:`fitz.Pixmap`."""

        def __init__(self, width=0, height=0, samples=b"", alpha=0):
            self.width = width
            self.height = height
            self.samples = samples
            self.alpha = alpha

    def open(*args, **kwargs):
        return Document()

