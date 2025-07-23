"""Offline authentication utilities."""

from __future__ import annotations

import base64
import json
import os
import hmac
import hashlib
import secrets
import uuid
from typing import Any, Dict, List

USERS_FILE = os.getenv("USERS_FILE", "users.json")
MASTER_KEY_FILE = os.getenv("MASTER_KEY_FILE", "master.key")


def _load_data() -> Dict[str, Any]:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    else:
        data = {}
    if "users" not in data:
        data["users"] = []
    return data


def _save_data(data: Dict[str, Any]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _pbkdf2(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)


def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = _pbkdf2(password, salt)
    return base64.b64encode(salt + dk).decode()


def check_password(password: str, hashed: str) -> bool:
    data = base64.b64decode(hashed.encode())
    salt, dk = data[:16], data[16:]
    return hmac.compare_digest(_pbkdf2(password, salt), dk)


def get_machine_id() -> str:
    return hex(uuid.getnode())


def preregister_email(email: str, role: str = "user") -> None:
    data = _load_data()
    if not any(u.get("email") == email for u in data["users"]):
        data["users"].append(
            {"email": email, "password": None, "machine": None, "role": role}
        )
        _save_data(data)


def set_password(email: str, password: str) -> bool:
    data = _load_data()
    for u in data["users"]:
        if u.get("email") == email and u.get("password") is None:
            u["password"] = hash_password(password)
            _save_data(data)
            return True
    return False


def reset_password(email: str) -> bool:
    data = _load_data()
    for u in data["users"]:
        if u.get("email") == email:
            u["password"] = None
            _save_data(data)
            return True
    return False


def verify_login(email: str, password: str, machine_id: str | None = None) -> bool:
    data = _load_data()
    for u in data["users"]:
        if u.get("email") != email:
            continue
        stored = u.get("password")
        if not stored or not check_password(password, stored):
            return False
        if machine_id is None:
            machine_id = get_machine_id()
        if u.get("machine") is None:
            u["machine"] = machine_id
            _save_data(data)
            return True
        return u.get("machine") == machine_id
    return False


def is_master(token: str) -> bool:
    hashed = os.getenv("MASTER_TOKEN_HASH")
    if not hashed and os.path.exists(MASTER_KEY_FILE):
        with open(MASTER_KEY_FILE, "r", encoding="utf-8") as f:
            hashed = f.read().strip()
    if not hashed:
        return False
    return check_password(token, hashed)


def log_access(email: str, machine_id: str, success: bool) -> None:
    entry = {
        "time": int(uuid.uuid1().time),
        "email": email,
        "machine": machine_id,
        "success": success,
    }
    log_file = os.getenv("ACCESS_LOG", "access.log")
    try:
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                logs: List[Dict[str, Any]] = json.load(f)
        else:
            logs = []
    except Exception:
        logs = []
    logs.append(entry)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)
