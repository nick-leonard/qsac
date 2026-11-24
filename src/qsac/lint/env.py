"""E rules: schema, references and environment hygiene."""

from __future__ import annotations

import json
import re

from ..definition import (
    PARAM_REF,
    column_refs,
    element_ids,
    expression_refs,
    expressions,
    iter_controls,
    iter_filter_groups,
    iter_filters,
    iter_parameters,
    layout_elements,
    walk,
)
from . import rule

ACCOUNT_RE = re.compile(r"arn:aws[\w-]*:|(?<!\d)\d{12}(?!\d)")


@rule("E01", "schema-valid", "error", "The definition validates against QuickSight's AnalysisDefinition shape (botocore).")
def e01(ctx):
    import botocore.session
    from botocore.validate import ParamValidator

    model = botocore.session.get_session().get_service_model("quicksight")
    report = ParamValidator().validate(ctx.defn, model.shape_for("AnalysisDefinition"))
    if report.has_errors():
        for line in report.generate_report().splitlines():
            line = line.strip()
            if line:
                yield "definition", line


def _dataset_columns(ctx) -> dict[str, set[str]]:
    """Columns per dataset alias from datasets/<alias>.json (describe-data-set output), if present."""
    cols: dict[str, set[str]] = {}
    ddir = ctx.project.datasets_dir
    if not ddir.is_dir():
        return cols
    for path in ddir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        ds = data.get("DataSet", data)
        names = {c["Name"] for c in ds.get("OutputColumns") or []}
        if names:
            cols[path.stem] = names
    return cols


@rule("E02", "references-resolve", "error", "Every reference points to something that exists.")
def e02(ctx):
    defn = ctx.defn
    declared = {d["Identifier"] for d in defn.get("DataSetIdentifierDeclarations") or []}
    sheets = {s["SheetId"]: s for s in defn.get("Sheets") or []}
    visuals = {sid: element_ids(s) for sid, s in sheets.items()}
    filter_ids = {body["FilterId"] for _, _, body in iter_filters(defn)}
    params = {body["Name"] for _, body in iter_parameters(defn)}
    calcs = {(f.get("DataSetIdentifier"), f["Name"]) for f in ctx.calc_fields}
    ds_cols = _dataset_columns(ctx)

    for ds, name in sorted(set(column_refs(defn)), key=lambda x: (str(x[0]), x[1])):
        if ds is not None and ds not in declared:
            yield name, f"dataset alias '{ds}' isn't declared"
        elif ds in ds_cols and (ds, name) not in calcs and name not in ds_cols[ds]:
            yield name, f"no column or calculated field '{name}' on dataset '{ds}'"
    for f in ctx.calc_fields:
        ds = f.get("DataSetIdentifier")
        if ds is not None and ds not in declared:
            yield f["Name"], f"dataset alias '{ds}' isn't declared"
        for ref in expression_refs(f["Expression"]):
            if ds in ds_cols and (ds, ref) not in calcs and ref not in ds_cols[ds]:
                yield f["Name"], f"formula refers to unknown field '{ref}'"
    for _, expr in expressions(defn):
        for p in PARAM_REF.findall(expr):
            if p not in params:
                yield p, "parameter referenced in an expression isn't declared"
    for path, node in walk(defn):
        if path and path[-1] in ("ParameterName", "SourceParameterName") and isinstance(node, str) and node not in params:
            yield node, "parameter isn't declared"

    for group in iter_filter_groups(defn):
        scopes = ((group.get("ScopeConfiguration") or {}).get("SelectedSheets") or {}).get("SheetVisualScopingConfigurations") or []
        for scope in scopes:
            sid = scope["SheetId"]
            if sid not in sheets:
                yield group["FilterGroupId"], f"scoped to missing sheet '{sid}'"
                continue
            for vid in scope.get("VisualIds") or []:
                if vid not in visuals[sid]:
                    yield group["FilterGroupId"], f"scoped to missing visual '{vid}' on sheet '{sid}'"
    for sheet, kind, _, body in iter_controls(defn):
        if kind == "filter" and body.get("SourceFilterId") not in filter_ids:
            yield body["FilterControlId"], f"control points to missing filter '{body.get('SourceFilterId')}'"
    for sid, sheet in sheets.items():
        for _, el in layout_elements(sheet):
            if el["ElementId"] not in visuals[sid]:
                yield el["ElementId"], f"layout element on sheet '{sid}' has no matching object"


@rule("E03", "no-account-ids", "error", "No account IDs or ARNs in report files; they belong in envs/.")
def e03(ctx):
    for path, node in walk(ctx.defn):
        if isinstance(node, str) and not node.startswith("${") and ACCOUNT_RE.search(node):
            yield "/".join(str(p) for p in path), "contains an account ID or ARN"
