"""Test e2e: uruchomienie main() z zamockowanym questionary/input, asercja stanu backupu."""
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
    """Przejdź do menu -> Wyjście -> backup pusty."""
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr(
        NeoAnki.questionary,
        "select",
        _make_select_mock(["Przejdź do menu", "Wyjście"]),
    )

    NeoAnki.main()

    assert NeoAnki.load_backup()[0] == {}


def test_main_save_and_exit(monkeypatch, backup_path):
    """Wpisz tablicę (mocked) -> menu -> Backup -> Zapisz -> Wstecz -> Wyjście -> backup ma 1 wpis."""
    monkeypatch.setattr(NeoAnki, "clearScreen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: None)
    monkeypatch.setattr(NeoAnki, "getInputTable", lambda: [("s1", ""), ("s2", "")])
    monkeypatch.setattr(
        NeoAnki,
        "datetime",
        type("dt", (), {"now": lambda: type("t", (), {"strftime": lambda s, fmt: "2025-01-01 12-00"})()}),
    )
    select_seq = [
        "Wpisz tablicę",
        "Wymieszaj",
        "Wróć do menu",
        "Backup",
        "Zapisz obecną",
        "Wyjście",
    ]
    monkeypatch.setattr(NeoAnki.questionary, "select", _make_select_mock(select_seq))
    monkeypatch.setattr(NeoAnki.questionary, "text", _make_text_mock([""]))

    NeoAnki.main()

    backup, _ = NeoAnki.load_backup()
    assert len(backup) == 1
    key = next(iter(backup))
    assert backup[key] == [("s1", ""), ("s2", "")]