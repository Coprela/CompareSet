"""Minimal command-line interface for the PDF comparator."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend import compare_pdfs, generate_highlighted_pdf


def parse_args() -> argparse.Namespace:
    """Return parsed command line arguments."""
    parser = argparse.ArgumentParser(description="Compare two PDFs and highlight differences")
    parser.add_argument("old_pdf", type=Path, help="path to the old revision")
    parser.add_argument("new_pdf", type=Path, help="path to the new revision")
    parser.add_argument("output", type=Path, help="path for the resulting PDF")
    return parser.parse_args()


def run() -> None:
    """Execute the comparison using command line arguments."""
    args = parse_args()
    removed, added = compare_pdfs(str(args.old_pdf), str(args.new_pdf))
    generate_highlighted_pdf(str(args.old_pdf), str(args.new_pdf), removed, added, str(args.output))
    print(f"Differences highlighted in {args.output}")
