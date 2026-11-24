"""Normalize an exported definition so git diffs show only real changes."""

from __future__ import annotations

import copy
import re
from typing import Any

DATASET_PLACEHOLDER = "${{dataset:{alias}}}"
PLACEHOLDER_RE = re.compile(r"\$\{dataset:([^}]+)\}")


class AssembleError(Exception):
    pass


def drop_nulls(obj: Any) -> Any:
    """Remove None values. Empty dicts and lists stay: some are meaningful ({"AllSheets": {}})."""
    if isinstance(obj, dict):
        return {k: drop_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [drop_nulls(v) for v in obj]
    return obj


def unwrap(response: dict) -> dict:
    """Accept a full describe-analysis-definition response or just its Definition."""
    if "Definition" in response and isinstance(response["Definition"], dict):
        return response["Definition"]
    return response


def normalize(defn: dict) -> dict:
    out = drop_nulls(copy.deepcopy(unwrap(defn)))
    for key in ("CalculatedFields", "FilterGroups", "Sheets"):
        if key in out and not out[key]:
            del out[key]
    for decl in out.get("DataSetIdentifierDeclarations") or []:
        decl["DataSetArn"] = DATASET_PLACEHOLDER.format(alias=decl["Identifier"])
    if out.get("CalculatedFields"):
        out["CalculatedFields"] = sorted(
            out["CalculatedFields"], key=lambda f: (f.get("DataSetIdentifier") or "", f["Name"])
        )
    return out


def apply_env(defn: dict, env: dict) -> dict:
    """Replace ${dataset:alias} placeholders with the environment's dataset ARNs."""
    out = copy.deepcopy(defn)
    datasets = env.get("datasets") or {}
    for decl in out.get("DataSetIdentifierDeclarations") or []:
        m = PLACEHOLDER_RE.fullmatch(decl.get("DataSetArn", ""))
        if not m:
            continue
        alias = m.group(1)
        if alias not in datasets:
            raise AssembleError(f"environment '{env.get('name')}' has no dataset ARN for alias '{alias}'")
        decl["DataSetArn"] = datasets[alias]
    return out
