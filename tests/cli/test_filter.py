import json


def test_filter_field_select(invoke, sample_ndjson):
    res = invoke(["filter", ".name"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2
    # ZQ returns raw JSON values (strings, numbers, etc.)
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
                "group_by(.status)",
            ],
            input_data=input_data,
        )
        assert res.exit_code == 0
        # group_by returns array of arrays
        groups = json.loads(res.output.strip())
        assert len(groups) == 2
        # One group has 2 items (active), one has 1 (inactive)
        group_sizes = sorted([len(g) for g in groups])
        assert group_sizes == [1, 2]

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
        """Test unique with slurp mode on simple values."""
        # Use unique directly on the array (returns deduplicated array)
        input_data = '1\n2\n1\n3\n2\n'
        res = invoke(
            ["filter", "-s", "unique"],
            input_data=input_data,
        )
        assert res.exit_code == 0
        types = json.loads(res.output.strip())
        assert sorted(types) == [1, 2, 3]

    def test_slurp_add(self, invoke):
        """Test add aggregation with slurp mode on number array."""
        input_data = '10\n20\n30\n'
        res = invoke(
            ["filter", "-s", "add"],
            input_data=input_data,
        )
        assert res.exit_code == 0
        total = json.loads(res.output.strip())
        assert total == 60

    def test_slurp_min_max(self, invoke):
        """Test min/max with slurp mode."""
        input_data = '5\n2\n8\n1\n9\n'

        res = invoke(["filter", "-s", "min"], input_data=input_data)
        assert res.exit_code == 0
        assert json.loads(res.output.strip()) == 1

        res = invoke(["filter", "-s", "max"], input_data=input_data)
        assert res.exit_code == 0
        assert json.loads(res.output.strip()) == 9

    def test_slurp_first_last(self, invoke):
        """Test first/last with slurp mode."""
        input_data = '{"n": 1}\n{"n": 2}\n{"n": 3}\n'

        res = invoke(["filter", "-s", "first"], input_data=input_data)
        assert res.exit_code == 0
        assert json.loads(res.output.strip())["n"] == 1

        res = invoke(["filter", "-s", "last"], input_data=input_data)
        assert res.exit_code == 0
        assert json.loads(res.output.strip())["n"] == 3

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


class TestUnsupportedFeatures:
    """Test that unsupported jq features give helpful error messages."""

    def test_regex_error(self, invoke):
        """Test that regex functions give helpful errors."""
        res = invoke(["filter", 'test("pattern")'], input_data='{"x": 1}\n')
        assert res.exit_code == 1
        assert "Unsupported" in res.output or "test" in res.output

    def test_variable_error(self, invoke):
        """Test that variable usage gives helpful errors."""
        res = invoke(["filter", '.x as $y | $y'], input_data='{"x": 1}\n')
        assert res.exit_code == 1
        assert "Unsupported" in res.output or "variable" in res.output
