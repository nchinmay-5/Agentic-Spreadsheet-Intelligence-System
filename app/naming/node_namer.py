"""Rule-based node names with a transparent persistent cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class NodeNameCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def get(self, workbook_id: str, node_id: str) -> str | None:
        return self.data.get(workbook_id, {}).get(node_id)

    def set(self, workbook_id: str, node_id: str, name: str) -> None:
        self.data.setdefault(workbook_id, {})[node_id] = name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_node_name(workbook_index: dict[str, Any], node_id: str, cache: NodeNameCache | None = None) -> dict[str, str]:
    workbook_id = workbook_index["workbook_id"]
    cached = cache.get(workbook_id, node_id) if cache else None
    if cached:
        return {"name": cached, "method": "cache"}
    sheet, address = node_id.rsplit("!", 1)
    sheet = sheet.strip("'")
    cell = _find_cell(workbook_index, sheet, address)
    name = _nearby_label(workbook_index, sheet, address) or (str(cell["value"]) if cell and isinstance(cell.get("value"), str) else f"{sheet} {address}")
    if cache:
        cache.set(workbook_id, node_id, name)
    return {"name": name, "method": "nearby_label"}


def _find_cell(index: dict[str, Any], sheet_name: str, address: str) -> dict[str, Any] | None:
    for sheet in index["sheets"]:
        if sheet["name"] == sheet_name:
            return next((cell for cell in sheet["cells"] if cell["address"] == address), None)
    return None


def _nearby_label(index: dict[str, Any], sheet_name: str, address: str) -> str | None:
    cell = _find_cell(index, sheet_name, address)
    if not cell:
        return None
    from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
    col, row = coordinate_from_string(address)
    column = column_index_from_string(col)
    candidates = []
    for sheet in index["sheets"]:
        if sheet["name"] != sheet_name:
            continue
        for item in sheet["cells"]:
            if isinstance(item.get("value"), str):
                item_col, item_row = coordinate_from_string(item["address"])
                distance = abs(column_index_from_string(item_col) - column) + abs(item_row - row)
                if distance <= 3:
                    candidates.append((distance, item["value"]))
    return min(candidates, default=(None, None))[1]
