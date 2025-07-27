"""Entry point script for the CompareSet GUI."""

from __future__ import annotations

import sys
import logging
from pathlib import Path

from dotenv import load_dotenv

# Ensure the package in the local "src" directory can be imported when the
# project has not been installed. This allows the helper script to be executed
# directly after cloning the repository or when double-clicked on Windows.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from compareset.ui.main_window import main


def _load_env() -> None:
    """Load configuration from a .env file if present."""
    try:
        load_dotenv()
    except Exception:
        # Failing to load the file should not prevent startup
        pass


if __name__ == "__main__":
    _load_env()
    logging.basicConfig(level=logging.INFO)
    main()
