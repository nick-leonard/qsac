"""Project configuration.

The tool knows nothing about any particular project. Everything project-specific
lives in the project's ``qsac.yaml`` (found by walking up from the working
directory), which is deep-merged over the generic defaults below.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_NAME = "qsac.yaml"


class ConfigError(Exception):
    pass


DEFAULTS: dict[str, Any] = {
    # Prefix for every asset ID the tool creates, e.g. "acme" -> acme-sales, acme-test-sales.
    "project": None,
    "reports_dir": "reports",
    "envs_dir": "envs",
    "datasets_dir": "datasets",
    "exceptions_file": "lint-exceptions.yaml",
    "naming": {
        # Calculated fields are "<kind><separator><Description>", e.g. "msr | Orders".
        "separator": " | ",
        "field_kinds": ["dim", "msr", "bench", "flag", "sort", "label", "util"],
        # Kinds that must never be placed directly in a visual.
        "display_forbidden_kinds": ["util"],
        # All-caps words allowed in descriptions (N05). Empty list = rule skipped.
        "abbreviations": [],
        "description_charset": r"^[A-Za-z0-9 %$()+\-]+$",
        # Case-insensitive patterns that mark scratch work (N02).
        "scratch_patterns": [
            r"\btest\b", r"\btset\b", r"\btmp\b", r"\btemp\b", r"\bcopy\b",
            r"\bwrk\b", r"\bv\d+\b", r"\(validated\)", r"\bsheet ?\d+\b",
        ],
        "parameter_pattern": r"^p[A-Z][A-Za-z0-9]*$",
        "ids": {
            "sheet": r"^[a-z0-9]+(-[a-z0-9]+)*$",
            "visual": r"^[a-z0-9]+(-[a-z0-9]+)+$",
            "text_box": r"^[a-z0-9]+(-[a-z0-9]+)+$",
            "filter_group": r"^fg-[a-z0-9]+(-[a-z0-9]+)+$",
            "filter": r"^f-[a-z0-9]+(-[a-z0-9]+)*$",
            "filter_control": r"^fc-[a-z0-9]+(-[a-z0-9]+)+$",
            "parameter_control": r"^pc-[a-z0-9]+(-[a-z0-9]+)+$",
        },
    },
    "asset_ids": {
        # Environment kinds that appear in non-prod asset IDs; never usable as report names.
        "reserved": ["dev", "test", "ci"],
    },
    "grid": {"canvas_width": 1600, "step": 8},
    # Allowed absolute font sizes in px (L05). Empty list = rule skipped.
    "theme": {"font_sizes": []},
    "lint": {
        "disabled": [],
        "levels": {},
        "hardcoded_list_threshold": 3,
        # Literal values that must not be hard-coded in formulas or filters (F04, R03),
        # e.g. customer or plan names.
        "entity_literals": [],
        "id_column_pattern": r"(^|_)ID$",
        # Columns that must never reach a visual, filter or formula (P01).
        "sensitive_columns": [],
        "data_file_globs": ["*.csv", "*.tsv", "*.xlsx", "*.xls", "*.parquet", "*.har"],
        "max_file_kb": 2048,
        "skip_dirs": [".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"],
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class Project:
    root: Path
    config: dict = field(default_factory=dict)

    @property
    def reports_dir(self) -> Path:
        return self.root / self.config["reports_dir"]

    @property
    def envs_dir(self) -> Path:
        return self.root / self.config["envs_dir"]

    @property
    def datasets_dir(self) -> Path:
        return self.root / self.config["datasets_dir"]

    def report_dir(self, name: str) -> Path:
        return self.reports_dir / name

    def reports(self) -> list[str]:
        if not self.reports_dir.is_dir():
            return []
        return sorted(p.name for p in self.reports_dir.iterdir() if (p / "definition.json").is_file())

    def env_names(self) -> list[str]:
        if not self.envs_dir.is_dir():
            return []
        return sorted(p.stem for p in self.envs_dir.glob("*.yaml"))

    def env(self, name: str) -> dict:
        path = self.envs_dir / f"{name}.yaml"
        if not path.is_file():
            raise ConfigError(f"no environment file {path}")
        data = load_yaml(path) or {}
        data.setdefault("name", name)
        return data

    def exceptions(self) -> list[dict]:
        path = self.root / self.config["exceptions_file"]
        if not path.is_file():
            return []
        items = load_yaml(path) or []
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("rule") or not item.get("object") or not item.get("reason"):
                raise ConfigError(f"{path.name} entry {i + 1}: needs rule, object and reason")
        return items


def find_project(start: Path | None = None, explicit: Path | None = None) -> Project:
    if explicit is not None:
        root = explicit.resolve()
        if root.is_file():
            root = root.parent
        if not (root / CONFIG_NAME).is_file():
            raise ConfigError(f"no {CONFIG_NAME} in {root}")
    else:
        here = (start or Path.cwd()).resolve()
        for candidate in [here, *here.parents]:
            if (candidate / CONFIG_NAME).is_file():
                root = candidate
                break
        else:
            raise ConfigError(f"no {CONFIG_NAME} found in {here} or any parent folder")
    user = load_yaml(root / CONFIG_NAME) or {}
    return Project(root=root, config=deep_merge(DEFAULTS, user))
