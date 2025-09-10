from __future__ import annotations

"""Helper functions for storing JSON files in a GitHub repository.

DEPRECATED: these utilities are only used by legacy modules and will
be removed in a future release.
"""
import os
import json
import base64
import logging
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

GITHUB_REPO = os.getenv("GITHUB_REPO", "Coprela/CompareSet")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")
GITHUB_PATH_PREFIX = os.getenv("GITHUB_PATH_PREFIX", "config")


def ensure_token() -> None:
    """Load ``GITHUB_TOKEN`` from the environment if not already loaded."""
    global GITHUB_TOKEN
    if not GITHUB_TOKEN:
        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
        if not GITHUB_TOKEN:
            logger.warning("GITHUB_TOKEN not set; GitHub operations may fail")


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
    ensure_token()
    url = _file_url(filename)
    try:
        resp = requests.get(url, headers=_headers(raw=True), timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Failed to load %s: %s", filename, exc)
        return {}


def _get_sha(filename: str) -> str | None:
    ensure_token()
    url = _file_url(filename)
    try:
        resp = requests.get(url, headers=_headers(), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("sha")
    except Exception as exc:
        logger.error("Failed to read SHA for %s: %s", filename, exc)
        return None


def save_json(
    filename: str,
    data: Dict[str, Any],
    commit_message: str = "Atualiza\u00e7\u00e3o via API",
) -> bool:
    """Save *data* as JSON to the GitHub repository."""
    ensure_token()
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
    except Exception as exc:
        logger.error("Failed to save %s: %s", filename, exc)
        return False
