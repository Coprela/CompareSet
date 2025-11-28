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
    requires_update: bool = False
    forced_block: bool = False


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

        local = csenv.APP_VERSION
        latest = status.latest_version or local
        min_supported = status.min_supported_version or local

        status.requires_update = latest > local
        status.forced_block = local < min_supported
        return status

    def download_new_version(self, url: str) -> Optional[Path]:
        target = Path(csenv.LOCAL_UPDATE_DIR) / "CompareSet_new.exe"
        ok = server_io.download_binary(url, target)
        return target if ok else None

    def apply_update(self, downloaded: Path) -> bool:
        """Replace the current executable with the downloaded one."""

        current_exe = Path(csenv.LOCAL_BASE_DIR) / "CompareSet.exe"
        try:
            if current_exe.exists():
                backup = current_exe.with_suffix(".bak")
                shutil.move(str(current_exe), backup)
            shutil.move(str(downloaded), current_exe)
            return True
        except Exception:
            return False


def perform_startup_update_check() -> UpdateStatus:
    updater = AutoUpdater()
    return updater.check_for_updates()
