import threading
import requests
from requests.exceptions import RequestException
from json import JSONDecodeError

CURRENT_VERSION = "0.2.1-beta"
VERSION_URL = (
    "https://raw.githubusercontent.com/Coprela/Version-tracker/main/"
    "CompareSet_latest_version.json"
)


def fetch_latest_version(url: str) -> str:
    """Return the latest version string from the given JSON URL."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        latest = data.get("version")
        if isinstance(latest, str):
            return latest
    except (RequestException, JSONDecodeError, ValueError, KeyError):
        pass
    return ""


def check_for_update() -> None:
    """Check GitHub for a new CompareSet version in a background thread."""

    def _task():
        latest = fetch_latest_version(VERSION_URL)
        if latest and latest != CURRENT_VERSION:
            print(f"Nova versão disponível: {latest}")

    threading.Thread(target=_task, daemon=True).start()

