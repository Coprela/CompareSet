"""Developer/test launcher for CompareSet.

This script enables development features (offline mode, role simulation) by
toggling developer mode settings before starting the main application.
"""
from __future__ import annotations

import compareset_env as csenv
from compareset_app import main  # noqa: E402

settings = csenv.get_dev_settings()
if not settings.get("dev_mode", False):
    settings["dev_mode"] = True
    csenv.save_dev_settings(settings)

if __name__ == "__main__":
    main()
