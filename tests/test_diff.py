"""Tests for the diff module."""

from pathlib import Path
import sys

# Ensure src directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compareset.core import diff


def test_compare_pdfs_placeholder(tmp_path):
    old = tmp_path / "old.pdf"
    new = tmp_path / "new.pdf"
    old.write_bytes(b"%PDF-1.4")
    new.write_bytes(b"%PDF-1.4")
    diff.compare_pdfs(old, new)
