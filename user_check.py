"""Remote user management for CompareSet."""

from __future__ import annotations

import os
import json
import base64
from typing import List

import requests
from requests import Response

USER_LIST_URL = os.getenv(
    "USER_LIST_URL",
    "https://raw.githubusercontent.com/Coprela/Version-tracker/main/allowed_users.json",
)
USER_LIST_WRITE_URL = os.getenv(
    "USER_LIST_WRITE_URL",
    "https://api.github.com/repos/Coprela/Version-tracker/contents/allowed_users.json",
)
USER_LIST_TOKEN = os.getenv(
    "USER_LIST_TOKEN", "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"
)


def load_users() -> List[str]:
    """Return the list of allowed users from the remote repository."""
    try:
        resp: Response = requests.get(USER_LIST_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        users = data.get("users", [])
        if isinstance(users, list):
            return [str(u) for u in users]
    except Exception:
        pass
    return []


def _get_file_sha() -> str | None:
    headers = {"Authorization": f"Bearer {USER_LIST_TOKEN}"}
    try:
        resp: Response = requests.get(USER_LIST_WRITE_URL, headers=headers, timeout=5)
        resp.raise_for_status()
        info = resp.json()
        return info.get("sha")
    except Exception:
        return None


def save_users(users: List[str]) -> bool:
    """Save *users* to the GitHub repository. Returns ``True`` on success."""
    sha = _get_file_sha()
    if not sha:
        return False

    content_bytes = json.dumps({"users": sorted(set(users))}, indent=2).encode("utf-8")
    b64_content = base64.b64encode(content_bytes).decode("ascii")
    payload = {
        "message": "Atualização da lista de usuários",
        "content": b64_content,
        "sha": sha,
    }
    headers = {"Authorization": f"Bearer {USER_LIST_TOKEN}"}
    try:
        resp: Response = requests.put(
            USER_LIST_WRITE_URL, headers=headers, json=payload, timeout=5
        )
        resp.raise_for_status()
    except Exception:
        return False
    return True
