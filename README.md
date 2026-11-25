# qsac: Amazon QuickSight as code

[![tests](https://github.com/nick-leonard/qsac/actions/workflows/tests.yml/badge.svg)](https://github.com/nick-leonard/qsac/actions/workflows/tests.yml) ![Amazon QuickSight](https://img.shields.io/badge/Amazon-QuickSight-232F3E) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) ![status: alpha](https://img.shields.io/badge/status-alpha-orange) [![last commit](https://img.shields.io/github/last-commit/nick-leonard/qsac)](https://github.com/nick-leonard/qsac/commits/main)

Keep QuickSight analyses and dashboards in git as reviewable files, lint them against numbered rules, and deploy them through CI.

QuickSight analyses live in the console. There is no diff, no review and no history, so a renamed field, a hard-coded customer filter or a visual 3px off the grid ships unnoticed. qsac pulls each analysis into git as one small JSON file per visual, sheet and filter group, checks it against 31 numbered lint rules, and fails CI when something breaks them.

## What it looks like

An analysis with a copied calculated field, a hard-coded customer name and a misplaced visual:

```console
$ qsac lint sales
sales: E02 references-resolve [error] flag | Completed: formula refers to unknown field 'CUSTOMER'
sales: F01 field-unused [error] msr | Order Count copy: not used anywhere
sales: F02 field-duplicate-formula [error] msr | Order Count copy: same formula as 'msr | Order Count'
sales: F04 no-entity-literals [error] flag | Completed: hard-coded globex; use a mapping table or parameter
sales: L02 on-grid [error] overview-kpi-orders: off the 8px grid: XAxisLocation=19
sales: N02 no-scratch-names [error] msr | Order Count copy: scratch word 'copy' in 'msr | Order Count copy'
1 report(s), 6 error(s), 0 warning(s)
```

`qsac lint` exits 1 on any error-level finding, so it can gate a merge request. `--format json` gives the same findings as machine-readable output.

`split` turns one `DescribeAnalysisDefinition` response into files small enough to review in a diff:

```console
$ qsac split response.json sales
wrote 6 file(s) under reports/sales

reports/sales/
├── definition.json
├── calculated-fields.json
├── filter-groups/
│   ├── fg-all-completed.json
│   └── fg-all-region.json
└── sheets/01-overview/
    ├── sheet.json
    └── visuals/overview-kpi-orders.json
```

A change to one visual is a change to one file. `assemble` puts the pieces back together with the target environment's dataset ARNs filled in.

## Why not the console, or CloudFormation?

- **The console** has no diff, no review and no history.
- **CloudFormation and Terraform** can deploy an analysis definition, but they hold the whole analysis in one file that runs to thousands of lines, and nothing checks naming, filters or layout against your team's conventions.
- **qsac** keeps the public API format, splits it into reviewable files, and enforces those conventions as lint rules with stable codes you can cite in a review.

## Install

```bash
pip install "git+https://github.com/nick-leonard/qsac"
qsac --help
```

Requires Python 3.11+, boto3 and PyYAML. To work on qsac itself:

```bash
git clone https://github.com/nick-leonard/qsac && cd qsac
pip install -e ".[test]"
pytest
```

## Status

| Piece | State |
| --- | --- |
| `split` / `assemble`: definition ⇄ one file per visual, sheet and filter group | Working, tested |
| `normalize`: drop nulls, sort fields, replace dataset ARNs with `${dataset:alias}` placeholders | Working, tested |
| `lint`: rule engine, levels, exceptions | Working, tested |
| Lint rules | 31 implemented |

### Roadmap

- **`export`** from a live account (`DescribeAnalysisDefinition`, read-only).
- **Lint rules** L03 component-unchanged and L06 explicit-labels.
- **Components and grid layout** (`layout.yaml`).
- **Deploy:** update-analysis, update-dashboard, publish, rollback, and a drift gate.
- **Control-total verification.**

## Use it in CI

Linting runs offline: it needs no AWS credentials. GitHub Actions:

```yaml
lint-quicksight:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: "3.12"}
    - run: pip install "git+https://github.com/nick-leonard/qsac"
    - run: qsac lint
```

GitLab CI:

```yaml
lint-quicksight:
  image: python:3.12
  script:
    - pip install "git+https://github.com/nick-leonard/qsac"
    - qsac lint
```

## Project layout the tool expects

The tool is generic. It knows nothing about the project that uses it: every project-specific value comes from the project's `qsac.yaml`, which the tool finds by walking up from the working directory.

```text
<project>/
├── qsac.yaml                 # project settings (see below)
├── lint-exceptions.yaml      # optional: [{rule, object, reason, report?}]
├── envs/<env>.yaml           # region, profile, account_id, dataset ARNs, asset IDs per report
├── datasets/<alias>.json     # optional: describe-data-set output, enables column checks (E02)
└── reports/<report>/
    ├── definition.json
    ├── calculated-fields.json
    ├── filter-groups/<FilterGroupId>.json
    └── sheets/<nn>-<SheetId>/{sheet.json, visuals/<VisualId>.json}
```

### `qsac.yaml`

All keys are optional; defaults are in `src/qsac/config.py`.

```yaml
project: acme                      # asset ID prefix: acme-sales, acme-test-sales, acme-dev-sales-<user>
naming:
  separator: " | "                 # calculated fields are "<kind> | <Description>"
  field_kinds: [dim, msr, bench, flag, sort, label, util]
  abbreviations: [KPI, YTD]        # all-caps words allowed in descriptions (N05)
grid: {canvas_width: 1600, step: 8}
theme: {font_sizes: [12, 14, 16, 20, 28]}
lint:
  disabled: [L05]                  # rule codes to skip
  levels: {R08: error}             # override a rule's level: error | warn | off
  entity_literals: [globex]        # names that must not be hard-coded in formulas or filters
  sensitive_columns: [CUSTOMER_EMAIL]
```

### `envs/<env>.yaml`

```yaml
kind: test                         # prod | test | dev | ci
profile: my-aws-profile
region: us-east-1
account_id: "111122223333"
datasets:                          # alias (DataSetIdentifier) -> ARN
  orders: arn:aws:quicksight:us-east-1:111122223333:dataset/orders-test
reports:
  sales: {analysis: acme-test-sales, dashboard: acme-test-sales}
```

## Commands

```bash
qsac rules                                   # list the lint rules
qsac lint [report ...] [--format json]       # exit 1 on any error-level finding
qsac split response.json sales               # import a describe-analysis-definition response
qsac assemble sales --env test -o out.json   # one definition with the env's dataset ARNs filled in
qsac export sales --env dev --analysis-id <id>   # read from QuickSight into reports/sales/
```

## Lint rules

Codes are stable, so they can be cited in reviews and exceptions. Run `qsac rules` for the current list.

| Group | Covers |
| --- | --- |
| N | names and IDs: `kind \| Description` fields, scratch words, spacing, ID and parameter patterns, asset IDs |
| F | calculated fields: unused, duplicate formulas, twins across datasets, hard-coded entities, date defaults, internal fields in visuals |
| R | filters and controls: duplicates, hard-coded lists, fixed dates, ID columns, no-op filters, disabled groups, single-visual scope, control titles |
| L | layout and style: canvas width, grid, theme colors, type scale |
| E | schema validity (botocore model), references, account IDs outside `envs/` |
| P | sensitive columns, data files in the repo |

Adding a rule: write a function in `src/qsac/lint/<group>.py`, decorate it with `@rule(code, name, level, summary)`, have it yield `(object, message)` pairs, and add a test.

## Design rules for contributors

- **No host-project knowledge.** No project names, field names or IDs in code, defaults, docs or tests. The tool never imports, reads or names anything in the host project beyond its `qsac.yaml` and the files above. Tests use the synthetic `acme` project in `tests/conftest.py`.
- **The definition format is the public QuickSight API format** (`DescribeAnalysisDefinition`), never the console's internal JSON.
- **Read-only by default.** Commands that write to AWS will be explicit and separate.

## License

MIT. See [LICENSE](LICENSE).
