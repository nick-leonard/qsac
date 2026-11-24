from qsac.config import find_project
from qsac.files import assemble, split
from qsac.normalize import apply_env, normalize


def test_split_assemble_round_trip(project_dir, clean):
    project = find_project(explicit=project_dir)
    defn = normalize(clean)
    split(defn, project.report_dir("sales"))
    assert assemble(project.report_dir("sales")) == defn


def test_split_writes_one_file_per_visual_and_filter_group(project_dir, clean):
    project = find_project(explicit=project_dir)
    split(normalize(clean), project.report_dir("sales"))
    rd = project.report_dir("sales")
    assert (rd / "sheets" / "01-overview" / "visuals" / "overview-kpi-orders.json").is_file()
    assert sorted(p.name for p in (rd / "filter-groups").iterdir()) == ["fg-all-completed.json", "fg-all-region.json"]


def test_resplit_removes_deleted_visuals(project_dir, clean):
    project = find_project(explicit=project_dir)
    rd = project.report_dir("sales")
    split(normalize(clean), rd)
    clean["Sheets"][0]["Visuals"] = []
    split(normalize(clean), rd)
    assert not (rd / "sheets" / "01-overview" / "visuals" / "overview-kpi-orders.json").exists()


def test_normalize_replaces_arns_and_sorts_fields(clean):
    clean["DataSetIdentifierDeclarations"][0]["DataSetArn"] = "arn:aws:quicksight:us-east-1:111122223333:dataset/x"
    clean["CalculatedFields"].reverse()
    clean["Sheets"][0]["Description"] = None
    out = normalize({"Definition": clean, "RequestId": "r"})
    assert out["DataSetIdentifierDeclarations"][0]["DataSetArn"] == "${dataset:orders}"
    assert [f["Name"] for f in out["CalculatedFields"]] == ["flag | Completed", "msr | Order Count"]
    assert "Description" not in out["Sheets"][0]


def test_apply_env_fills_dataset_arns(project_dir, clean):
    project = find_project(explicit=project_dir)
    out = apply_env(normalize(clean), project.env("test"))
    assert out["DataSetIdentifierDeclarations"][0]["DataSetArn"].endswith("orders-test")
