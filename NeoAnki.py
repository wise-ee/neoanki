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

# ANSI: bold + color for backup list titles; yellow for "to repeat"
_BOLD_CYAN = "\033[1m\033[36m"
_YELLOW = "\033[1;33m"
_RESET = "\033[0m"

# Table = list of pairs (word, translation). Translation can be "".
TableRow = tuple[str, str]
Table = list[TableRow]


def _row_to_display(row: TableRow | str) -> str:
    """Accepts (word, trans) or legacy: single string (treated as word without translation)."""
    if isinstance(row, str):
        return row
    w, t = row
    return f"{w} ({t})" if t else w


def _table_display(table: Table, max_items: int | None = None) -> str:
    part = table[:max_items] if max_items else table
    return ", ".join(_row_to_display(r) for r in part) + ("..." if max_items and len(table) > max_items else "")


def _table_display_words_only(table: Table, max_items: int | None = None) -> str:
    """Words only (no translations) — for shuffle view."""
    part = table[:max_items] if max_items else table
    return ", ".join(r[0] for r in part) + ("..." if max_items and len(table) > max_items else "")


def _table_display_with_revealed(
    table: Table, revealed: int, to_repeat: set[TableRow] | None = None
) -> str:
    """Numbered list: first `revealed` with translation, rest word only. Rows in to_repeat are yellow."""
    if not table:
        return "(empty)"
    to_repeat = to_repeat or set()
    width = len(str(len(table)))
    lines: list[str] = []
    for i, r in enumerate(table):
        text = _row_to_display(r) if i < revealed else r[0]
        line = f"  {i + 1:>{width}}. {text}"
        if r in to_repeat:
            line = f"  {i + 1:>{width}}. {_YELLOW}{text}{_RESET}"
        lines.append(line)
    header = "─" * (width + 4)
    return f"  {header}\n" + "\n".join(lines) + f"\n  {header}"


def _print_backup_list(backup: dict[str, Table]) -> None:
    """Prints backup list: title (bold, colored), below table elements."""
    for name in sorted(backup.keys()):
        table = backup[name]
        print(f"{_BOLD_CYAN}{name}{_RESET}")
        for word, trans in table:
            print(f"    {word}: {trans if trans else '(no translation)'}")
        print()


def format_translations_display(table: Table) -> str:
    """Returns display text: each row '  word: trans' or '  word: (no translation)' in table order."""
    lines = [
        f"  {word}: {trans if trans else '(no translation)'}"
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
    """Accepts dict: values are lists of strings (old format) or lists [word, trans]. Returns normalized [word, trans] lists."""
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
    """Checks if this is a Table (list of pairs (str, str))."""
    if not isinstance(table, list):
        return False
    for row in table:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            return False
        if not isinstance(row[0], str) or not isinstance(row[1], str):
            return False
    return True


def _parse_board_row_list(v: object) -> list[TableRow] | None:
    """Parses list of [word, trans] or legacy list of str. Returns list of (word, trans) or None."""
    if not isinstance(v, list):
        return None
    out: list[TableRow] = []
    for x in v:
        if isinstance(x, str):
            out.append((x, ""))
        elif isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], str):
            out.append((x[0], x[1]))
        else:
            return None
    return out


def _read_backup_raw(path: str) -> object:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _parse_backup_data(data: object) -> tuple[dict[str, Table], dict[str, list[TableRow]]]:
    """Parses backup file. New format: name -> {table: [...], to_repeat: [...]}. Legacy: name -> [...]. Returns (tables, to_repeat_by_name)."""
    tables: dict[str, Table] = {}
    to_repeat: dict[str, list[TableRow]] = {}
    if not isinstance(data, dict):
        return {}, {}
    # Legacy: root had "tables" and "to_repeat" as separate top-level keys
    if "tables" in data and isinstance(data.get("tables"), dict):
        for k, v in (data["tables"] or {}).items():
            if not isinstance(k, str):
                continue
            rows = _parse_board_row_list(v)
            if rows is not None:
                tables[k] = rows
        for k, v in (data.get("to_repeat") or {}).items():
            if not isinstance(k, str) or not isinstance(v, list):
                continue
            rows = _parse_board_row_list(v)
            if rows is not None:
                to_repeat[k] = rows
        return tables, to_repeat
    # New format: name -> { table: [...], to_repeat: [...] }  or legacy: name -> [...]
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, list):
            rows = _parse_board_row_list(v)
            if rows is not None:
                tables[k] = rows
                # legacy: no to_repeat key for this board
        elif isinstance(v, dict) and "table" in v:
            t_rows = _parse_board_row_list(v["table"])
            if t_rows is not None:
                tables[k] = t_rows
                r_rows = _parse_board_row_list(v.get("to_repeat")) if isinstance(v.get("to_repeat"), list) else []
                to_repeat[k] = r_rows if r_rows is not None else []
        else:
            continue
    return tables, to_repeat


