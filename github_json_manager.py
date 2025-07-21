from __future__ import annotations
import os
import json
import base64
from typing import Any, Dict

from cryptography.fernet import Fernet

import requests

GITHUB_REPO = os.getenv("GITHUB_REPO", "Coprela/CompareSet")
# Optional encrypted token for convenience. The symmetric key and encrypted
# value are embedded in code and decrypted at runtime. This merely obfuscates
# the token, so the ``GITHUB_TOKEN`` environment variable takes precedence
# when set.
FERNET_KEY = b""
ENCRYPTED_TOKEN = b""


def _decrypt_token() -> str:
    if not (FERNET_KEY and ENCRYPTED_TOKEN):
        return ""
    try:
        return Fernet(FERNET_KEY).decrypt(ENCRYPTED_TOKEN).decode()
    except Exception:
        return ""


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or _decrypt_token()
GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")
GITHUB_PATH_PREFIX = os.getenv("GITHUB_PATH_PREFIX", "config")


def _headers(raw: bool = False) -> Dict[str, str]:
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if raw:
        headers["Accept"] = "application/vnd.github.v3.raw"
    return headers


def _file_url(filename: str) -> str:
    return f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{GITHUB_PATH_PREFIX}/{filename}"


def load_json(filename: str) -> Dict[str, Any]:
    """Load JSON file *filename* from the GitHub repository."""
    url = _file_url(filename)
    try:
        resp = requests.get(url, headers=_headers(raw=True), timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _get_sha(filename: str) -> str | None:
    url = _file_url(filename)
    try:
        resp = requests.get(url, headers=_headers(), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("sha")
    except Exception:
        return None


def save_json(filename: str, data: Dict[str, Any], commit_message: str = "Atualiza\u00e7\u00e3o via API") -> bool:
    """Save *data* as JSON to the GitHub repository."""
    url = _file_url(filename)
    sha = _get_sha(filename)
    content = json.dumps(data, indent=2).encode("utf-8")
    b64_content = base64.b64encode(content).decode("ascii")
    payload = {
        "message": commit_message,
        "content": b64_content,
    }
    if sha:
        payload["sha"] = sha
    try:
        resp = requests.put(url, headers=_headers(), json=payload, timeout=5)
        resp.raise_for_status()
        return True
    except Exception:
        return False
