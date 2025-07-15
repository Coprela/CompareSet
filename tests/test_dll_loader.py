import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
import dll_loader

def test_carregar_dll_missing(monkeypatch):
    # Simulate that the DLL file does not exist
    monkeypatch.setattr(dll_loader.os.path, "exists", lambda path: False)
    with pytest.raises(FileNotFoundError):
        dll_loader.carregar_dll()
