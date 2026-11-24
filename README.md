# qsac: Amazon QuickSight as code

*Working name.*

Keep QuickSight analyses and dashboards in git as reviewable files, lint them against numbered rules, and deploy them through CI.

The tool is generic. It knows nothing about the project that uses it: every project-specific value comes from the project's `qsac.yaml`, which the tool finds by walking up from the working directory. It never imports, reads or names anything else in the host project.

## Status

| Piece | State |
|---|---|
| `split` / `assemble`: definition ⇄ one file per visual, sheet and filter group | Working, tested |
| `normalize`: drop nulls, sort fields, replace dataset ARNs with `${dataset:alias}` placeholders | Working, tested |
| `lint`: rule engine, levels, exceptions | Working, tested |
| Lint rules | 31 implemented; L03 component-unchanged and L06 explicit-labels are planned |
| `export`: DescribeAnalysisDefinition (read-only) | Written, not yet run against a live account |
| Components and grid layout (`layout.yaml`) | Planned |
| Deploy: update-analysis, update-dashboard, publish, rollback, drift gate | Planned |
| Control-total verification | Planned |

## Install

```bash
pip install -e path/to/qsac          # or: pip install "path/to/qsac[test]" to run its tests
qsac --help
```

Requires Python 3.11+, boto3 and PyYAML.

## Project layout the tool expects

```
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
|---|---|
| N | names and IDs: `kind \| Description` fields, scratch words, spacing, ID and parameter patterns, asset IDs |
| F | calculated fields: unused, duplicate formulas, twins across datasets, hard-coded entities, date defaults, internal fields in visuals |
| R | filters and controls: duplicates, hard-coded lists, fixed dates, ID columns, no-op filters, disabled groups, single-visual scope, control titles |
| L | layout and style: canvas width, grid, theme colors, type scale |
| E | schema validity (botocore model), references, account IDs outside `envs/` |
| P | sensitive columns, data files in the repo |

Adding a rule: write a function in `src/qsac/lint/<group>.py`, decorate it with `@rule(code, name, level, summary)`, have it yield `(object, message)` pairs, and add a test.

## Design rules for contributors

- **No host-project knowledge.** No project names, field names or IDs in code, defaults, docs or tests. Tests use the synthetic `acme` project in `tests/conftest.py`.
- **The definition format is the public QuickSight API format** (`DescribeAnalysisDefinition`), never the console's internal JSON.
- **Read-only by default.** Commands that write to AWS will be explicit and separate.

## License

To be decided before the first public release.
