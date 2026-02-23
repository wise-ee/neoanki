"""Unit tests for load_backup / save_backup."""
import json

import pytest

import NeoAnki


def test_load_backup_missing_returns_empty(backup_path):
    assert not backup_path.exists()
    data, _, _ = NeoAnki.load_backup()
    assert data == {}


def test_load_backup_empty_file_returns_empty_when_no_bak(backup_path):
    backup_path.write_text("", encoding="utf-8")
    data, _, recovered = NeoAnki.load_backup()
    assert data == {}
    assert recovered is False


def test_load_backup_valid_content(backup_path):
    # Legacy format (listy [word, trans]) jest akceptowany
    data = {"tab1": [["a", ""], ["b", ""]], "tab2": [["x", ""]]}
    backup_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    loaded, _, _ = NeoAnki.load_backup()
    assert loaded == {"tab1": [("a", ""), ("b", "")], "tab2": [("x", "")]}


def test_save_backup_persists(backup_path):
    data = {"k": [("s1", "s2")]}
    NeoAnki.save_backup(data)
    assert backup_path.exists()
    loaded = json.loads(backup_path.read_text(encoding="utf-8"))
    assert loaded["k"] == {"table": [["s1", "s2"]], "to_repeat": []}


def test_save_then_load_roundtrip(backup_path):
    data = {"a": [("ą", "aa"), ("b", "")], "b": []}
    NeoAnki.save_backup(data)
    loaded, _, _ = NeoAnki.load_backup()
    assert loaded == {"a": [("ą", "aa"), ("b", "")], "b": []}


def test_load_backup_recovery_from_bak(backup_path):
    backup_path.write_text("not json", encoding="utf-8")
    bak_path = backup_path.with_suffix(backup_path.suffix + ".bak")
    bak_path.write_text(json.dumps({"x": [["y", ""]]}), encoding="utf-8")
    data, _, recovered = NeoAnki.load_backup()
    assert data == {"x": [("y", "")]}
    assert recovered is True
    main_data = json.loads(backup_path.read_text(encoding="utf-8"))
    assert main_data["x"] == {"table": [["y", ""]], "to_repeat": []}


def test_load_backup_invalid_structure_main_tries_bak(backup_path):
    """Main file has valid JSON but wrong structure → treated as corrupted, tries .bak."""
    backup_path.write_text('{"tab": 123}', encoding="utf-8")
    bak_path = backup_path.with_suffix(backup_path.suffix + ".bak")
    bak_path.write_text(json.dumps({"ok": [["a", ""]]}), encoding="utf-8")
    data, _, recovered = NeoAnki.load_backup()
    assert data == {"ok": [("a", "")]}
    assert recovered is True


def test_save_backup_rejects_invalid_structure(backup_path):
    """save_backup with invalid structure (values not Table: list of (str, str)) raises ValueError."""
    with pytest.raises(ValueError, match="Invalid backup structure"):
        NeoAnki.save_backup({"k": [(1, "x")]})
    with pytest.raises(ValueError, match="Invalid backup structure"):
        NeoAnki.save_backup("not a dict")
    with pytest.raises(ValueError, match="Invalid backup structure"):
        NeoAnki.save_backup({"k": [("a", "b", "c")]})


def test_save_backup_creates_bak(backup_path):
    """After second save .bak contains state before last save."""
    NeoAnki.save_backup({"first": [("a", "")]})
    NeoAnki.save_backup({"second": [("b", "")]})
    bak_path = backup_path.with_suffix(backup_path.suffix + ".bak")
    assert bak_path.exists()
    bak_data = json.loads(bak_path.read_text(encoding="utf-8"))
    assert bak_data["first"] == {"table": [["a", ""]], "to_repeat": []}
    main_data = json.loads(backup_path.read_text(encoding="utf-8"))
    assert main_data["second"] == {"table": [["b", ""]], "to_repeat": []}


def test_save_backup_with_to_repeat_persists(backup_path):
    """save_backup(boards, to_repeat_by_name) persists both; load_backup returns to_repeat."""
    boards = {"t1": [("a", "A"), ("b", "B")]}
    to_repeat = {"t1": [("a", "A")]}
    NeoAnki.save_backup(boards, to_repeat)
    loaded_tables, loaded_to_repeat, _ = NeoAnki.load_backup()
    assert loaded_tables == {"t1": [("a", "A"), ("b", "B")]}
    assert loaded_to_repeat == {"t1": [("a", "A")]}


def test_load_backup_new_format_with_to_repeat(backup_path):
    """Per-board format { table, to_repeat } loads correctly."""
    payload = {
        "board1": {"table": [["x", "X"], ["y", ""]], "to_repeat": [["x", "X"]]},
    }
    backup_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tables, to_repeat, _ = NeoAnki.load_backup()
    assert tables == {"board1": [("x", "X"), ("y", "")]}
    assert to_repeat == {"board1": [("x", "X")]}


def test_load_backup_legacy_returns_empty_to_repeat(backup_path):
    """Legacy format (no 'tables' key) returns empty to_repeat."""
    legacy = {"only": [["a", ""], ["b", ""]]}
    backup_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    tables, to_repeat, _ = NeoAnki.load_backup()
    assert tables == {"only": [("a", ""), ("b", "")]}
    assert to_repeat == {}


def test_save_backup_preserves_to_repeat_when_none_passed(backup_path):
    """save_backup(boards) without to_repeat keeps existing to_repeat from file."""
    NeoAnki.save_backup({"k": [("a", "")]}, {"k": [("a", "")]})
    NeoAnki.save_backup({"k": [("a", ""), ("b", "")]})  # only update tables
    _, to_repeat, _ = NeoAnki.load_backup()
    assert to_repeat.get("k") == [("a", "")]


def test_parse_backup_data_invalid_to_repeat_returns_empty(backup_path):
    """Per-board format with invalid to_repeat (e.g. wrong type) yields empty to_repeat for that board."""
    payload = {"b": {"table": [["x", ""]], "to_repeat": "not a list"}}
    backup_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tables, to_repeat, _ = NeoAnki.load_backup()
    assert tables == {"b": [("x", "")]}
    assert to_repeat.get("b") == []
