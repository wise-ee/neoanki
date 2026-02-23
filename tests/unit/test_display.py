"""Tests for _table_display, _table_display_words_only and _table_display_with_revealed."""
import NeoAnki


def test_table_display_includes_translations():
    table = [("a", "A"), ("b", "")]
    out = NeoAnki._table_display(table)
    assert "a (A)" in out
    assert "b" in out


def test_table_display_max_items():
    table = [("x", ""), ("y", ""), ("z", "")]
    out = NeoAnki._table_display(table, max_items=2)
    assert "x" in out and "y" in out
    assert "..." in out
    assert "z" not in out


def test_table_display_words_only_only_words():
    table = [("a", "A"), ("b", "bb"), ("c", "")]
    out = NeoAnki._table_display_words_only(table)
    assert out == "a, b, c"
    assert "A" not in out and "bb" not in out


def test_table_display_words_only_empty():
    assert NeoAnki._table_display_words_only([]) == ""


def test_table_display_words_only_max_items():
    table = [("a", ""), ("b", ""), ("c", "")]
    out = NeoAnki._table_display_words_only(table, max_items=2)
    assert "a, b" in out
    assert "..." in out
    assert "c" not in out


def test_table_display_with_revealed_empty():
    assert NeoAnki._table_display_with_revealed([], 0) == "(empty)"


def test_table_display_with_revealed_none_revealed():
    table = [("a", "A"), ("b", "B")]
    out = NeoAnki._table_display_with_revealed(table, 0)
    assert "1." in out and "2." in out
    assert "a" in out and "b" in out
    assert "A" not in out and "B" not in out
    assert "─" in out


def test_table_display_with_revealed_partial():
    table = [("a", "A"), ("b", "B"), ("c", "C")]
    out = NeoAnki._table_display_with_revealed(table, 2)
    assert "a (A)" in out or "A" in out
    assert "b (B)" in out or "B" in out
    assert "c" in out and "C" not in out


def test_table_display_with_revealed_all():
    table = [("x", "xx"), ("y", "yy")]
    out = NeoAnki._table_display_with_revealed(table, 2)
    assert "x (xx)" in out or "xx" in out
    assert "y (yy)" in out or "yy" in out


def test_table_display_with_revealed_numbering_width():
    table = [("a", "")] * 12
    out = NeoAnki._table_display_with_revealed(table, 0)
    assert " 1." in out
    assert "12." in out


def test_table_display_with_revealed_to_repeat_wraps_in_yellow():
    """Rows in to_repeat are wrapped with ANSI yellow (\\033[1;33m)."""
    table = [("a", "A"), ("b", "B"), ("c", "C")]
    to_repeat = {("b", "B")}
    out = NeoAnki._table_display_with_revealed(table, 3, to_repeat)
    assert "\033[1;33m" in out
    assert "b (B)" in out or "B" in out
    assert "\033[0m" in out
