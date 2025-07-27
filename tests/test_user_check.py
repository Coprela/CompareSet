import pytest

pytest.importorskip("requests")
import user_check


def test_load_users(monkeypatch):
    data = {
        "users": [
            {"username": "a", "active": True},
            {"username": "b", "active": False},
        ],
        "admins": ["c"],
    }

    monkeypatch.setattr(user_check, "load_json", lambda name: data)

    users = user_check.load_users()
    assert set(users) == {"a", "c"}
    assert user_check.is_admin("c")
