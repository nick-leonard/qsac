"""R rules: filters and controls."""

from __future__ import annotations

import json
import re

from ..definition import iter_controls, iter_filter_groups, iter_filters, walk
from . import rule


def _signature(ftype: str, body: dict) -> str:
    core = {k: v for k, v in body.items() if k not in ("FilterId", "DefaultFilterControlConfiguration")}
    return ftype + json.dumps(core, sort_keys=True)


def _category_values(body: dict) -> list:
    values: list = []
    for conf in (body.get("Configuration") or {}).values():
        if isinstance(conf, dict):
            values += conf.get("CategoryValues") or []
            if conf.get("CategoryValue") is not None:
                values.append(conf["CategoryValue"])
    return values


@rule("R01", "filter-duplicate", "error", "One rule, one filter group: no two filters with the same column and condition.")
def r01(ctx):
    first: dict[str, str] = {}
    for group, ftype, body in iter_filters(ctx.defn):
        sig = _signature(ftype, body)
        if sig in first and first[sig] != group["FilterGroupId"]:
            yield group["FilterGroupId"], f"same filter as {first[sig]}; widen that group's scope instead"
        else:
            first.setdefault(sig, group["FilterGroupId"])


@rule("R02", "filter-hardcoded-list", "error", "No hard-coded value lists in category filters (approved ones go in lint-exceptions.yaml).")
def r02(ctx):
    threshold = ctx.cfg["lint"]["hardcoded_list_threshold"]
    for group, ftype, body in iter_filters(ctx.defn):
        values = _category_values(body) if ftype == "CategoryFilter" else []
        if len(values) >= threshold:
            yield group["FilterGroupId"], f"{len(values)} hard-coded values on {body['Column']['ColumnName']}"


@rule("R03", "filter-no-entity-literal", "error", "No configured entity names as filter values.")
def r03(ctx):
    literals = [s.lower() for s in ctx.cfg["lint"]["entity_literals"]]
    if not literals:
        return
    for group, ftype, body in iter_filters(ctx.defn):
        text = " ".join(str(v) for v in _category_values(body)).lower()
        hits = [lit for lit in literals if lit in text]
        if hits:
            yield group["FilterGroupId"], f"filters on {', '.join(hits)}"


@rule("R04", "filter-no-fixed-dates", "error", "No fixed date ranges; use period flags, rolling dates or parameters.")
def r04(ctx):
    for group, ftype, body in iter_filters(ctx.defn):
        fixed = False
        if ftype == "TimeRangeFilter":
            fixed = any((body.get(k) or {}).get("StaticValue") is not None for k in ("RangeMinimumValue", "RangeMaximumValue"))
        elif ftype == "TimeEqualityFilter":
            fixed = body.get("Value") is not None
        if fixed:
            yield group["FilterGroupId"], f"fixed date on {body['Column']['ColumnName']}"


@rule("R05", "filter-no-id-column", "error", "No filters on ID columns, which can carry request or member identifiers.")
def r05(ctx):
    pat = re.compile(ctx.cfg["lint"]["id_column_pattern"])
    for group, _, body in iter_filters(ctx.defn):
        col = body["Column"]["ColumnName"]
        if pat.search(col):
            yield group["FilterGroupId"], f"filters on ID column {col}"


@rule("R06", "filter-noop", "error", "No 'include all' filter without a control attached.")
def r06(ctx):
    controlled = {body.get("SourceFilterId") for _, kind, _, body in iter_controls(ctx.defn) if kind == "filter"}
    for group, _, body in iter_filters(ctx.defn):
        select_all = any(
            path and path[-1] == "SelectAllOptions" and node == "FILTER_ALL_VALUES" for path, node in walk(body)
        )
        bound = any(path and path[-1] == "ParameterName" for path, _ in walk(body))
        if select_all and not bound and body["FilterId"] not in controlled:
            yield group["FilterGroupId"], f"'include all' on {body['Column']['ColumnName']} with no control: it does nothing"


@rule("R07", "filter-disabled", "error", "No disabled filter groups.")
def r07(ctx):
    for group in iter_filter_groups(ctx.defn):
        if group.get("Status") == "DISABLED":
            yield group["FilterGroupId"], "disabled"


@rule("R08", "filter-single-visual", "warn", "Filters scoped to selected visuals are exceptions; list them in lint-exceptions.yaml.")
def r08(ctx):
    for group in iter_filter_groups(ctx.defn):
        scopes = ((group.get("ScopeConfiguration") or {}).get("SelectedSheets") or {}).get("SheetVisualScopingConfigurations") or []
        if any(s.get("Scope") == "SELECTED_VISUALS" for s in scopes):
            yield group["FilterGroupId"], "scoped to selected visuals"


@rule("R09", "control-label", "error", "Every control has an explicit title.")
def r09(ctx):
    for _, kind, ctype, body in iter_controls(ctx.defn):
        if ctype == "CrossSheet":
            continue
        if not (body.get("Title") or "").strip():
            yield body.get("FilterControlId") or body.get("ParameterControlId"), f"{kind} control has no title"
