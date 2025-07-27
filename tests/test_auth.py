import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load_auth(path: Path):
    import importlib
    import os

    os.environ["USERS_FILE"] = str(path)
    return importlib.import_module("compareset.auth")


def test_first_access_flow(tmp_path):
    users_file = tmp_path / "users.json"
    auth = load_auth(users_file)

    auth.preregister_email("user@example.com")
    assert users_file.exists()

    # user must set password first
    assert not auth.verify_login("user@example.com", "pass", "machine1")

    assert auth.set_password("user@example.com", "pass")

    assert auth.verify_login("user@example.com", "pass", "machine1")
    # subsequent login same machine
    assert auth.verify_login("user@example.com", "pass", "machine1")
    # different machine should fail
    assert not auth.verify_login("user@example.com", "pass", "machine2")


def test_reset_password(tmp_path):
    users_file = tmp_path / "users.json"
    auth = load_auth(users_file)

    auth.preregister_email("u@example.com")
    auth.set_password("u@example.com", "pass")
    assert auth.verify_login("u@example.com", "pass", "m1")

    auth.reset_password("u@example.com")
    assert not auth.verify_login("u@example.com", "pass", "m1")
