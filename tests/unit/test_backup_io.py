"""Testy jednostkowe load_backup / save_backup."""
import json

import pytest

import NeoAnki


def test_load_backup_missing_returns_empty(backup_path):
    assert not backup_path.exists()
    assert NeoAnki.load_backup() == {}


def test_load_backup_empty_file_raises(backup_path):
    backup_path.write_text("", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        NeoAnki.load_backup()


def test_load_backup_valid_content(backup_path):
    data = {"tab1": ["a", "b"], "tab2": ["x"]}
    backup_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert NeoAnki.load_backup() == data


def test_save_backup_persists(backup_path):
    data = {"k": ["s1", "s2"]}
    NeoAnki.save_backup(data)
    assert backup_path.exists()
    loaded = json.loads(backup_path.read_text(encoding="utf-8"))
    assert loaded == data


def test_save_then_load_roundtrip(backup_path):
    data = {"a": ["ą", "b"], "b": []}
    NeoAnki.save_backup(data)
    assert NeoAnki.load_backup() == data
