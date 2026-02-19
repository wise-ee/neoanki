import random
import os
import json
import subprocess
import sys
import tempfile
from datetime import datetime

import questionary

BACKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neoanki_backup.json")
BACKUP_BACKUP_PATH = BACKUP_PATH + ".bak"

# ANSI: bold + kolor dla tytułów list w backupie
_BOLD_CYAN = "\033[1m\033[36m"
_RESET = "\033[0m"

# Tablica = lista par (słowo, tłumaczenie). Tłumaczenie może być "".
TableRow = tuple[str, str]
Table = list[TableRow]


def _row_to_display(row: TableRow | str) -> str:
    """Akceptuje (word, trans) lub legacy: pojedynczy string (traktowany jako word bez tłumaczenia)."""
    if isinstance(row, str):
        return row
    w, t = row
    return f"{w} ({t})" if t else w


def _table_display(table: Table, max_items: int | None = None) -> str:
    part = table[:max_items] if max_items else table
    return ", ".join(_row_to_display(r) for r in part) + ("..." if max_items and len(table) > max_items else "")


def _table_display_words_only(table: Table, max_items: int | None = None) -> str:
    """Tylko wyrazy (bez tłumaczeń) — do widoku po wymieszaniu."""
    part = table[:max_items] if max_items else table
    return ", ".join(r[0] for r in part) + ("..." if max_items and len(table) > max_items else "")


def _table_display_with_revealed(table: Table, revealed: int) -> str:
    """Numerowana lista: pierwsze `revealed` z tłumaczeniem, reszta tylko word."""
    if not table:
        return "(pusta)"
    width = len(str(len(table)))
    lines = [
        f"  {i + 1:>{width}}. " + (_row_to_display(r) if i < revealed else r[0])
        for i, r in enumerate(table)
    ]
    header = "─" * (width + 4)
    return f"  {header}\n" + "\n".join(lines) + f"\n  {header}"


def _print_backup_list(backup: dict[str, Table]) -> None:
    """Wypisuje listę backupów: tytuł (pogrubiony, kolorowy), poniżej elementy tablicy."""
    for name in sorted(backup.keys()):
        table = backup[name]
        print(f"{_BOLD_CYAN}{name}{_RESET}")
        for word, trans in table:
            print(f"    {word}: {trans if trans else '(brak tłumaczenia)'}")
        print()


def format_translations_display(table: Table) -> str:
    """Zwraca tekst do wyświetlenia: każdy wiersz '  word: trans' lub '  word: (brak tłumaczenia)' w kolejności tablicy."""
    lines = [
        f"  {word}: {trans if trans else '(brak tłumaczenia)'}"
        for word, trans in table
    ]
    return "\n".join(lines)


def _parse_table_cell(cell: str) -> TableRow:
    cell = cell.strip()
    if "|" in cell:
        w, _, t = cell.partition("|")
        return (w.strip(), t.strip())
    return (cell, "")


def _validate_backup(data: object) -> dict[str, list[list[str]]] | None:
    """Akceptuje dict: wartości to listy stringów (stary format) lub listy [word, trans]. Zwraca znormalizowane listy [word, trans]."""
    if not isinstance(data, dict):
        return None
    out: dict[str, list[list[str]]] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, list):
            return None
        rows: list[list[str]] = []
        for x in v:
            if isinstance(x, str):
                rows.append([x, ""])
            elif isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], str):
                rows.append([x[0], x[1]])
            else:
                return None
        out[k] = rows
    return out


def _backup_to_table(rows: list[list[str]]) -> Table:
    return [ (r[0], r[1]) for r in rows ]


def _table_to_backup(table: Table) -> list[list[str]]:
    return [ [w, t] for w, t in table ]


def _validate_table(table: object) -> bool:
    """Sprawdza, czy to Table (lista par (str, str))."""
    if not isinstance(table, list):
        return False
    for row in table:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            return False
        if not isinstance(row[0], str) or not isinstance(row[1], str):
            return False
    return True


def _read_backup_file(path: str) -> dict[str, list[list[str]]] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _validate_backup(data)
    except (json.JSONDecodeError, OSError):
        return None


