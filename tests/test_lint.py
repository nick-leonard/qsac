import yaml

from qsac.config import find_project
from qsac.lint import RULES, run


def lint(project_dir, defn, **kw):
    project = find_project(explicit=project_dir)
    return run(project, ["sales"], definitions={"sales": defn}, **kw)


def codes(findings):
    return {f.code for f in findings}


def test_rule_codes_are_unique_and_well_formed():
    for code, r in RULES.items():
        assert code[0] in "NFRLEP" and code[1:].isdigit() and r.name and r.summary


def test_clean_definition_has_no_findings(project_dir, clean):
    findings = lint(project_dir, clean)
    assert findings == [], "\n".join(f.as_text() for f in findings)


def test_naming_rules(project_dir, clean):
    fields = clean["CalculatedFields"]
    fields.append({"DataSetIdentifier": "orders", "Name": "Order Count copy", "Expression": "count({ORDER_NUMBER})"})
    fields.append({"DataSetIdentifier": "orders", "Name": "msr |  Bad  Spacing", "Expression": "1"})
    fields.append({"DataSetIdentifier": "orders", "Name": "msr | Rate #", "Expression": "2"})
    fields.append({"DataSetIdentifier": "orders", "Name": "msr | XYZ Total", "Expression": "3"})
    clean["Sheets"][0]["SheetId"] = "Sheet_1"
    clean["ParameterDeclarations"][0]["StringParameterDeclaration"]["Name"] = "region"
    found = codes(lint(project_dir, clean))
    assert {"N01", "N02", "N03", "N04", "N05", "N06", "N07"} <= found


def test_field_rules(project_dir, clean):
    fields = clean["CalculatedFields"]
    fields.append({"DataSetIdentifier": "orders", "Name": "msr | Unused", "Expression": "sum({ORDER_NUMBER})"})
    fields.append({"DataSetIdentifier": "orders", "Name": "msr | Order Count Again", "Expression": "distinct_count( {ORDER_NUMBER} )"})
    fields.append({"DataSetIdentifier": "orders", "Name": "msr | Globex Price",
                   "Expression": "ifelse({REGION} = 'Globex West', 10, 5)"})
    fields.append({"DataSetIdentifier": "orders", "Name": "dim | Ship Date",
                   "Expression": "coalesce({STATUS}, parseDate('2022-01-01'))"})
    found = codes(lint(project_dir, clean))
    assert {"F01", "F02", "F04", "F05"} <= found


def test_twin_fields_must_match(project_dir, clean):
    clean["DataSetIdentifierDeclarations"].append({"Identifier": "returns", "DataSetArn": "${dataset:returns}"})
    clean["CalculatedFields"].append({"DataSetIdentifier": "returns", "Name": "flag | Completed", "Expression": "1"})
    assert "F03" in codes(lint(project_dir, clean))


def test_util_field_in_visual(project_dir, clean):
    clean["CalculatedFields"][1]["Name"] = "util | Order Count"
    col = clean["Sheets"][0]["Visuals"][0]["KPIVisual"]["ChartConfiguration"]["FieldWells"]["Values"][0]
    col["NumericalMeasureField"]["Column"]["ColumnName"] = "util | Order Count"
    assert "F06" in codes(lint(project_dir, clean))


