"""Developer/test launcher for CompareSet.

This script enables development features (offline mode, role simulation) by
setting environment flags before starting the main application.
"""
from __future__ import annotations

import os

# Enable developer/test mode
os.environ["COMPARESET_DEV_MODE"] = "1"

from compareset_app import main  # noqa: E402

if __name__ == "__main__":
    main()
