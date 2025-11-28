"""Access validation against server control list."""
from __future__ import annotations

import getpass
from typing import Tuple

import server_io


def current_username() -> str:
    return getpass.getuser()


def ensure_user_access(access_path: str | None = None) -> Tuple[bool, str]:
    username = current_username()
    return server_io.check_access_allowed(username, access_path)