def test_filter_rules(project_dir, clean):
    groups = clean["FilterGroups"]
    dup = yaml.safe_load(yaml.safe_dump(groups[0]))
    dup["FilterGroupId"] = "fg-overview-completed-copy"
    dup["Filters"][0]["NumericEqualityFilter"]["FilterId"] = "f-completed-copy"
    dup["Status"] = "DISABLED"
    dup["ScopeConfiguration"] = {"SelectedSheets": {"SheetVisualScopingConfigurations": [
        {"SheetId": "overview", "Scope": "SELECTED_VISUALS", "VisualIds": ["overview-kpi-orders"]}]}}
    groups.append(dup)
    groups.append({"FilterGroupId": "fg-all-regions-list", "CrossDataset": "SINGLE_DATASET",
                   "ScopeConfiguration": {"AllSheets": {}},
                   "Filters": [{"CategoryFilter": {"FilterId": "f-regions-list",
                                                   "Column": {"DataSetIdentifier": "orders", "ColumnName": "REGION"},
                                                   "Configuration": {"FilterListConfiguration": {
                                                       "MatchOperator": "CONTAINS",
                                                       "CategoryValues": ["North", "South", "Globex East"]}}}}]})
    groups.append({"FilterGroupId": "fg-all-order-number", "CrossDataset": "SINGLE_DATASET",
                   "ScopeConfiguration": {"AllSheets": {}},
                   "Filters": [{"TimeRangeFilter": {"FilterId": "f-order-id",
                                                    "Column": {"DataSetIdentifier": "orders", "ColumnName": "ORDER_ID"},
                                                    "NullOption": "NON_NULLS_ONLY",
                                                    "RangeMinimumValue": {"StaticValue": "2026-01-01T00:00:00Z"}}}]})
    clean["Sheets"][0]["FilterControls"] = [{"Dropdown": {"FilterControlId": "fc-overview-region",
                                                          "SourceFilterId": "f-missing"}}]
    found = codes(lint(project_dir, clean))
    assert {"R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "E02"} <= found


def test_layout_rules(project_dir, clean):
    layout = clean["Sheets"][0]["Layouts"][0]["Configuration"]["FreeFormLayout"]
    layout["CanvasSizeOptions"]["ScreenCanvasSizeOptions"]["OptimizedViewPortWidth"] = "1920px"
    layout["Elements"][0]["XAxisLocation"] = "243px"
    clean["Sheets"][0]["TextBoxes"] = [{"SheetTextBoxId": "overview-title", "Content": "<text-box><inline color=\"#1894E1\">Hi</inline></text-box>"}]
    found = codes(lint(project_dir, clean))
    assert {"L01", "L02", "L04"} <= found


def test_env_and_phi_rules(project_dir, clean):
    clean["Sheets"][0]["Name"] = "Overview for 111122223333"
    clean["CalculatedFields"].append({"DataSetIdentifier": "orders", "Name": "dim | Contact",
                                      "Expression": "{CUSTOMER_EMAIL}"})
    vis = clean["Sheets"][0]["Visuals"][0]["KPIVisual"]["ChartConfiguration"]["FieldWells"]["Values"]
    vis.append({"NumericalMeasureField": {"FieldId": "contact", "Column": {"DataSetIdentifier": "orders",
                                                                           "ColumnName": "dim | Contact"}}})
    clean["Sheets"][0]["Visuals"][0]["KPIVisual"]["ChartConfiguration"]["FieldWells"]["Values"][0]["NumericalMeasureField"]["FieldId"] = 7
    found = codes(lint(project_dir, clean))
    assert {"E01", "E03", "P01"} <= found


def test_project_rules(project_dir, clean):
    (project_dir / "export.csv").write_text("a,b\n1,2\n")
    env = yaml.safe_load((project_dir / "envs" / "test.yaml").read_text())
    env["reports"]["sales"]["dashboard"] = "sales-dashboard"
    (project_dir / "envs" / "test.yaml").write_text(yaml.safe_dump(env))
    found = codes(lint(project_dir, clean))
    assert {"N08", "P02"} <= found


def test_exceptions_and_levels(project_dir, clean):
    clean["FilterGroups"][1]["Filters"][0]["CategoryFilter"]["Configuration"]["FilterListConfiguration"] = {
        "MatchOperator": "CONTAINS", "CategoryValues": ["North", "South", "East"]}
    assert "R02" in codes(lint(project_dir, clean))
    (project_dir / "lint-exceptions.yaml").write_text(yaml.safe_dump(
        [{"rule": "R02", "object": "fg-all-region", "reason": "approved region list"}]))
    assert "R02" not in codes(lint(project_dir, clean))

    cfg = yaml.safe_load((project_dir / "qsac.yaml").read_text())
    cfg["lint"]["levels"] = {"R06": "off"}
    (project_dir / "qsac.yaml").write_text(yaml.safe_dump(cfg))
    clean["Sheets"][0]["FilterControls"] = []
    clean["Sheets"][0]["Layouts"][0]["Configuration"]["FreeFormLayout"]["Elements"].pop()
    assert "R06" not in codes(lint(project_dir, clean))
