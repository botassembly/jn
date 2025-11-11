import json
from pathlib import Path


def test_run_csv_to_json(invoke, people_csv, tmp_path):
    out = tmp_path / "out.json"
    res = invoke(["run", str(people_csv), str(out)])
    assert res.exit_code == 0
    data = json.loads(Path(out).read_text())
    assert len(data) == 5
    assert data[0]["name"] == "Alice"


def test_run_with_custom_home(invoke, people_csv, jn_home, tmp_path):
    out = tmp_path / "out.json"
    res = invoke(["--home", str(jn_home), "run", str(people_csv), str(out)])
    assert res.exit_code == 0
    data = json.loads(Path(out).read_text())
    assert len(data) == 5

