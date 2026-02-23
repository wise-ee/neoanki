"""E2E test: running main() with mocked questionary/input, asserting backup state."""
import json

import NeoAnki


def _make_select_mock(seq):
    it = iter(seq)
    def fake_select(*a, **k):
        class P:
            def ask(_, _self=None):
                return next(it, None)
        return P()
    return fake_select


def _make_text_mock(seq):
    it = iter(seq)
    def fake_text(*a, **k):
        class P:
            def ask(_, _self=None):
                return next(it, "")
        return P()
    return fake_text


def test_main_exit_immediately(monkeypatch, backup_path):
    """Go to menu -> Exit -> backup empty."""
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(
        NeoAnki.questionary,
        "select",
        _make_select_mock(["Go to menu", "Exit"]),
    )

    NeoAnki.main()

    tables, _, _ = NeoAnki.load_backup()
    assert tables == {}


def test_main_save_and_exit(monkeypatch, backup_path):
    """Enter table (mocked) -> menu -> Backup -> Save -> Back -> Exit -> backup has 1 entry."""
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: None)
    monkeypatch.setattr(NeoAnki, "getInputTable", lambda: [("s1", ""), ("s2", "")])
    monkeypatch.setattr(NeoAnki, "getShuffledTable", lambda t: t)
    monkeypatch.setattr(
        NeoAnki,
        "datetime",
        type("dt", (), {"now": lambda: type("t", (), {"strftime": lambda s, fmt: "2025-01-01 12-00"})()}),
    )
    select_seq = [
        "Enter table",
        "Shuffle",
        "Back to menu",
        "Backup",
        "Save current",
        "[new table]",
        "Exit",
    ]
    monkeypatch.setattr(NeoAnki.questionary, "select", _make_select_mock(select_seq))
    monkeypatch.setattr(NeoAnki.questionary, "text", _make_text_mock([""]))

    NeoAnki.main()

    backup, _, _ = NeoAnki.load_backup()
    assert len(backup) == 1
    key = next(iter(backup))
    assert backup[key] == [("s1", ""), ("s2", "")]


def test_main_show_translations_displays_manual_only(capsys, monkeypatch, backup_path):
    """Shuffle -> Show all translations: stdout has manual translations and '(no translation)' in table order."""
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: None)
    table_with_trans = [("word1", "trans1"), ("word2", ""), ("x", "iks")]
    monkeypatch.setattr(NeoAnki, "getInputTable", lambda: table_with_trans)
    monkeypatch.setattr(NeoAnki, "getShuffledTable", lambda t: t)
    select_seq = [
        "Enter table",
        "Shuffle",
        "Show all translations",
        "Back to menu",
        "Exit",
    ]
    monkeypatch.setattr(NeoAnki.questionary, "select", _make_select_mock(select_seq))

    NeoAnki.main()

    out = capsys.readouterr().out
    assert "word1: trans1" in out
    assert "word2: (no translation)" in out
    assert "x: iks" in out
    assert "Order as after shuffle" in out


def test_main_to_repeat_auto_backup(monkeypatch, backup_path):
    """Load table -> Shuffle -> Mark last as to repeat -> Back -> Exit: to_repeat is persisted."""
    payload = {
        "tables": {"mytable": [["word1", "t1"], ["word2", "t2"]]},
        "to_repeat": {},
    }
    backup_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: None)
    monkeypatch.setattr(NeoAnki, "getShuffledTable", lambda t: t)
    select_seq = [
        "Load table from backup",
        "mytable",
        "Shuffle",
        "Show next translation",
        "Mark last as to repeat",
        "Back to menu",
        "Exit",
    ]
    monkeypatch.setattr(NeoAnki.questionary, "select", _make_select_mock(select_seq))

    NeoAnki.main()

    tables, to_repeat, _ = NeoAnki.load_backup()
    assert "mytable" in to_repeat
    assert to_repeat["mytable"] == [("word1", "t1")]