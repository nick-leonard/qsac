"""Helpers for walking a QuickSight analysis definition (API format)."""

from __future__ import annotations

import re
from typing import Any, Iterator

# {Field Name} references inside expressions; ${pName} is a parameter.
FIELD_REF = re.compile(r"(?<!\$)\{([^{}]+)\}")
PARAM_REF = re.compile(r"\$\{([A-Za-z0-9]+)\}")


def single(obj: dict) -> tuple[str, dict]:
    """QuickSight unions ({"BarChartVisual": {...}}) -> (type, body)."""
    if not isinstance(obj, dict) or len(obj) != 1:
        raise ValueError(f"expected a single-key union object, got keys {list(obj)[:5]}")
    key, body = next(iter(obj.items()))
    return key, body


def visual_id(visual: dict) -> str:
    return single(visual)[1]["VisualId"]


def iter_visuals(defn: dict) -> Iterator[tuple[dict, str, dict]]:
    for sheet in defn.get("Sheets") or []:
        for visual in sheet.get("Visuals") or []:
            vtype, body = single(visual)
            yield sheet, vtype, body


def iter_filter_groups(defn: dict) -> Iterator[dict]:
    yield from defn.get("FilterGroups") or []


def iter_filters(defn: dict) -> Iterator[tuple[dict, str, dict]]:
    for group in iter_filter_groups(defn):
        for flt in group.get("Filters") or []:
            ftype, body = single(flt)
            yield group, ftype, body


def iter_controls(defn: dict) -> Iterator[tuple[dict, str, str, dict]]:
    """Yields (sheet, "filter"|"parameter", control type, body)."""
    for sheet in defn.get("Sheets") or []:
        for ctl in sheet.get("FilterControls") or []:
            ctype, body = single(ctl)
            yield sheet, "filter", ctype, body
        for ctl in sheet.get("ParameterControls") or []:
            ctype, body = single(ctl)
            yield sheet, "parameter", ctype, body


def iter_parameters(defn: dict) -> Iterator[tuple[str, dict]]:
    for decl in defn.get("ParameterDeclarations") or []:
        yield single(decl)


def walk(obj: Any, path: tuple = ()) -> Iterator[tuple[tuple, Any]]:
    """Yields (path, value) for every node."""
    yield path, obj
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from walk(value, path + (key,))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from walk(value, path + (i,))


def column_refs(obj: Any) -> Iterator[tuple[str | None, str]]:
    """(DataSetIdentifier, ColumnName) for every ColumnIdentifier-shaped dict."""
    for _, node in walk(obj):
        if isinstance(node, dict) and isinstance(node.get("ColumnName"), str) and "Expression" not in node:
            yield node.get("DataSetIdentifier"), node["ColumnName"]


def expression_refs(expr: str) -> set[str]:
    return set(FIELD_REF.findall(expr or ""))


def expressions(obj: Any) -> Iterator[tuple[tuple, str]]:
    for path, node in walk(obj):
        if path and path[-1] == "Expression" and isinstance(node, str):
            yield path, node


def element_ids(sheet: dict) -> set[str]:
    ids: set[str] = set()
    for visual in sheet.get("Visuals") or []:
        ids.add(visual_id(visual))
    for tb in sheet.get("TextBoxes") or []:
        ids.add(tb["SheetTextBoxId"])
    for img in sheet.get("Images") or []:
        if "SheetImageId" in img:
            ids.add(img["SheetImageId"])
    for kind in ("FilterControls", "ParameterControls"):
        for ctl in sheet.get(kind) or []:
            _, body = single(ctl)
            ids.add(body.get("FilterControlId") or body.get("ParameterControlId"))
    return ids


def layout_elements(sheet: dict) -> Iterator[tuple[str, dict]]:
    """Yields (layout type, element) for free-form and grid layouts."""
    for layout in sheet.get("Layouts") or []:
        config = layout.get("Configuration") or {}
        for ltype in ("FreeFormLayout", "GridLayout"):
            for element in (config.get(ltype) or {}).get("Elements") or []:
                yield ltype, element


def px(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*px\s*", value)
        if m:
            return int(float(m.group(1)))
    return None
