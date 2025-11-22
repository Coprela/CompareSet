"""Developer/test launcher for CompareSet.

This script enables development features (offline mode, role simulation) by
toggling developer mode settings before starting the main application.
"""
from __future__ import annotations

import compareset_env as csenv
from compareset_app import main  # noqa: E402

settings = csenv.get_dev_settings()
settings["dev_mode"] = True

current_user = csenv.get_current_username()
super_admins = settings.get("super_admins", [])
if current_user not in super_admins:
    super_admins.append(current_user)
settings["super_admins"] = super_admins

local_testers = settings.get("local_storage_testers", [])
if current_user not in local_testers:
    local_testers.append(current_user)
settings["local_storage_testers"] = local_testers

csenv.save_dev_settings(settings)

if __name__ == "__main__":
    main()
