"""Synthetic test project: a fictional retailer ("acme") with one orders dataset."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

CLEAN = {
    "DataSetIdentifierDeclarations": [{"Identifier": "orders", "DataSetArn": "${dataset:orders}"}],
    "CalculatedFields": [
        {"DataSetIdentifier": "orders", "Name": "flag | Completed", "Expression": "ifelse({STATUS} = 'Completed', 1, 0)"},
        {"DataSetIdentifier": "orders", "Name": "msr | Order Count", "Expression": "distinct_count({ORDER_NUMBER})"},
    ],
    "ParameterDeclarations": [
        {"StringParameterDeclaration": {"ParameterValueType": "MULTI_VALUED", "Name": "pRegion",
                                        "DefaultValues": {"StaticValues": ["West"]}}}
    ],
    "FilterGroups": [
        {
            "FilterGroupId": "fg-all-completed",
            "CrossDataset": "SINGLE_DATASET",
            "Status": "ENABLED",
            "ScopeConfiguration": {"AllSheets": {}},
            "Filters": [{"NumericEqualityFilter": {
                "FilterId": "f-completed",
                "Column": {"DataSetIdentifier": "orders", "ColumnName": "flag | Completed"},
                "Value": 1, "MatchOperator": "EQUALS", "NullOption": "NON_NULLS_ONLY"}}],
        },
        {
            "FilterGroupId": "fg-all-region",
            "CrossDataset": "SINGLE_DATASET",
            "Status": "ENABLED",
            "ScopeConfiguration": {"AllSheets": {}},
            "Filters": [{"CategoryFilter": {
                "FilterId": "f-region",
                "Column": {"DataSetIdentifier": "orders", "ColumnName": "REGION"},
                "Configuration": {"FilterListConfiguration": {"MatchOperator": "CONTAINS",
                                                              "SelectAllOptions": "FILTER_ALL_VALUES"}}}}],
        },
    ],
    "Sheets": [
        {
            "SheetId": "overview",
            "Name": "Overview",
            "FilterControls": [{"Dropdown": {"FilterControlId": "fc-overview-region", "SourceFilterId": "f-region",
                                             "Title": "Region"}}],
            "Visuals": [{"KPIVisual": {
                "VisualId": "overview-kpi-orders",
                "ChartConfiguration": {"FieldWells": {"Values": [{"NumericalMeasureField": {
                    "FieldId": "orders-count",
                    "Column": {"DataSetIdentifier": "orders", "ColumnName": "msr | Order Count"}}}]}}}}],
            "Layouts": [{"Configuration": {"FreeFormLayout": {
                "CanvasSizeOptions": {"ScreenCanvasSizeOptions": {"OptimizedViewPortWidth": "1600px"}},
                "Elements": [
                    {"ElementId": "overview-kpi-orders", "ElementType": "VISUAL", "XAxisLocation": "16px",
                     "YAxisLocation": "16px", "Width": "384px", "Height": "160px"},
                    {"ElementId": "fc-overview-region", "ElementType": "FILTER_CONTROL", "XAxisLocation": "416px",
                     "YAxisLocation": "16px", "Width": "240px", "Height": "64px"},
                ]}}}],
        }
    ],
}

CONFIG = {
    "project": "acme",
    "naming": {"abbreviations": ["KPI"]},
    "lint": {"entity_literals": ["globex"], "sensitive_columns": ["CUSTOMER_EMAIL"]},
}

ENVS = {
    "prod": {"kind": "prod", "region": "us-east-1",
             "datasets": {"orders": "arn:aws:quicksight:us-east-1:111122223333:dataset/orders-prod"},
             "reports": {"sales": {"dashboard": "acme-sales"}}},
    "test": {"kind": "test", "region": "us-east-1",
             "datasets": {"orders": "arn:aws:quicksight:us-east-1:111122223333:dataset/orders-test"},
             "reports": {"sales": {"dashboard": "acme-test-sales", "analysis": "acme-test-sales"}}},
}

DATASET = {"DataSet": {"OutputColumns": [{"Name": n, "Type": "STRING"} for n in
                                         ("ORDER_NUMBER", "STATUS", "REGION", "CUSTOMER_EMAIL")]}}


@pytest.fixture
def clean():
    return copy.deepcopy(CLEAN)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "qsac.yaml").write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    (tmp_path / "envs").mkdir()
    for name, env in ENVS.items():
        (tmp_path / "envs" / f"{name}.yaml").write_text(yaml.safe_dump(env), encoding="utf-8")
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "orders.json").write_text(json.dumps(DATASET), encoding="utf-8")
    return tmp_path
