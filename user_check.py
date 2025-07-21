"""Remote user management for CompareSet."""

from __future__ import annotations

import os
from typing import List

from github_json_manager import load_json, save_json

ALLOWED_USERS_FILE = os.getenv("ALLOWED_USERS_FILE", "allowed_users.json")


def load_users() -> List[str]:
    """Return the list of allowed users from the remote repository."""
    data = load_json(ALLOWED_USERS_FILE)
    if not data:
        raise RuntimeError("Unable to fetch user list from GitHub")
    users = data.get("users", [])
    if isinstance(users, list):
        return [str(u) for u in users]
    return []


def save_users(users: List[str]) -> bool:
    """Save *users* to the GitHub repository. Returns ``True`` on success."""
    data = {"users": sorted(set(users))}
    return save_json(ALLOWED_USERS_FILE, data, "Atualiza\u00e7\u00e3o da lista de usu\u00e1rios")
