"""AWS calls. Read-only for now: export (DescribeAnalysisDefinition).

Deploy operations (update-analysis, update-dashboard, publish, rollback) will be
added here behind explicit commands; nothing in this module writes to AWS yet.
"""

from __future__ import annotations

import boto3


def session(env: dict) -> boto3.session.Session:
    return boto3.session.Session(profile_name=env.get("profile"), region_name=env["region"])


def account_id(env: dict) -> str:
    if env.get("account_id"):
        return str(env["account_id"])
    return session(env).client("sts").get_caller_identity()["Account"]


def describe_analysis_definition(env: dict, analysis_id: str) -> dict:
    qs = session(env).client("quicksight")
    resp = qs.describe_analysis_definition(AwsAccountId=account_id(env), AnalysisId=analysis_id)
    errors = resp.get("Errors") or []
    if errors:
        print(f"warning: QuickSight reported {len(errors)} definition error(s) for {analysis_id}:")
        for err in errors[:20]:
            print(f"  - {err.get('Type')}: {err.get('Message')}")
    return resp["Definition"]
