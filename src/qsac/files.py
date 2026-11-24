"""Split a definition into reviewable files, and assemble it back.

Layout of reports/<report>/ :
  definition.json            everything not split out; lists the order of sheets and filter groups
  calculated-fields.json     all calculated fields, sorted by dataset and name
  filter-groups/<id>.json    one file per filter group
  sheets/<nn>-<SheetId>/sheet.json            the sheet, with Visuals as an ordered list of IDs
  sheets/<nn>-<SheetId>/visuals/<VisualId>.json  one file per visual
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .definition import visual_id

MANAGED_DIRS = ("filter-groups", "sheets")


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(obj), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split(defn: dict, report_dir: Path) -> list[Path]:
    """Write a normalized definition as files. Replaces managed files, keeps anything else."""
    report_dir.mkdir(parents=True, exist_ok=True)
    for name in MANAGED_DIRS:
        shutil.rmtree(report_dir / name, ignore_errors=True)
    written: list[Path] = []

    top = {k: v for k, v in defn.items() if k not in ("CalculatedFields", "FilterGroups", "Sheets")}

    fields = defn.get("CalculatedFields") or []
    write_json(report_dir / "calculated-fields.json", fields)
    written.append(report_dir / "calculated-fields.json")

    group_ids = []
    for group in defn.get("FilterGroups") or []:
        gid = group["FilterGroupId"]
        group_ids.append(gid)
        path = report_dir / "filter-groups" / f"{gid}.json"
        write_json(path, group)
        written.append(path)
    top["FilterGroups"] = group_ids

    sheet_dirs = []
    for i, sheet in enumerate(defn.get("Sheets") or [], start=1):
        dirname = f"{i:02d}-{sheet['SheetId']}"
        sheet_dirs.append(dirname)
        sheet_copy = dict(sheet)
        visual_ids = []
        for visual in sheet.get("Visuals") or []:
            vid = visual_id(visual)
            visual_ids.append(vid)
            path = report_dir / "sheets" / dirname / "visuals" / f"{vid}.json"
            write_json(path, visual)
            written.append(path)
        if "Visuals" in sheet:
            sheet_copy["Visuals"] = visual_ids
        path = report_dir / "sheets" / dirname / "sheet.json"
        write_json(path, sheet_copy)
        written.append(path)
    top["Sheets"] = sheet_dirs

    write_json(report_dir / "definition.json", top)
    written.append(report_dir / "definition.json")
    return written


def assemble(report_dir: Path) -> dict:
    top = read_json(report_dir / "definition.json")
    defn = {k: v for k, v in top.items() if k not in ("FilterGroups", "Sheets")}

    fields_path = report_dir / "calculated-fields.json"
    fields = read_json(fields_path) if fields_path.is_file() else []
    if fields:
        defn["CalculatedFields"] = fields

    groups = [read_json(report_dir / "filter-groups" / f"{gid}.json") for gid in top.get("FilterGroups") or []]
    if groups:
        defn["FilterGroups"] = groups

    sheets = []
    for dirname in top.get("Sheets") or []:
        sheet = read_json(report_dir / "sheets" / dirname / "sheet.json")
        if "Visuals" in sheet:
            sheet["Visuals"] = [
                read_json(report_dir / "sheets" / dirname / "visuals" / f"{vid}.json") for vid in sheet["Visuals"]
            ]
        sheets.append(sheet)
    if sheets:
        defn["Sheets"] = sheets
    return defn
