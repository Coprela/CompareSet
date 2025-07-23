import types

import pytest

pytest.importorskip("requests")
import version_check


def test_fetch_latest(monkeypatch):
    def fake_load(name):
        return {"version": "1.2.3"}

    monkeypatch.setattr(version_check, "load_json", fake_load)
    assert version_check.fetch_latest_version("dummy.json") == "1.2.3"
