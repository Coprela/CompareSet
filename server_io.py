"""Server/SharePoint IO helpers.

This module centralizes all remote interactions so the GUI only imports a
single surface for reading manifests, access lists and uploading logs. The
functions are intentionally defensive and fall back to local behaviour when the
server paths are unreachable.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import compareset_env as csenv


def _load_remote_json(source: str) -> Dict[str, Any]:
    """Load JSON from a UNC path or HTTP URL."""

    if not source:
        return {}
    try:
        if source.lower().startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=10) as response:  # nosec B310
                payload = response.read().decode("utf-8")
        else:
            with open(source, "r", encoding="utf-8") as handle:
                payload = handle.read()
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def check_access_allowed(username: str, access_path: str | None = None) -> Tuple[bool, str]:
    """Validate whether ``username`` is present in the server access list."""

    source = access_path or csenv.ACCESS_CONTROL_PATH
    if not source:
        return True, "Access list unavailable; allowing session by default."
    data = _load_remote_json(source)
    allowed = {user.lower() for user in data.get("allowed_users", []) if isinstance(user, str)}
    normalized = username.lower()
    if not allowed:
        return True, "Access list unavailable; allowing session by default."
    if normalized in allowed:
        return True, "User authorized."
    return False, "User is not authorized to use CompareSet."


def fetch_version_manifest(manifest_path: str | None = None) -> Dict[str, Any]:
    """Return the server version manifest if available."""

    return _load_remote_json(manifest_path or csenv.VERSION_MANIFEST_PATH)


def download_binary(url: str, target_path: Path) -> bool:
    """Download a binary file from SharePoint/HTTP into ``target_path``."""

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310
            data = response.read()
        with open(target_path, "wb") as handle:
            handle.write(data)
        return True
    except Exception:
        return False


def persist_server_log(job_id: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Persist a structured log JSON to the configured server logs root."""

    timestamp = datetime.now()
    year = f"{timestamp:%Y}"
    month = f"{timestamp:%m}"
    target_dir = Path(csenv.SERVER_LOGS_ROOT) / year / month
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"LOG_{job_id}.json"
        with open(csenv.make_long_path(str(target_file)), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        return True, str(target_file)
    except Exception as exc:
        return False, str(exc)


def send_released_pdf(job_id: str, source_path: Path) -> Tuple[bool, str]:
    """Upload the released PDF to the server directory hierarchy."""

    timestamp = datetime.now()
    year = f"{timestamp:%Y}"
    month = f"{timestamp:%m}"
    target_dir = Path(csenv.SERVER_RELEASED_ROOT) / year / month
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False, "Unable to create released directory on server."

    target_file = target_dir / f"{job_id}_RESULTADO.pdf"
    try:
        shutil.copy2(csenv.make_long_path(str(source_path)), csenv.make_long_path(str(target_file)))
        return True, str(target_file)
    except Exception as exc:
        return False, str(exc)