def load_backup() -> tuple[dict[str, Table], bool]:
    """Wczytuje backup; przy uszkodzeniu głównego pliku próbuje .bak. Naprawia main z .bak jeśli trzeba.
    Zwraca (dane, recovered_from_bak)."""
    main_data = _read_backup_file(BACKUP_PATH)
    if main_data is not None:
        return {k: _backup_to_table(v) for k, v in main_data.items()}, False
    bak_data = _read_backup_file(BACKUP_BACKUP_PATH)
    if bak_data is not None:
        try:
            with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(bak_data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return {k: _backup_to_table(v) for k, v in bak_data.items()}, True
    return {}, False


def save_backup(boards: dict[str, Table]) -> None:
    """Zapisuje backup: najpierw kopia main→.bak, potem zapis do main (przez plik tymczasowy)."""
    if not isinstance(boards, dict):
        raise ValueError("Nieprawidłowa struktura backupu")
    for k, v in boards.items():
        if not isinstance(k, str) or not _validate_table(v):
            raise ValueError("Nieprawidłowa struktura backupu")
    serialized = {k: _table_to_backup(v) for k, v in boards.items()}
    if _validate_backup(serialized) is None:
        raise ValueError("Nieprawidłowa struktura backupu")
    if os.path.exists(BACKUP_PATH):
        try:
            with open(BACKUP_PATH, "r", encoding="utf-8") as f:
                prev = f.read()
            with open(BACKUP_BACKUP_PATH, "w", encoding="utf-8") as f:
                f.write(prev)
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(BACKUP_PATH) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)
        os.replace(tmp, BACKUP_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _confirm_table(table: Table) -> bool:
    """Pokazuje tablicę i pyta o zatwierdzenie. Zwraca True jeśli użytkownik zatwierdza."""
    if not table:
        return False
    clearScreen()
    print("Tablica:\n")
    print(_table_display_with_revealed(table, len(table)))
    print()
    return questionary.select("Zatwierdzić tablicę?", choices=["Tak", "Nie"]).ask() == "Tak"


def getInputTableSingle() -> Table:
    """Dodawanie słów pojedynczo (słowo + Enter). Pusty Enter = koniec. Na końcu zatwierdzenie."""
    table: Table = []
    while True:
        clearScreen()
        if table:
            print(f"Liczba słów: {len(table)}\nDodaj puste słowo by zakończyć")
            print(_table_display_with_revealed(table, len(table)))
            print()
        prompt = "Słowo|tłumaczenie (pusty Enter = koniec): "
        line = input(prompt).strip()
        if not line:
            break
        table.append(_parse_table_cell(line))
    if not table:
        return []
    return table if _confirm_table(table) else []


def getInputTableAllAtOnce() -> Table:
    """Wszystkie elementy naraz (oddzielone przecinkami). Na końcu zatwierdzenie."""
    clearScreen()
    prompt = "Wpisz elementy (element|tłumaczenie oddzielone przecinkiem)\nPrzykład: slowo|tlumaczenie,slowo1|tlumaczenie1,slowo2,slowo3|tlum3\nTłumaczenia są opcjonalne\n"
    raw = input(prompt)
    table = [_parse_table_cell(cell) for cell in raw.split(",") if cell.strip()]
    return table if _confirm_table(table) else []


def getInputTable() -> Table:
    """Pyta o tryb (pojedynczo / wszystko naraz) i zwraca tablicę po zatwierdzeniu."""
    clearScreen()
    mode = questionary.select(
        "Jak dodawać słowa?",
        choices=["Pojedynczo (słowo po słowie)", "Wszystko naraz (oddzielone przecinkami)"],
    ).ask()
    if not mode:
        return []
    if mode == "Pojedynczo (słowo po słowie)":
        return getInputTableSingle()
    return getInputTableAllAtOnce()


def clearScreen():
    os.system("cls" if sys.platform == "win32" else "clear")


def getShuffledTable(table: list):
    clearScreen()
    random.shuffle(table)
    return table


def backup_submenu(
    current_table: Table,
    current_name: str | None,
    used_boards: dict[str, Table],
) -> tuple[Table, str | None, dict[str, Table]]:
    clearScreen()
    label = f"Obecna tablica: {current_name or '(bez nazwy)'}"
    print(label)
    print(_table_display(current_table) if current_table else "(pusta)")
    print()
    choice = questionary.select(
        "Backup:",
        choices=["Wyciągnij tablicę", "Zapisz obecną", "Edytuj tablicę", "Usuń nieużywane", "Wstecz"],
    ).ask()
    if not choice or choice == "Wstecz":
        return current_table, current_name, used_boards

    if choice == "Wyciągnij tablicę":
        backup, _ = load_backup()
        if not backup:
            clearScreen()
            input("Brak zapisanych tablic. Enter...")
            return current_table, current_name, used_boards
        clearScreen()
        _print_backup_list(backup)
        name = questionary.select("Którą tablicę wyciągnąć?", choices=sorted(backup.keys())).ask()
        if name:
            used_boards[name] = backup[name]
            return backup[name], name, used_boards

    if choice == "Zapisz obecną":
        clearScreen()
        print("Obecna tablica:", _table_display(current_table) if current_table else "(pusta)\n")
        base = questionary.text("Nazwa tablicy (opcjonalnie):").ask()
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M")
        name = f"{base} {stamp}".strip() if base else stamp
        if name:
            used_boards[name] = current_table
            backup, _ = load_backup()
            backup[name] = current_table
            save_backup(backup)
            return current_table, name, used_boards

    if choice == "Edytuj tablicę":
        backup, _ = load_backup()
        if not backup:
            clearScreen()
            input("Brak zapisanych tablic. Enter...")
            return current_table, current_name, used_boards
        clearScreen()
        _print_backup_list(backup)
        name = questionary.select("Którą tablicę edytować?", choices=sorted(backup.keys())).ask()
        if not name:
            return current_table, current_name, used_boards
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(", ".join(f"{w}|{t}" if t else w for w, t in backup[name]))
            path = f.name
        try:
            editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
            subprocess.run([editor, path], shell=(sys.platform == "win32"))
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        finally:
            os.unlink(path)
        new_table = [_parse_table_cell(cell) for cell in raw.split(",") if cell.strip()]
        backup[name] = new_table
        save_backup(backup)
        if current_name == name:
            current_table = new_table
        if name in used_boards:
            used_boards[name] = new_table
        clearScreen()
        input(f"Zapisano: {name}. Enter...")

    if choice == "Usuń nieużywane":
        backup, _ = load_backup()
        if not backup:
            clearScreen()
            input("Brak zapisanych tablic. Enter...")
            return current_table, current_name, used_boards
        clearScreen()
        _print_backup_list(backup)
        print("Zaznacz: Spacja. Potwierdź: Enter. Aby wrócić bez usuwania: nie zaznaczaj nic i Enter.")
        print()
        choices = [
            questionary.Choice(title=f"{k} | {_table_display(backup[k], 8)}", value=k)
            for k in sorted(backup.keys())
        ]
        selected = questionary.checkbox("Które tablice usunąć?", choices=choices).ask()
        if selected is None:
            return current_table, current_name, used_boards
        if not selected:
            clearScreen()
            input("Anulowano (nic nie usunięto). Enter...")
            return current_table, current_name, used_boards
        confirm = questionary.select(
            f"Usunąć {len(selected)} tablic z backupu?",
            choices=["Tak, usuń", "Nie, wróć"],
        ).ask()
        if confirm == "Tak, usuń":
            for k in selected:
                del backup[k]
            save_backup(backup)
            clearScreen()
            input(f"Usunięto z backupu: {', '.join(selected)}. Enter...")

    return current_table, current_name, used_boards


def main() -> None:
    clearScreen()
    _, recovered = load_backup()
    if recovered:
        print("Odzyskano backup z pliku .bak (główny plik był uszkodzony).")
        input("Enter...")
        clearScreen()
    start = questionary.select(
        "Co chcesz zrobić?",
        choices=["Wpisz tablicę", "Przejdź do menu"],
    ).ask()
    current_table = getInputTable() if start == "Wpisz tablicę" else []
    current_name: str | None = None
    used_boards: dict[str, Table] = {}

    while True:
        clearScreen()
        choice = questionary.select(
            "Wybierz:",
            choices=["Wymieszaj", "Nowa tablica", "Backup", "Wyjście"],
        ).ask()
        if not choice or choice == "Wyjście":
            return
        if choice == "Wymieszaj":
            while True:
                current_table = getShuffledTable(current_table)
                revealed_count = 0
                while True:
                    clearScreen()
                    print(_table_display_with_revealed(current_table, revealed_count))
                    choices_list = ["Przetłumacz wszystko", "Wymieszaj ponownie", "Usuń element", "Wróć do menu"]
                    if revealed_count < len(current_table):
                        choices_list.insert(0, "Przetłumacz kolejne słowo")
                    again = questionary.select("\nCo dalej?", choices=choices_list).ask()
                    if not again or again == "Wróć do menu":
                        break
                    if again == "Wymieszaj ponownie":
                        break
                    if again == "Przetłumacz kolejne słowo":
                        if revealed_count < len(current_table):
                            revealed_count += 1
                        continue
                    if again == "Przetłumacz wszystko" and current_table:
                        clearScreen()
                        print("Kolejność jak po wymieszaniu:\n")
                        print(format_translations_display(current_table))
                        input("\nEnter...")
                    if again == "Usuń element":
                        if not current_table:
                            input("Tablica pusta. Enter...")
                            continue
                        choices = [
                            questionary.Choice(title=_row_to_display(r), value=i)
                            for i, r in enumerate(current_table)
                        ] + [questionary.Choice(title="Anuluj", value=None)]
                        to_remove = questionary.select("Który element usunąć?", choices=choices).ask()
                        if to_remove is not None:
                            current_table.pop(to_remove)
                            revealed_count = min(revealed_count, len(current_table))
                if again == "Wróć do menu":
                    break
            continue
        if choice == "Nowa tablica":
            current_table = getInputTable()
            current_name = None
            continue
        if choice == "Backup":
            current_table, current_name, used_boards = backup_submenu(
                current_table, current_name, used_boards
            )
            continue


if __name__ == "__main__":
    main()
