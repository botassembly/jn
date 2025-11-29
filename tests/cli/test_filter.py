import json


def test_filter_field_select(invoke, sample_ndjson):
    res = invoke(["filter", ".name"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2
    # jq returns raw JSON values (strings, numbers, etc.), not just objects
    values = [json.loads(line) for line in lines]
    assert values == ["Alice", "Bob"]


def test_filter_condition(invoke, sample_ndjson):
    res = invoke(["filter", "select(.age > 25)"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["name"] == "Alice"


class TestSlurpMode:
    """Test slurp mode for aggregation queries."""

    def test_slurp_length(self, invoke, sample_ndjson):
        """Test counting records with slurp mode."""
        res = invoke(["filter", "-s", "length"], input_data=sample_ndjson)
        assert res.exit_code == 0
        count = json.loads(res.output.strip())
        assert count == 2

    def test_slurp_group_by(self, invoke):
        """Test group_by with slurp mode."""
        input_data = (
            '{"status": "active", "id": 1}\n'
            '{"status": "inactive", "id": 2}\n'
            '{"status": "active", "id": 3}\n'
        )
        res = invoke(
            [
                "filter",
                "-s",
                "group_by(.status) | map({status: .[0].status, count: length}) | .[]",
            ],
            input_data=input_data,
        )
        assert res.exit_code == 0
        lines = [
            json.loads(line) for line in res.output.strip().split("\n") if line
        ]
        # group_by returns array of arrays, we mapped to objects then emitted each
        assert len(lines) == 2
        statuses = {r["status"]: r["count"] for r in lines}
        assert statuses["active"] == 2
        assert statuses["inactive"] == 1

    def test_slurp_sort_by(self, invoke):
        """Test sort_by with slurp mode."""
        input_data = (
            '{"name": "Charlie", "score": 75}\n'
            '{"name": "Alice", "score": 95}\n'
            '{"name": "Bob", "score": 85}\n'
        )
        res = invoke(
            ["filter", "--slurp", "sort_by(.score) | reverse | .[]"],
            input_data=input_data,
        )
        assert res.exit_code == 0
        lines = [
            json.loads(line) for line in res.output.strip().split("\n") if line
        ]
        assert len(lines) == 3
        # Should be sorted by score descending
        assert lines[0]["name"] == "Alice"
        assert lines[1]["name"] == "Bob"
        assert lines[2]["name"] == "Charlie"

    def test_slurp_unique(self, invoke):
        """Test unique with slurp mode."""
        input_data = (
            '{"type": "a"}\n'
            '{"type": "b"}\n'
            '{"type": "a"}\n'
            '{"type": "c"}\n'
            '{"type": "b"}\n'
        )
        res = invoke(
            ["filter", "-s", "[.[].type] | unique"],
            input_data=input_data,
        )
        assert res.exit_code == 0
        types = json.loads(res.output.strip())
        assert sorted(types) == ["a", "b", "c"]

    def test_slurp_sum(self, invoke):
        """Test sum aggregation with slurp mode."""
        input_data = '{"amount": 10}\n' '{"amount": 20}\n' '{"amount": 30}\n'
        res = invoke(
            ["filter", "-s", "[.[].amount] | add"],
            input_data=input_data,
        )
        assert res.exit_code == 0
        total = json.loads(res.output.strip())
        assert total == 60

    def test_without_slurp_streaming(self, invoke, sample_ndjson):
        """Test that without slurp, records stream one at a time."""
        # Without slurp, 'length' on each object returns number of keys
        res = invoke(["filter", "length"], input_data=sample_ndjson)
        assert res.exit_code == 0
        lines = [
            json.loads(line) for line in res.output.strip().split("\n") if line
        ]
        # Each object has 2 keys (name, age)
        assert lines == [2, 2]
