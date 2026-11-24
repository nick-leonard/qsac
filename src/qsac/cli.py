"""Command line: qsac <command>. Run from anywhere inside a project (a folder with qsac.yaml)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, find_project
from .files import assemble, dump, split
from .normalize import AssembleError, apply_env, normalize


def _project(args):
    return find_project(explicit=Path(args.project) if args.project else None)


def cmd_lint(args) -> int:
    from .lint import run

    project = _project(args)
    reports = args.reports or project.reports()
    findings = run(project, reports)
    errors = [f for f in findings if f.level == "error"]
    if args.format == "json":
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        for f in findings:
            print(f.as_text())
        print(f"{len(reports)} report(s), {len(errors)} error(s), {len(findings) - len(errors)} warning(s)")
    return 1 if errors else 0


def cmd_rules(args) -> int:
    from .lint import RULES

    for r in sorted(RULES.values(), key=lambda x: x.code):
        print(f"{r.code}  {r.name:<26} {r.level:<5}  {r.summary}")
    return 0


def cmd_split(args) -> int:
    project = _project(args)
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    written = split(normalize(source), project.report_dir(args.report))
    print(f"wrote {len(written)} file(s) under {project.report_dir(args.report).relative_to(project.root)}")
    return 0


def cmd_assemble(args) -> int:
    project = _project(args)
    defn = assemble(project.report_dir(args.report))
    if args.env:
        defn = apply_env(defn, project.env(args.env))
    text = dump(defn)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def cmd_export(args) -> int:
    from .aws import describe_analysis_definition

    project = _project(args)
    env = project.env(args.env)
    analysis_id = args.analysis_id or ((env.get("reports") or {}).get(args.report) or {}).get("analysis")
    if not analysis_id:
        raise ConfigError(f"no analysis ID: pass --analysis-id or set reports.{args.report}.analysis in envs/{args.env}.yaml")
    defn = describe_analysis_definition(env, analysis_id)
    written = split(normalize(defn), project.report_dir(args.report))
    print(f"exported {analysis_id} -> {len(written)} file(s) under {project.report_dir(args.report).relative_to(project.root)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qsac", description="Amazon QuickSight analyses and dashboards as code.")
    p.add_argument("--version", action="version", version=f"qsac {__version__}")
    p.add_argument("--project", help="project folder (default: nearest parent with qsac.yaml)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("lint", help="run the lint rules")
    s.add_argument("reports", nargs="*", help="report names (default: all)")
    s.add_argument("--format", choices=["text", "json"], default="text")
    s.set_defaults(func=cmd_lint)

    s = sub.add_parser("rules", help="list the lint rules")
    s.set_defaults(func=cmd_rules)

    s = sub.add_parser("split", help="import a definition JSON file into reports/<report>/")
    s.add_argument("source", help="describe-analysis-definition output, or just its Definition")
    s.add_argument("report")
    s.set_defaults(func=cmd_split)

    s = sub.add_parser("assemble", help="build one definition JSON from reports/<report>/")
    s.add_argument("report")
    s.add_argument("--env", help="fill in dataset ARNs from envs/<env>.yaml")
    s.add_argument("-o", "--output")
    s.set_defaults(func=cmd_assemble)

    s = sub.add_parser("export", help="read an analysis from QuickSight (read-only) into reports/<report>/")
    s.add_argument("report")
    s.add_argument("--env", required=True)
    s.add_argument("--analysis-id")
    s.set_defaults(func=cmd_export)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, AssembleError, FileNotFoundError) as exc:
        print(f"qsac: {exc}", file=sys.stderr)
        return 2
