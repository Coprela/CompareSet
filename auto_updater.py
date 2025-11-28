"""Auto-update helper using SharePoint-hosted manifest."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import compareset_env as csenv
import server_io


@dataclass
class UpdateStatus:
    local_version: str
    latest_version: Optional[str] = None
    min_supported_version: Optional[str] = None
    download_url: Optional[str] = None
    changelog: Optional[str] = None
    update_available: bool = False
    requires_update: bool = False
    forced_block: bool = False
    message: str | None = None


def _version_tuple(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return (0,)
    try:
        return tuple(int(part) for part in raw.split("."))
    except Exception:
        return (0,)


class AutoUpdater:
    def __init__(self, manifest_path: str | None = None) -> None:
        self.manifest_path = manifest_path or csenv.VERSION_MANIFEST_PATH

    def check_for_updates(self) -> UpdateStatus:
        manifest = server_io.fetch_version_manifest(self.manifest_path)
        status = UpdateStatus(local_version=csenv.APP_VERSION)
        if not manifest:
            return status

        status.latest_version = manifest.get("latest_version")
        status.min_supported_version = manifest.get("min_supported_version")
        status.download_url = manifest.get("download_url")
        status.changelog = manifest.get("changelog")

        local_tuple = _version_tuple(csenv.APP_VERSION)
        latest_tuple = _version_tuple(status.latest_version)
        min_supported_tuple = _version_tuple(status.min_supported_version)

        status.update_available = latest_tuple > local_tuple
        status.requires_update = status.update_available
        status.forced_block = bool(status.min_supported_version) and local_tuple < min_supported_tuple
        if status.forced_block:
            status.message = (
                "A newer version is required to continue."
                if not manifest.get("changelog")
                else str(manifest.get("changelog"))
            )
        elif status.update_available:
            status.message = manifest.get("changelog") or "Nova versão disponível."
        return status

    def download_new_version(self, url: str) -> Optional[Path]:
        target = Path(csenv.LOCAL_UPDATE_DIR) / "CompareSet_new.exe"
        ok = server_io.download_binary(url, target)
        return target if ok else None

    def apply_update(self, downloaded: Path) -> bool:
        """Replace the current executable with the downloaded one."""

        current_exe = Path(csenv.LOCAL_BASE_DIR) / "CompareSet.exe"
        try:
            current_exe.parent.mkdir(parents=True, exist_ok=True)
            if current_exe.exists():
                backup = current_exe.with_suffix(".bak")
                shutil.move(str(current_exe), backup)
            shutil.move(str(downloaded), current_exe)
            return True
        except Exception:
            return False

    def download_and_apply_update(self, download_url: str) -> bool:
        downloaded = self.download_new_version(download_url)
        if not downloaded:
            return False
        return self.apply_update(downloaded)


def perform_startup_update_check() -> UpdateStatus:
    updater = AutoUpdater()
    return updater.check_for_updates()
