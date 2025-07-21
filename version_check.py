import os
from json import JSONDecodeError

import requests
from requests.exceptions import RequestException


CURRENT_VERSION = "0.2.1-beta"

# URL with the latest version JSON. Can be overridden by the VERSION_URL
# environment variable.
VERSION_URL = os.getenv(
    "VERSION_URL",
    "https://raw.githubusercontent.com/Coprela/Version-tracker/main/CompareSet_latest_version.json",
)


def fetch_latest_version(url: str) -> str:
    """Return the latest version string from *url* or an empty string."""

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except (RequestException, JSONDecodeError):
        return ""

    latest = data.get("version")
    return latest if isinstance(latest, str) else ""


def check_for_update() -> str:
    """Return the latest version available or an empty string if unavailable."""

    return fetch_latest_version(VERSION_URL)


if __name__ == "__main__":
    latest = check_for_update()
    if latest and latest != CURRENT_VERSION:
        print(f"New version available: {latest}")
    elif latest:
        print("Using the latest version.")
    else:
        print("Could not retrieve latest version.")
