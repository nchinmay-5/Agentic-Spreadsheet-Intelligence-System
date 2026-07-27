"""Parse A1-style cell and range references from Excel formulas."""

from __future__ import annotations

import re

from openpyxl.utils.cell import column_index_from_string


_REFERENCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"(?:(?P<sheet>'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?"
    r"(?P<start>\$?[A-Za-z]{1,3}\$?\d+)"
    r"(?::(?P<end>\$?[A-Za-z]{1,3}\$?\d+))?"
    r"(?![A-Za-z0-9_.])"
)
_CELL_PATTERN = re.compile(r"^(?P<column>[A-Za-z]{1,3})(?P<row>\d+)$")
_SIMPLE_SHEET_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def parse_references(formula: str, current_sheet: str) -> list[str]:
    """Return normalized A1 references used by an Excel formula.

    Same-sheet references are expanded with ``current_sheet``. Absolute
    markers are removed because they do not change a reference's identity.
    Text literals are ignored.
    """
    return parse_references_with_diagnostics(formula, current_sheet)[0]


def parse_references_with_diagnostics(
    formula: str, current_sheet: str
) -> tuple[list[str], list[str]]:
    """Parse references and return non-fatal diagnostics for unsupported formulas."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return [], ["Formula is not a string beginning with '='."]

    formula_without_strings = _remove_text_literals(formula)
    references: list[str] = []
    diagnostics: list[str] = []
    seen: set[str] = set()

    for match in _REFERENCE_PATTERN.finditer(formula_without_strings):
        start = _normalise_cell(match.group("start"))
        end_text = match.group("end")
        end = _normalise_cell(end_text) if end_text else None
        if start is None or (end_text is not None and end is None):
            continue

        sheet_name = _normalise_sheet_name(match.group("sheet"), current_sheet)
        reference = f"{_format_sheet_name(sheet_name)}!{start}"
        if end is not None:
            reference = f"{reference}:{end}"

        if reference not in seen:
            references.append(reference)
            seen.add(reference)

    if "[" in formula_without_strings and "]" in formula_without_strings:
        diagnostics.append("External workbook references are not supported.")
    if not references and re.search(r"[A-Za-z]+", formula_without_strings[1:]):
        diagnostics.append("No A1-style references were recognized.")
    return references, diagnostics


def _remove_text_literals(formula: str) -> str:
    return re.sub(r'"(?:[^"]|"")*"', lambda match: " " * len(match.group()), formula)


def _normalise_cell(cell: str) -> str | None:
    match = _CELL_PATTERN.fullmatch(cell.replace("$", "").upper())
    if match is None:
        return None

    column = match.group("column")
    row = int(match.group("row"))
    if row < 1 or row > 1_048_576:
        return None

    try:
        if column_index_from_string(column) > 16_384:
            return None
    except ValueError:
        return None

    return f"{column}{row}"


def _normalise_sheet_name(reference_sheet: str | None, current_sheet: str) -> str:
    if reference_sheet is None:
        return current_sheet
    if reference_sheet.startswith("'"):
        return reference_sheet[1:-1].replace("''", "'")
    return reference_sheet


def _format_sheet_name(sheet_name: str) -> str:
    if _SIMPLE_SHEET_NAME.fullmatch(sheet_name):
        return sheet_name
    return "'" + sheet_name.replace("'", "''") + "'"
