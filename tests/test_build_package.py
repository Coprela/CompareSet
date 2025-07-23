import pytest

pytest.importorskip("PyInstaller")
import build_package


def test_obfuscate_fallback(monkeypatch, tmp_path):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        # simulate successful command
        return

    monkeypatch.setattr(build_package.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)

    result = build_package._obfuscate("run_app.py")
    assert result == "run_app.py"
    assert calls
