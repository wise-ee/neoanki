"""Pytest fixtures: izolowany backup path na czas testów."""
import pytest


@pytest.fixture(autouse=True)
def backup_path(tmp_path, monkeypatch):
    path = tmp_path / "neoanki_backup.json"
    import NeoAnki
    monkeypatch.setattr(NeoAnki, "BACKUP_PATH", str(path))
    monkeypatch.setattr(NeoAnki, "BACKUP_BACKUP_PATH", str(path) + ".bak")
    return path
