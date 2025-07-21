import requests
from requests.exceptions import RequestException
from json import JSONDecodeError

CURRENT_VERSION = "0.2.1-beta"
VERSION_URL = "https://raw.githubusercontent.com/Coprela/Version-tracker/main/CompareSet_latest_version.json"


def check_for_update() -> str:
    """Return the latest version string if an update is available."""
    try:
        response = requests.get(VERSION_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        latest_version = data.get("version")
        if isinstance(latest_version, str) and latest_version != CURRENT_VERSION:
            return latest_version
    except (RequestException, JSONDecodeError, ValueError, KeyError):
        # fail silently on connection or parsing errors
        pass
    return ""