def load_backup() -> tuple[dict[str, Table], dict[str, list[TableRow]], bool]:
    """Loads backup; if main file is corrupted tries .bak. Repairs main from .bak if needed.
    Returns (tables, to_repeat_by_name, recovered_from_bak)."""
    main_raw = _read_backup_raw(BACKUP_PATH)
    if main_raw is not None:
        tables, to_repeat = _parse_backup_data(main_raw)
        if tables or main_raw == {}:
            return tables, to_repeat, False
    bak_raw = _read_backup_raw(BACKUP_BACKUP_PATH)
    if bak_raw is not None:
        tables, to_repeat = _parse_backup_data(bak_raw)
        try:
            with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {name: {"table": _table_to_backup(t), "to_repeat": _table_to_backup(to_repeat.get(name, []))} for name, t in tables.items()},
                    f, ensure_ascii=False, indent=2,
                )
        except OSError:
            pass
        return tables, to_repeat, True
    return {}, {}, False


def save_backup(boards: dict[str, Table], to_repeat_by_name: dict[str, list[TableRow]] | None = None) -> None:
    """Saves backup: each board is one object { table, to_repeat }. If to_repeat_by_name is None, keeps current from file."""
    if not isinstance(boards, dict):
        raise ValueError("Invalid backup structure")
    for k, v in boards.items():
        if not isinstance(k, str) or not _validate_table(v):
            raise ValueError("Invalid backup structure")
    if to_repeat_by_name is None:
        _, to_repeat_by_name, _ = load_backup()
    payload = {
        name: {
            "table": _table_to_backup(boards[name]),
            "to_repeat": _table_to_backup(to_repeat_by_name.get(name, [])),
        }
        for name in boards
    }
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
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, BACKUP_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _confirm_table(table: Table) -> bool:
    """Shows table and asks for confirmation. Returns True if user confirms."""
    if not table:
        return False
    clearScreen()
    print("Table:\n")
    print(_table_display_with_revealed(table, len(table)))
    print()
    return questionary.select("Confirm table?", choices=["Yes", "No"]).ask() == "Yes"


def getInputTableSingle() -> Table:
    """Add words one by one (word + Enter). Empty Enter = finish. Confirmation at the end."""
    table: Table = []
    while True:
        clearScreen()
        if table:
            print(f"Word count: {len(table)}\nAdd empty word to finish")
            print(_table_display_with_revealed(table, len(table)))
            print()
        prompt = "Word|translation (empty Enter = finish): "
        line = input(prompt).strip()
        if not line:
            break
        table.append(_parse_table_cell(line))
    if not table:
        return []
    return table if _confirm_table(table) else []


def getInputTableAllAtOnce() -> Table:
    """All elements at once (comma-separated). Confirmation at the end."""
    clearScreen()
    prompt = "Enter elements (element|translation separated by comma)\nExample: word|translation,word1|translation1,word2,word3|trans3\nTranslations are optional\n"
    raw = input(prompt)
    table = [_parse_table_cell(cell) for cell in raw.split(",") if cell.strip()]
    return table if _confirm_table(table) else []


