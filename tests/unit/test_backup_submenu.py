"""Testy jednostkowe backup_submenu z zamockowanym questionary."""
import NeoAnki


def test_backup_submenu_wstecz_returns_unchanged(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(
        NeoAnki.questionary,
        "select",
        lambda *a, **k: type("Q", (), {"ask": lambda _: "Wstecz"})(),
    )
    table, name, used = NeoAnki.backup_submenu(
        [("x", "")], "old", {"old": [("x", "")]}
    )
    assert table == [("x", "")]
    assert name == "old"
    assert used == {"old": [("x", "")]}


def test_backup_submenu_zapisz_obecna_persists(monkeypatch, backup_path):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(NeoAnki, "datetime", type("dt", (), {"now": lambda: type("t", (), {"strftime": lambda s, fmt: "2025-01-01 12-00"})()}))
    call_count = 0
    def fake_select(*a, **k):
        class Q:
            def ask(_, _self=None):
                nonlocal call_count
                call_count += 1
                return "Zapisz obecną" if call_count == 1 else None
        return Q()
    def fake_text(*a, **k):
        class Q:
            def ask(_, _self=None):
                return ""
        return Q()
    monkeypatch.setattr(NeoAnki.questionary, "select", fake_select)
    monkeypatch.setattr(NeoAnki.questionary, "text", fake_text)

    NeoAnki.backup_submenu([("elem1", ""), ("elem2", "")], None, {})

    backup, _ = NeoAnki.load_backup()
    assert len(backup) == 1
    key = next(iter(backup))
    assert "2025-01-01" in key
    assert backup[key] == [("elem1", ""), ("elem2", "")]


def test_backup_submenu_wyciagnij_tablice(monkeypatch, backup_path):
    backup_path.write_text('{"saved": [["a", ""], ["b", ""], ["c", ""]]}', encoding="utf-8")
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    call_count = 0
    def fake_select(*a, **k):
        class Q:
            def ask(_, _self=None):
                nonlocal call_count
                call_count += 1
                return "Wyciągnij tablicę" if call_count == 1 else "saved"
        return Q()
    monkeypatch.setattr(NeoAnki.questionary, "select", fake_select)

    table, name, used = NeoAnki.backup_submenu([], None, {})

    assert table == [("a", ""), ("b", ""), ("c", "")]
    assert name == "saved"
    assert used["saved"] == [("a", ""), ("b", ""), ("c", "")]


def test_backup_submenu_usun_nieuzywane(monkeypatch, backup_path):
    backup_path.write_text(
        '{"keep": [["x", ""]], "drop": [["y", ""]]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: None)
    call_count = 0
    def fake_select(*a, **k):
        class Q:
            def ask(_, _self=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return "Usuń nieużywane"
                if call_count == 2:
                    return "Tak, usuń"
                return None
        return Q()
    def fake_checkbox(*a, **k):
        class Q:
            def ask(_, _self=None):
                return ["drop"]
        return Q()
    monkeypatch.setattr(NeoAnki.questionary, "select", fake_select)
    monkeypatch.setattr(NeoAnki.questionary, "checkbox", fake_checkbox)

    NeoAnki.backup_submenu([("x", "")], "keep", {"keep": [("x", "")]})

    backup, _ = NeoAnki.load_backup()
    assert "keep" in backup
    assert "drop" not in backup


def test_backup_submenu_edytuj_tablice(monkeypatch, backup_path):
    backup_path.write_text('{"tab1": [["a", ""], ["b", ""]]}', encoding="utf-8")
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: None)
    call_count = 0
    def fake_select(*a, **k):
        class Q:
            def ask(_, _self=None):
                nonlocal call_count
                call_count += 1
                return "Edytuj tablicę" if call_count == 1 else "tab1"
        return Q()
    def fake_run(args, **kwargs):
        from pathlib import Path
        Path(args[-1]).write_text("z|zł, y|yy", encoding="utf-8")
    monkeypatch.setattr(NeoAnki.questionary, "select", fake_select)
    monkeypatch.setattr(NeoAnki.subprocess, "run", fake_run)

    table, name, used = NeoAnki.backup_submenu(
        [("a", ""), ("b", "")], "tab1", {"tab1": [("a", ""), ("b", "")]}
    )

    backup, _ = NeoAnki.load_backup()
    assert backup["tab1"] == [("z", "zł"), ("y", "yy")]
    assert table == [("z", "zł"), ("y", "yy")]
    assert used["tab1"] == [("z", "zł"), ("y", "yy")]
