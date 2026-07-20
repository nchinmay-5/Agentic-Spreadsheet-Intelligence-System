"""Create a JSON-safe index of workbook metadata and populated cells."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.workbook.workbook import Workbook


def build_workbook_index(workbook_path: str | Path) -> dict[str, Any]:
    """Read an Excel workbook into a traceable, JSON-safe index.

    Formulas are loaded as their original Excel text. The function does not
    recalculate formula results.
    """
    source_path = Path(workbook_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Workbook not found: {source_path}")
    if source_path.suffix.lower() not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        raise ValueError("Only modern Excel workbook formats are supported.")

    workbook = load_workbook(
        filename=source_path,
        read_only=False,
        data_only=False,
        keep_vba=source_path.suffix.lower() in {".xlsm", ".xltm"},
    )

    sheet_indexes = [_index_sheet(sheet) for sheet in workbook.worksheets]
    formula_cells_count = sum(sheet["formula_cells_count"] for sheet in sheet_indexes)
    value_cells_count = sum(sheet["value_cells_count"] for sheet in sheet_indexes)
    named_ranges = _extract_named_ranges(workbook)

    return {
        "workbook_id": source_path.stem,
        "source_file": source_path.name,
        "sheet_names": workbook.sheetnames,
        "sheets": sheet_indexes,
        "formula_cells_count": formula_cells_count,
        "value_cells_count": value_cells_count,
        "named_ranges_count": len(named_ranges),
        "named_ranges": named_ranges,
    }


def index_workbook_to_file(
    workbook_path: str | Path, output_path: str | Path | None = None
) -> Path:
    """Build an index and write it as formatted JSON, returning its path."""
    source_path = Path(workbook_path)
    index = build_workbook_index(source_path)
    destination = (
        Path(output_path)
        if output_path is not None
        else Path("data") / "indexes" / f"{source_path.stem}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def _index_sheet(sheet: Any) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    formula_cells_count = 0
    value_cells_count = 0

    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue

            is_formula = cell.data_type == "f"
            if is_formula:
                formula_cells_count += 1
            else:
                value_cells_count += 1
            cells.append(_index_cell(cell))

    return {
        "name": sheet.title,
        "used_range": sheet.calculate_dimension(),
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "formula_cells_count": formula_cells_count,
        "value_cells_count": value_cells_count,
        "merged_cells": [str(cell_range) for cell_range in sheet.merged_cells.ranges],
        "cells": cells,
    }


def _index_cell(cell: Cell) -> dict[str, Any]:
    is_formula = cell.data_type == "f"
    return {
        "address": cell.coordinate,
        "value": None if is_formula else _json_value(cell.value),
        "formula": cell.value if is_formula else None,
        "data_type": cell.data_type,
        "comment": cell.comment.text if cell.comment else None,
        "fill": _fill_details(cell),
        "number_format": cell.number_format,
    }


def _fill_details(cell: Cell) -> dict[str, Any] | None:
    fill = cell.fill
    if fill.fill_type is None:
        return None

    return {
        "fill_type": fill.fill_type,
        "foreground_color": _color_details(fill.fgColor),
        "background_color": _color_details(fill.bgColor),
    }


def _color_details(color: Any) -> dict[str, Any]:
    return {
        "type": color.type,
        "rgb": color.rgb,
        "indexed": color.indexed,
        "theme": color.theme,
        "tint": color.tint,
    }


def _extract_named_ranges(workbook: Workbook) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for defined_name in workbook.defined_names.values():
        ranges.append(
            {
                "name": defined_name.name,
                "definition": defined_name.attr_text,
                "local_sheet_id": defined_name.localSheetId,
                "hidden": defined_name.hidden,
            }
        )
    return ranges


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a JSON index from an Excel workbook."
    )
    parser.add_argument("workbook", help="Path to the Excel workbook")
    parser.add_argument(
        "--output",
        help="JSON output path (default: data/indexes/<workbook name>.json)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    written_path = index_workbook_to_file(args.workbook, args.output)
    print(f"Workbook index written to {written_path}")