def getInputTable() -> Table:
    """Asks for mode (one by one / all at once) and returns table after confirmation."""
    clearScreen()
    mode = questionary.select(
        "How to add words?",
        choices=["One by one (word by word)", "All at once (comma-separated)"],
    ).ask()
    if not mode:
        return []
    if mode == "One by one (word by word)":
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
    session_to_repeat: list[TableRow] | None = None,
) -> tuple[Table, str | None, dict[str, Table]]:
    clearScreen()
    label = f"Current table: {current_name or '(unnamed)'}"
    print(label)
    print(_table_display(current_table) if current_table else "(empty)")
    print()
    choice = questionary.select(
        "Backup:",
        choices=["Load table", "Save current", "Edit table", "Delete tables", "Back"],
    ).ask()
    if not choice or choice == "Back":
        return current_table, current_name, used_boards

    if choice == "Load table":
        backup, _, _ = load_backup()
        if not backup:
            clearScreen()
            input("No saved tables. Enter...")
            return current_table, current_name, used_boards
        clearScreen()
        _print_backup_list(backup)
        name = questionary.select("Which table to load?", choices=sorted(backup.keys())).ask()
        if name:
            used_boards[name] = backup[name]
            return backup[name], name, used_boards

    if choice == "Save current":
        backup, to_repeat_dict, _ = load_backup()
        clearScreen()
        _print_backup_list(backup)
        choices_save = ["[new table]"] + sorted(backup.keys())
        target = questionary.select("Save as (new or overwrite selected):", choices=choices_save).ask()
        if not target:
            return current_table, current_name, used_boards
        if target == "[new table]":
            base = questionary.text("Table name (optional):").ask()
            stamp = datetime.now().strftime("%Y-%m-%d %H-%M")
            name = f"{base} {stamp}".strip() if base else stamp
            if name:
                used_boards[name] = current_table
                backup, to_repeat_dict, _ = load_backup()
                backup[name] = current_table
                to_repeat_dict[name] = session_to_repeat if session_to_repeat is not None else []
                save_backup(backup, to_repeat_dict)
                return current_table, name, used_boards
        else:
            name = target
            backup, to_repeat_dict, _ = load_backup()
            backup[name] = current_table
            to_repeat_dict[name] = session_to_repeat if session_to_repeat is not None else []
            save_backup(backup, to_repeat_dict)
            used_boards[name] = current_table
            clearScreen()
            input(f"Overwritten: {name}. Enter...")
            return current_table, name, used_boards

    if choice == "Edit table":
        backup, to_repeat_dict, _ = load_backup()
        if not backup:
            clearScreen()
            input("No saved tables. Enter...")
            return current_table, current_name, used_boards
        clearScreen()
        _print_backup_list(backup)
        name = questionary.select("Which table to edit?", choices=sorted(backup.keys())).ask()
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
        to_repeat_dict[name] = []  # clear to_repeat after edit
        save_backup(backup, to_repeat_dict)
        if current_name == name:
            current_table = new_table
        if name in used_boards:
            used_boards[name] = new_table
        clearScreen()
        input(f"Saved: {name}. Enter...")

    if choice == "Delete tables":
        backup, to_repeat_dict, _ = load_backup()
        if not backup:
            clearScreen()
            input("No saved tables. Enter...")
            return current_table, current_name, used_boards
        clearScreen()
        _print_backup_list(backup)
        print("Select: Space. Confirm: Enter. To go back without deleting: select nothing and Enter.")
        print()
        choices = [
            questionary.Choice(title=f"{k} | {_table_display(backup[k], 8)}", value=k)
            for k in sorted(backup.keys())
        ]
        selected = questionary.checkbox("Which tables to delete?", choices=choices).ask()
        if selected is None:
            return current_table, current_name, used_boards
        if not selected:
            clearScreen()
            input("Cancelled (nothing deleted). Enter...")
            return current_table, current_name, used_boards
        confirm = questionary.select(
            f"Delete {len(selected)} table(s) from backup?",
            choices=["Yes, delete", "No, go back"],
        ).ask()
        if confirm == "Yes, delete":
            for k in selected:
                del backup[k]
                to_repeat_dict.pop(k, None)
            save_backup(backup, to_repeat_dict)
            clearScreen()
            input(f"Deleted from backup: {', '.join(selected)}. Enter...")

    return current_table, current_name, used_boards


