"""Testy jednostkowe load_backup / save_backup."""
import json

import pytest

import NeoAnki


def test_load_backup_missing_returns_empty(backup_path):
    assert not backup_path.exists()
    data, _ = NeoAnki.load_backup()
    assert data == {}


def test_load_backup_empty_file_returns_empty_when_no_bak(backup_path):
    backup_path.write_text("", encoding="utf-8")
    data, recovered = NeoAnki.load_backup()
    assert data == {}
    assert recovered is False


def test_load_backup_valid_content(backup_path):
    # Stary format (listy stringów) i nowy (listy [word, trans]) są akceptowane
    data = {"tab1": [["a", ""], ["b", ""]], "tab2": [["x", ""]]}
    backup_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    loaded, _ = NeoAnki.load_backup()
    assert loaded == {"tab1": [("a", ""), ("b", "")], "tab2": [("x", "")]}


def test_save_backup_persists(backup_path):
    data = {"k": [("s1", "s2")]}
    NeoAnki.save_backup(data)
    assert backup_path.exists()
    loaded = json.loads(backup_path.read_text(encoding="utf-8"))
    assert loaded == {"k": [["s1", "s2"]]}


def test_save_then_load_roundtrip(backup_path):
    data = {"a": [("ą", "aa"), ("b", "")], "b": []}
    NeoAnki.save_backup(data)
    loaded, _ = NeoAnki.load_backup()
    assert loaded == {"a": [("ą", "aa"), ("b", "")], "b": []}


def test_load_backup_recovery_from_bak(backup_path):
    backup_path.write_text("not json", encoding="utf-8")
    bak_path = backup_path.with_suffix(backup_path.suffix + ".bak")
    bak_path.write_text(json.dumps({"x": [["y", ""]]}), encoding="utf-8")
    data, recovered = NeoAnki.load_backup()
    assert data == {"x": [("y", "")]}
    assert recovered is True
    assert json.loads(backup_path.read_text(encoding="utf-8")) == {"x": [["y", ""]]}


def test_load_backup_invalid_structure_main_tries_bak(backup_path):
    """Główny plik ma poprawny JSON ale złą strukturę → uznane za uszkodzone, próba .bak."""
    backup_path.write_text('{"tab": 123}', encoding="utf-8")
    bak_path = backup_path.with_suffix(backup_path.suffix + ".bak")
    bak_path.write_text(json.dumps({"ok": [["a", ""]]}), encoding="utf-8")
    data, recovered = NeoAnki.load_backup()
    assert data == {"ok": [("a", "")]}
    assert recovered is True


def test_save_backup_rejects_invalid_structure(backup_path):
    """save_backup z nieprawidłową strukturą (wartości nie Table: list of (str, str)) rzuca ValueError."""
    with pytest.raises(ValueError, match="Nieprawidłowa struktura"):
        NeoAnki.save_backup({"k": [(1, "x")]})
    with pytest.raises(ValueError, match="Nieprawidłowa struktura"):
        NeoAnki.save_backup("not a dict")
    with pytest.raises(ValueError, match="Nieprawidłowa struktura"):
        NeoAnki.save_backup({"k": [("a", "b", "c")]})


def test_save_backup_creates_bak(backup_path):
    """Po drugim zapisie .bak zawiera stan sprzed ostatniego zapisu."""
    NeoAnki.save_backup({"first": [("a", "")]})
    NeoAnki.save_backup({"second": [("b", "")]})
    bak_path = backup_path.with_suffix(backup_path.suffix + ".bak")
    assert bak_path.exists()
    assert json.loads(bak_path.read_text(encoding="utf-8")) == {"first": [["a", ""]]}
    assert json.loads(backup_path.read_text(encoding="utf-8")) == {"second": [["b", ""]]}
