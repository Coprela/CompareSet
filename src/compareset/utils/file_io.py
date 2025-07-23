"""Helper utilities for file input/output."""

from pathlib import Path


def read_json(path: Path) -> dict:
    """Read a JSON file and return its data."""
    import json

    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
