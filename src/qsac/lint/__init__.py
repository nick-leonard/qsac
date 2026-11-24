"""Lint engine: a registry of numbered rules run against each report and the project.

A rule is a function decorated with @rule. Report rules get a Context and yield
(object, message) pairs; project rules get the Project and yield the same.
Levels and on/off come from the project's qsac.yaml (lint.levels, lint.disabled);
individual exceptions come from lint-exceptions.yaml (rule, object, reason).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable, Iterable, Iterator

from ..config import Project
from ..definition import column_refs, expression_refs, iter_visuals, walk

LEVELS = ("error", "warn")


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    level: str
    summary: str
    scope: str  # "report" or "project"
    func: Callable


@dataclass(frozen=True)
class Finding:
    code: str
    name: str
    level: str
    report: str
    obj: str
    message: str

    def as_text(self) -> str:
        where = f"{self.report}: " if self.report else ""
        return f"{where}{self.code} {self.name} [{self.level}] {self.obj}: {self.message}"


RULES: dict[str, Rule] = {}


def rule(code: str, name: str, level: str, summary: str, scope: str = "report"):
    assert level in LEVELS and scope in ("report", "project")

    def deco(func: Callable) -> Callable:
        if code in RULES:
            raise ValueError(f"duplicate rule code {code}")
        RULES[code] = Rule(code, name, level, summary, scope, func)
        return func

    return deco


@dataclass
class Context:
    project: Project
    report: str
    defn: dict
    cfg: dict = field(init=False)

    def __post_init__(self) -> None:
        self.cfg = self.project.config

    @property
    def calc_fields(self) -> list[dict]:
        return self.defn.get("CalculatedFields") or []

    @property
    def sep(self) -> str:
        return self.cfg["naming"]["separator"]

    def kind_of(self, name: str) -> str | None:
        head, sep, _ = name.partition(self.sep)
        return head if sep and head in self.cfg["naming"]["field_kinds"] else None

    def description_of(self, name: str) -> str:
        return name.partition(self.sep)[2] if self.kind_of(name) else name

    @cached_property
    def used_fields(self) -> set[tuple[str | None, str]]:
        """(dataset, name) of every calculated field reachable from something displayed or filtered."""
        calcs = {(f.get("DataSetIdentifier"), f["Name"]): f for f in self.calc_fields}
        # Column formatting (ColumnConfigurations) alone doesn't make a field "used".
        rest = {k: v for k, v in self.defn.items() if k not in ("CalculatedFields", "ColumnConfigurations")}
        used: set[tuple[str | None, str]] = set(column_refs(rest))
        loose_names: set[str] = set()
        for path, node in walk(rest):
            if path and path[-1] == "Expression" and isinstance(node, str):
                loose_names |= expression_refs(node)
        used |= {key for key in calcs if key[1] in loose_names}
        frontier = [key for key in used if key in calcs]
        while frontier:
            ds, name = frontier.pop()
            for ref in expression_refs(calcs[(ds, name)]["Expression"]):
                key = (ds, ref)
                if key in calcs and key not in used:
                    used.add(key)
                    frontier.append(key)
        return used

    @cached_property
    def visual_column_refs(self) -> set[tuple[str | None, str]]:
        refs: set[tuple[str | None, str]] = set()
        for _, _, body in iter_visuals(self.defn):
            refs |= set(column_refs(body))
        return refs


def _effective_level(project: Project, r: Rule) -> str | None:
    lint_cfg = project.config["lint"]
    if r.code in (lint_cfg.get("disabled") or []):
        return None
    level = (lint_cfg.get("levels") or {}).get(r.code, r.level)
    return None if level == "off" else level


def _excepted(exceptions: list[dict], code: str, report: str, obj: str) -> bool:
    for exc in exceptions:
        if exc["rule"] != code:
            continue
        if exc.get("report") and exc["report"] != report:
            continue
        if fnmatch.fnmatchcase(obj, str(exc["object"])):
            return True
    return False


def run(project: Project, reports: Iterable[str] | None = None, definitions: dict[str, dict] | None = None) -> list[Finding]:
    """Lint the given reports (default: all). `definitions` lets callers pass assembled definitions."""
    from ..files import assemble

    exceptions = project.exceptions()
    names = list(reports) if reports else project.reports()
    findings: list[Finding] = []

    def emit(r: Rule, level: str, report: str, items: Iterator[tuple[str, str]]) -> None:
        for obj, message in items:
            if not _excepted(exceptions, r.code, report, obj):
                findings.append(Finding(r.code, r.name, level, report, obj, message))

    for r in sorted(RULES.values(), key=lambda x: x.code):
        level = _effective_level(project, r)
        if level is None or r.scope != "project":
            continue
        emit(r, level, "", r.func(project))

    for report in names:
        defn = (definitions or {}).get(report)
        if defn is None:
            defn = assemble(project.report_dir(report))
        ctx = Context(project, report, defn)
        for r in sorted(RULES.values(), key=lambda x: x.code):
            level = _effective_level(project, r)
            if level is None or r.scope != "report":
                continue
            emit(r, level, report, r.func(ctx))
    return findings


# Register rules.
from . import env, fields, filters, names, phi, style  # noqa: E402,F401
