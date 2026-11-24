"""P rules: sensitive data (PHI/PII) must not reach reports or the repo."""

from __future__ import annotations

import fnmatch
import os

from ..definition import column_refs, expression_refs, expressions
from . import rule


@rule("P01", "no-sensitive-columns", "error", "Configured sensitive columns aren't used in any visual, field or filter.")
def p01(ctx):
    sensitive = set(ctx.cfg["lint"]["sensitive_columns"])
    if not sensitive:
        return
    hits: set[str] = {name for _, name in column_refs(ctx.defn) if name in sensitive}
    for _, expr in expressions(ctx.defn):
        hits |= expression_refs(expr) & sensitive
    for name in sorted(hits):
        yield name, "sensitive column is used"


@rule("P02", "no-data-files", "error", "No data files (CSV, XLSX, query results) or oversized files in the repo.", scope="project")
def p02(project):
    lint_cfg = project.config["lint"]
    globs = lint_cfg["data_file_globs"]
    max_bytes = int(lint_cfg["max_file_kb"]) * 1024
    skip = set(lint_cfg["skip_dirs"])
    for dirpath, dirnames, filenames in os.walk(project.root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            rel = os.path.relpath(path, project.root)
            if any(fnmatch.fnmatch(fname.lower(), g) for g in globs):
                yield rel, "data file in the repo"
            elif os.path.getsize(path) > max_bytes:
                yield rel, f"larger than {lint_cfg['max_file_kb']} KB"
