"""Testy jednostkowe getShuffledTable."""
import NeoAnki


def test_get_shuffled_table_preserves_elements(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    table = ["a", "b", "c"]
    result = NeoAnki.getShuffledTable(table)
    assert set(result) == {"a", "b", "c"}
    assert len(result) == 3
    assert result is table


def test_get_shuffled_table_empty(monkeypatch):
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    table = []
    result = NeoAnki.getShuffledTable(table)
    assert result == []
