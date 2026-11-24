"""N rules: names and IDs."""

from __future__ import annotations

import re
from typing import Iterator

from ..definition import iter_controls, iter_filters, iter_parameters, iter_visuals, single
from . import rule


def _display_names(ctx) -> Iterator[tuple[str, str]]:
    """(object, text) for every human-facing name the project controls."""
    for f in ctx.calc_fields:
        yield f["Name"], f["Name"]
    for sheet in ctx.defn.get("Sheets") or []:
        for key in ("Name", "Title"):
            if sheet.get(key):
                yield f"sheet {sheet['SheetId']}", sheet[key]
    for _, _, body in iter_visuals(ctx.defn):
        text = (((body.get("Title") or {}).get("FormatText")) or {}).get("PlainText")
        if text:
            yield f"visual {body['VisualId']}", text
    for _, _, _, body in iter_controls(ctx.defn):
        if body.get("Title"):
            yield body.get("FilterControlId") or body.get("ParameterControlId"), body["Title"]


@rule("N01", "field-kind-prefix", "error", "Every calculated field is '<kind> | <Description>'.")
def n01(ctx):
    kinds = ctx.cfg["naming"]["field_kinds"]
    for f in ctx.calc_fields:
        if ctx.kind_of(f["Name"]) is None or not ctx.description_of(f["Name"]).strip():
            yield f["Name"], f"expected '<kind>{ctx.sep}<Description>' with kind in {', '.join(kinds)}"


@rule("N02", "no-scratch-names", "error", "No scratch words (test, copy, v1, ...) in names.")
def n02(ctx):
    patterns = [re.compile(p, re.IGNORECASE) for p in ctx.cfg["naming"]["scratch_patterns"]]
    for obj, text in _display_names(ctx):
        for p in patterns:
            m = p.search(text)
            if m:
                yield obj, f"scratch word '{m.group(0)}' in '{text}'"
                break


@rule("N03", "name-spacing", "error", "No double, leading or trailing spaces; the separator appears once.")
def n03(ctx):
    sep = ctx.sep
    sep_char = sep.strip()
    for obj, text in _display_names(ctx):
        if text != text.strip() or "  " in text:
            yield obj, f"stray spaces in '{text}'"
        elif sep_char and sep_char in text and (text.count(sep) != 1 or text.count(sep_char) != 1):
            yield obj, f"'{sep_char}' must appear exactly once, as '{sep}'"


@rule("N04", "name-charset", "error", "Field descriptions use only the allowed characters.")
def n04(ctx):
    charset = re.compile(ctx.cfg["naming"]["description_charset"])
    for f in ctx.calc_fields:
        desc = ctx.description_of(f["Name"])
        if desc and not charset.match(desc):
            bad = sorted({c for c in desc if not charset.match(c)})
            yield f["Name"], f"characters not allowed: {' '.join(bad) or '?'}"


@rule("N05", "approved-abbreviations", "warn", "All-caps words in field descriptions are on the approved list.")
def n05(ctx):
    allowed = set(ctx.cfg["naming"]["abbreviations"])
    if not allowed:
        return
    for f in ctx.calc_fields:
        for word in re.findall(r"\b[A-Z]{2,}\b", ctx.description_of(f["Name"])):
            if word not in allowed:
                yield f["Name"], f"'{word}' is not an approved abbreviation"


@rule("N06", "id-pattern", "error", "Sheet, visual, text box, filter and control IDs follow the project's patterns.")
def n06(ctx):
    pats = {k: re.compile(v) for k, v in ctx.cfg["naming"]["ids"].items()}

    def check(kind: str, value: str):
        if kind in pats and not pats[kind].match(value):
            return value, f"{kind.replace('_', ' ')} ID doesn't match {pats[kind].pattern}"
        return None

    found = []
    for sheet in ctx.defn.get("Sheets") or []:
        found.append(check("sheet", sheet["SheetId"]))
        for tb in sheet.get("TextBoxes") or []:
            found.append(check("text_box", tb["SheetTextBoxId"]))
    for _, _, body in iter_visuals(ctx.defn):
        found.append(check("visual", body["VisualId"]))
    seen_groups = set()
    for group, _, body in iter_filters(ctx.defn):
        if group["FilterGroupId"] not in seen_groups:
            seen_groups.add(group["FilterGroupId"])
            found.append(check("filter_group", group["FilterGroupId"]))
        found.append(check("filter", body["FilterId"]))
    for _, kind, _, body in iter_controls(ctx.defn):
        if kind == "filter":
            found.append(check("filter_control", body["FilterControlId"]))
        else:
            found.append(check("parameter_control", body["ParameterControlId"]))
    yield from (f for f in found if f)


@rule("N07", "parameter-name", "error", "Parameter names follow the project's pattern (default p + PascalCase).")
def n07(ctx):
    pat = re.compile(ctx.cfg["naming"]["parameter_pattern"])
    for _, body in iter_parameters(ctx.defn):
        if not pat.match(body["Name"]):
            yield body["Name"], f"doesn't match {pat.pattern}"


@rule("N08", "asset-id-pattern", "error", "Analysis and dashboard IDs in envs/ follow <project>-[<env>-]<report>.", scope="project")
def n08(project):
    prefix = project.config.get("project")
    reserved = project.config["asset_ids"]["reserved"]
    for env_name in project.env_names():
        env = project.env(env_name)
        kind = env.get("kind", env_name)
        for report, ids in (env.get("reports") or {}).items():
            if report in reserved:
                yield f"{env_name}:{report}", f"report name '{report}' is reserved"
            for asset, value in (ids or {}).items():
                if not value or "<" in str(value):
                    continue
                expected = f"{prefix}-{report}" if kind == "prod" else f"{prefix}-{kind}-{report}"
                ok = value == expected or (kind not in ("prod",) and value.startswith(expected + "-"))
                if not prefix:
                    yield f"{env_name}:{report}.{asset}", "set 'project' in qsac.yaml to check asset IDs"
                    return
                if not ok:
                    yield f"{env_name}:{report}.{asset}", f"'{value}' should be '{expected}'" + ("" if kind == "prod" else " or start with it")