def main() -> None:
    clearScreen()
    _, _, recovered = load_backup()
    if recovered:
        print("Recovered backup from .bak file (main file was corrupted).")
        input("Enter...")
        clearScreen()
    start = questionary.select(
        "What do you want to do?",
        choices=["Enter table", "Load table from backup", "Go to menu"],
    ).ask()
    if start == "Enter table":
        current_table = getInputTable()
        current_name = None
    elif start == "Load table from backup":
        backup, _, _ = load_backup()
        if not backup:
            clearScreen()
            input("No saved tables. Enter...")
            current_table = []
            current_name = None
        else:
            clearScreen()
            _print_backup_list(backup)
            name = questionary.select("Which table to load?", choices=sorted(backup.keys())).ask()
            if name:
                current_table = backup[name]
                current_name = name
            else:
                current_table = []
                current_name = None
    else:
        current_table = []
        current_name = None
    used_boards: dict[str, Table] = {}
    if current_name:
        used_boards[current_name] = current_table
    session_to_repeat: list[TableRow] = []

    while True:
        clearScreen()
        menu_choices = ["New table", "Backup", "Exit"]
        if current_table:
            menu_choices.insert(0, "Shuffle")
        choice = questionary.select("Choose:", choices=menu_choices).ask()
        if not choice or choice == "Exit":
            return
        if choice == "Shuffle":
            _, to_repeat_by_name, _ = load_backup()
            to_repeat: set[TableRow] = set(to_repeat_by_name.get(current_name, []))
            while True:
                current_table = getShuffledTable(current_table)
                revealed_count = 0

                def _auto_backup() -> None:
                    if current_name:
                        backup, to_repeat_dict, _ = load_backup()
                        backup[current_name] = current_table
                        to_repeat_dict[current_name] = list(to_repeat)
                        save_backup(backup, to_repeat_dict)
                while True:
                    clearScreen()
                    print(_table_display_with_revealed(current_table, revealed_count, to_repeat))
                    if revealed_count < len(current_table):
                        choices_list = ["Show all translations", "Shuffle again", "Add element", "Remove element", "Back to menu"]
                        choices_list.insert(0, "Show next translation")
                        if revealed_count >= 1:
                            choices_list.insert(1, "Mark last as to repeat")
                        if to_repeat:
                            choices_list.insert(-1, "Show to repeat")
                        choices_list.insert(-1, "Edit to repeat")
                    else:
                        choices_list = ["Shuffle again", "Show all translations", "Add element", "Remove element", "Back to menu"]
                        if len(current_table) >= 1:
                            choices_list.insert(2, "Mark last as to repeat")
                        if to_repeat:
                            choices_list.insert(-1, "Show to repeat")
                        choices_list.insert(-1, "Edit to repeat")
                    again = questionary.select("\nWhat next?", choices=choices_list).ask()
                    if not again or again == "Back to menu":
                        session_to_repeat = list(to_repeat)
                        break
                    if again == "Shuffle again":
                        break
                    if again == "Show next translation":
                        if revealed_count < len(current_table):
                            revealed_count += 1
                        continue
                    if again == "Mark last as to repeat" and revealed_count >= 1:
                        to_repeat.add(current_table[revealed_count - 1])
                        _auto_backup()
                        continue
                    if again == "Edit to repeat" and current_table:
                        clearScreen()
                        print("Select words to repeat (current selection is pre-checked).")
                        print("Select/deselect: Space. Confirm: Enter.")
                        print()
                        choices = [
                            questionary.Choice(title=_row_to_display(r), value=r, checked=(r in to_repeat))
                            for r in current_table
                        ]
                        selected = questionary.checkbox("Which to mark as to repeat?", choices=choices).ask()
                        if selected is not None:
                            to_repeat = set(selected)
                            _auto_backup()
                        continue
                    if again == "Show to repeat" and to_repeat:
                        child_table = [r for r in current_table if r in to_repeat]
                        random.shuffle(child_table)
                        child_revealed = 0
                        while True:
                            clearScreen()
                            print(f"  To repeat ({len(child_table)}):\n")
                            print(_table_display_with_revealed(child_table, child_revealed, set(child_table)))
                            if child_revealed < len(child_table):
                                child_choices = ["Show next translation", "Show all translations", "Shuffle again", "Back"]
                            else:
                                child_choices = ["Shuffle again", "Show all translations", "Back"]
                            child_again = questionary.select("\nWhat next?", choices=child_choices).ask()
                            if not child_again or child_again == "Back":
                                break
                            if child_again == "Shuffle again":
                                random.shuffle(child_table)
                                child_revealed = 0
                                continue
                            if child_again == "Show next translation" and child_revealed < len(child_table):
                                child_revealed += 1
                                continue
                            if child_again == "Show all translations" and child_table:
                                clearScreen()
                                print("To repeat — order as after shuffle:\n")
                                print(format_translations_display(child_table))
                                input("\nEnter...")
                        continue
                    if again == "Show all translations" and current_table:
                        clearScreen()
                        print("Order as after shuffle:\n")
                        print(format_translations_display(current_table))
                        input("\nEnter...")
                    if again == "Add element":
                        new_row = questionary.text("Word|translation (empty = cancel):").ask()
                        if new_row and new_row.strip():
                            current_table.append(_parse_table_cell(new_row.strip()))
                            _auto_backup()
                    if again == "Remove element":
                        if not current_table:
                            input("Table empty. Enter...")
                            continue
                        choices = [
                            questionary.Choice(title=_row_to_display(r), value=i)
                            for i, r in enumerate(current_table)
                        ] + [questionary.Choice(title="Cancel", value=None)]
                        to_remove = questionary.select("Which element to remove?", choices=choices).ask()
                        if to_remove is not None:
                            removed_row = current_table[to_remove]
                            current_table.pop(to_remove)
                            to_repeat.discard(removed_row)
                            revealed_count = min(revealed_count, len(current_table))
                            _auto_backup()
                if again == "Back to menu":
                    break
            continue
        if choice == "New table":
            current_table = getInputTable()
            current_name = None
            continue
        if choice == "Backup":
            current_table, current_name, used_boards = backup_submenu(
                current_table, current_name, used_boards, session_to_repeat
            )
            continue


if __name__ == "__main__":
    main()
