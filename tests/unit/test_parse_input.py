"""Testy _parse_table_cell, _confirm_table, getInputTableSingle, getInputTableAllAtOnce, getInputTable."""
import NeoAnki


def test_parse_table_cell_word_only():
    assert NeoAnki._parse_table_cell("abc") == ("abc", "")
    assert NeoAnki._parse_table_cell("  word  ") == ("word", "")


def test_parse_table_cell_word_and_trans():
    assert NeoAnki._parse_table_cell("a|b") == ("a", "b")
    assert NeoAnki._parse_table_cell("słowo | tłumaczenie") == ("słowo", "tłumaczenie")


def test_confirm_table_empty_returns_false(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Nie"})())
    assert NeoAnki._confirm_table([]) is False


def test_confirm_table_accept_returns_true(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Tak"})())
    assert NeoAnki._confirm_table([("a", "A")]) is True


def test_confirm_table_reject_returns_false(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Nie"})())
    assert NeoAnki._confirm_table([("x", "")]) is False


def test_get_input_table_single_builds_and_confirm(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    inputs = ["a|A", "b|B", ""]
    def fake_input(prompt):
        return inputs.pop(0)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Tak"})())
    result = NeoAnki.getInputTableSingle()
    assert result == [("a", "A"), ("b", "B")]


def test_get_input_table_single_empty_returns_empty(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = NeoAnki.getInputTableSingle()
    assert result == []


def test_get_input_table_single_reject_returns_empty(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    lines = ["x|y", ""]
    monkeypatch.setattr("builtins.input", lambda _: lines.pop(0))
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Nie"})())
    result = NeoAnki.getInputTableSingle()
    assert result == []


def test_get_input_table_all_at_once_confirm(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: "p|P, q, r|RR")
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Tak"})())
    result = NeoAnki.getInputTableAllAtOnce()
    assert result == [("p", "P"), ("q", ""), ("r", "RR")]


def test_get_input_table_all_at_once_reject_returns_empty(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: "a|b")
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Nie"})())
    result = NeoAnki.getInputTableAllAtOnce()
    assert result == []


def test_get_input_table_delegates_to_single(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Pojedynczo (słowo po słowie)"})())
    monkeypatch.setattr(NeoAnki, "getInputTableSingle", lambda: [("m", "M")])
    result = NeoAnki.getInputTable()
    assert result == [("m", "M")]


def test_get_input_table_delegates_to_all_at_once(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(NeoAnki.questionary, "select", lambda *a, **k: type("Q", (), {"ask": lambda _: "Wszystko naraz (oddzielone przecinkami)"})())
    monkeypatch.setattr(NeoAnki, "getInputTableAllAtOnce", lambda: [("n", "N")])
    result = NeoAnki.getInputTable()
    assert result == [("n", "N")]
