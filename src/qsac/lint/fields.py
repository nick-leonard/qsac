"""F rules: calculated fields."""

from __future__ import annotations

import re
from collections import defaultdict

from . import rule


def _norm(expr: str) -> str:
    return re.sub(r"\s+", "", expr or "").lower()


@rule("F01", "field-unused", "error", "Every calculated field is used by a visual, filter, control or another used field.")
def f01(ctx):
    used = ctx.used_fields
    for f in ctx.calc_fields:
        if (f.get("DataSetIdentifier"), f["Name"]) not in used:
            yield f["Name"], "not used anywhere"


@rule("F02", "field-duplicate-formula", "error", "No two fields on the same dataset share a formula.")
def f02(ctx):
    by_expr: dict[tuple, list[str]] = defaultdict(list)
    for f in ctx.calc_fields:
        by_expr[(f.get("DataSetIdentifier"), _norm(f["Expression"]))].append(f["Name"])
    for names in by_expr.values():
        for name in names[1:]:
            yield name, f"same formula as '{names[0]}'"


@rule("F03", "twin-fields-match", "error", "A field that exists on several datasets has the same formula on each.")
def f03(ctx):
    by_name: dict[str, list[dict]] = defaultdict(list)
    for f in ctx.calc_fields:
        by_name[f["Name"]].append(f)
    for name, fields in by_name.items():
        if len({_norm(f["Expression"]) for f in fields}) > 1:
            yield name, "formula differs between datasets " + ", ".join(str(f.get("DataSetIdentifier")) for f in fields)


@rule("F04", "no-entity-literals", "error", "No configured entity names (customers, plans, ...) hard-coded in formulas.")
def f04(ctx):
    literals = [s.lower() for s in ctx.cfg["lint"]["entity_literals"]]
    if not literals:
        return
    for f in ctx.calc_fields:
        quoted = " ".join(re.findall(r"'[^']*'|\"[^\"]*\"", f["Expression"])).lower()
        hits = [lit for lit in literals if lit in quoted]
        if hits:
            yield f["Name"], f"hard-coded {', '.join(hits)}; use a mapping table or parameter"


@rule("F05", "no-literal-date-default", "warn", "No coalesce that fills a missing date with a fixed date.")
def f05(ctx):
    for f in ctx.calc_fields:
        expr = f["Expression"]
        if re.search(r"coalesce\s*\(", expr, re.IGNORECASE) and re.search(r"\d{4}-\d{2}-\d{2}", expr):
            yield f["Name"], "fills missing dates with a fixed date"


@rule("F06", "util-not-displayed", "error", "Internal (util) fields aren't placed directly in visuals.")
def f06(ctx):
    forbidden = set(ctx.cfg["naming"]["display_forbidden_kinds"])
    for ds, name in sorted(ctx.visual_column_refs, key=lambda x: (str(x[0]), x[1])):
        if ctx.kind_of(name) in forbidden:
            yield name, "internal field used directly in a visual"
