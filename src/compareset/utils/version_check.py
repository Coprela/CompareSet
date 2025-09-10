"""Check for updates using files stored on GitHub.

DEPRECATED: retained for the legacy interface. New code should
retrieve version information through other means.
"""

import os
import logging

from .github_json_manager import load_json

logger = logging.getLogger(__name__)
from compareset import __version__ as CURRENT_VERSION

LATEST_VERSION_FILE = os.getenv("LATEST_VERSION_FILE", "CompareSet_latest_version.json")


def fetch_latest_version(filename: str = LATEST_VERSION_FILE) -> str:
    """Return the latest version string from the remote repository."""

    data = load_json(filename)
    latest = data.get("version")
    return latest if isinstance(latest, str) else ""


def check_for_update() -> str:
    """Return the latest version available or an empty string if unavailable."""

    return fetch_latest_version(LATEST_VERSION_FILE)


if __name__ == "__main__":
    latest = check_for_update()
    if latest and latest != CURRENT_VERSION:
        logger.info("New version available: %s", latest)
    elif latest:
        logger.info("Using the latest version.")
    else:
        logger.error("Could not retrieve latest version.")
