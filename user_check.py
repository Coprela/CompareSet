"""Remote user management for CompareSet.

This module loads and saves the user list stored remotely on GitHub.  The
remote JSON file contains two keys:

``users``
    List of dictionaries with the following structure::

        {
            "username": "jdoe",
            "name": "John Doe",
            "email": "jdoe@example.com",
            "active": true,
            "added": 1712000000.0
        }

    The ``active`` flag indicates whether the user currently has access.  Old
    entries are kept even when deactivated so the history is preserved.

``admins``
    List of usernames with administrative privileges.  Admins always have
    access regardless of the ``active`` state in ``users``.

Only the ``username`` field is used to grant access; the remaining fields are
purely informational.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from github_json_manager import load_json, save_json

ALLOWED_USERS_FILE = os.getenv("ALLOWED_USERS_FILE", "allowed_users.json")


def _load_data() -> Dict[str, Any]:
    """Return the raw user data from GitHub."""
    data = load_json(ALLOWED_USERS_FILE)
    if not data:
        raise RuntimeError("Unable to fetch user list from GitHub")
    if "users" not in data:
        data["users"] = []
    if "admins" not in data:
        data["admins"] = []
    return data


def load_user_records() -> List[Dict[str, Any]]:
    """Return the list of user dictionaries from the repository."""
    data = _load_data()
    users = data.get("users", [])
    if not isinstance(users, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for u in users:
        if not isinstance(u, dict):
            continue
        cleaned.append(
            {
                "username": str(u.get("username", "")),
                "name": str(u.get("name", "")),
                "email": str(u.get("email", "")),
                "active": bool(u.get("active", True)),
                "added": float(u.get("added", 0)),
            }
        )
    return cleaned


def load_users() -> List[str]:
    """Return the list of usernames with access."""
    data = _load_data()
    users = load_user_records()
    allowed = [u["username"] for u in users if u.get("active", True)]
    admins = data.get("admins", [])
    if isinstance(admins, list):
        allowed.extend(str(a) for a in admins)
    return sorted(set(allowed))


def save_users(users: List[str]) -> bool:
    """Save *users* to the GitHub repository. Returns ``True`` on success."""
    existing = _load_data()
    records = load_user_records()
    now = time.time()
    usernames = {u["username"]: u for u in records}
    for name in users:
        if name not in usernames:
            usernames[name] = {
                "username": name,
                "name": "",
                "email": "",
                "active": True,
                "added": now,
            }
        else:
            usernames[name]["active"] = True
    for rec in usernames.values():
        if rec["username"] not in users:
            rec["active"] = False
    data = {
        "users": sorted(usernames.values(), key=lambda r: r.get("added", 0)),
        "admins": existing.get("admins", []),
    }
    return save_json(
        ALLOWED_USERS_FILE, data, "Atualiza\u00e7\u00e3o da lista de usu\u00e1rios"
    )


def is_admin(username: str) -> bool:
    """Return ``True`` if *username* has administrative privileges."""
    data = _load_data()
    admins = data.get("admins", [])
    return isinstance(admins, list) and username in admins


def load_admins() -> List[str]:
    """Return the list of administrator usernames."""
    data = _load_data()
    admins = data.get("admins", [])
    if not isinstance(admins, list):
        return []
    return [str(a) for a in admins]


def save_user_records(
    users: List[Dict[str, Any]], admins: List[str] | None = None
) -> bool:
    """Persist *users* and optionally *admins* to GitHub."""
    data = {
        "users": users,
        "admins": admins if admins is not None else _load_data().get("admins", []),
    }
    return save_json(
        ALLOWED_USERS_FILE, data, "Atualiza\u00e7\u00e3o da lista de usu\u00e1rios"
    )
