"""Integration tests for source and target format adapters."""

import json
from pathlib import Path

import pytest

from jn.cli import app


@pytest.fixture
def yaml_file(tmp_path):
    """Create a test YAML file."""
    yaml_path = tmp_path / "test.yaml"
    yaml_path.write_text(
        "- name: Alice\n"
        "  age: 30\n"
        "  city: NYC\n"
        "- name: Bob\n"
        "  age: 25\n"
        "  city: SF\n"
    )
    return yaml_path


@pytest.fixture
def toml_file(tmp_path):
    """Create a test TOML file."""
    toml_path = tmp_path / "test.toml"
    toml_path.write_text(
        "[[items]]\n"
        'name = "Alice"\n'
        "age = 30\n"
        'city = "NYC"\n\n'
        "[[items]]\n"
        'name = "Bob"\n'
        "age = 25\n"
        'city = "SF"\n'
    )
    return toml_path


@pytest.fixture
def xml_file(tmp_path):
    """Create a test XML file."""
    xml_path = tmp_path / "test.xml"
    xml_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<root>\n"
        "  <item>\n"
        "    <name>Alice</name>\n"
        "    <age>30</age>\n"
        "    <city>NYC</city>\n"
        "  </item>\n"
        "  <item>\n"
        "    <name>Bob</name>\n"
        "    <age>25</age>\n"
        "    <city>SF</city>\n"
        "  </item>\n"
        "</root>\n"
    )
    return xml_path


@pytest.fixture
def csv_file(tmp_path):
    """Create a test CSV file."""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text(
        "name,age,city\n"
        "Alice,30,NYC\n"
        "Bob,25,SF\n"
    )
    return csv_path


class TestSourceAdapters:
    """Test source format adapters (reading files)."""

    def test_cat_yaml_file(self, runner, yaml_file):
        """Test cat with YAML file auto-detection."""
        result = runner.invoke(app, ["cat", str(yaml_file)])

        assert result.exit_code == 0

        # Parse NDJSON output
        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["age"] == 30
        assert first["city"] == "NYC"

        second = json.loads(lines[1])
        assert second["name"] == "Bob"

    def test_cat_toml_file(self, runner, toml_file):
        """Test cat with TOML file auto-detection."""
        result = runner.invoke(app, ["cat", str(toml_file)])

        assert result.exit_code == 0

        # Parse NDJSON output - TOML parser should extract the items array
        lines = result.output.strip().split("\n")

        # Parse the output to find items
        parsed = json.loads(lines[0])
        if "items" in parsed:
            items = parsed["items"]
            assert len(items) == 2
            assert items[0]["name"] == "Alice"
            assert items[1]["name"] == "Bob"

    def test_cat_xml_file(self, runner, xml_file):
        """Test cat with XML file auto-detection."""
        result = runner.invoke(app, ["cat", str(xml_file)])

        assert result.exit_code == 0

        # Parse NDJSON output
        lines = result.output.strip().split("\n")
        assert len(lines) >= 1

        # XML parser wraps content in a root dict
        parsed = json.loads(lines[0])
        assert "root" in parsed


class TestTargetAdapters:
    """Test target format adapters (writing files)."""

    def test_write_json_array(self, runner, tmp_path):
        """Test writing NDJSON to JSON array format."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.json"

        # Create jn.json config
        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "data",
                    "driver": "exec",
                    "exec": {
                        "argv": [
                            "python", "-c",
                            "import json; print(json.dumps({'x': 1})); print(json.dumps({'x': 2}))"
                        ]
                    }
                }
            ],
            "converters": [
                {
                    "name": "pass",
                    "engine": "jq",
                    "jq": {"expr": "."}
                }
            ],
            "targets": [
                {
                    "name": "file",
                    "driver": "file",
                    "file": {
                        "path": "out/output.json",
                        "mode": "write", "create_parents": True,
                        "allow_outside_config": False
                    }
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "data"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "file"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        # Run pipeline
        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Check output file
        assert output_file.exists()
        content = json.loads(output_file.read_text())

        # Should be a JSON array
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["x"] == 1
        assert content[1]["x"] == 2

    def test_write_jsonl(self, runner, tmp_path):
        """Test writing NDJSON to JSONL format."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.jsonl"

        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "data",
                    "driver": "exec",
                    "exec": {
                        "argv": [
                            "python", "-c",
                            "import json; print(json.dumps({'x': 1})); print(json.dumps({'x': 2}))"
                        ]
                    }
                }
            ],
            "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
            "targets": [
                {
                    "name": "file",
                    "driver": "file",
                    "file": {"path": "out/output.jsonl", "mode": "write", "create_parents": True}
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "data"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "file"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Check output - should be NDJSON (one object per line)
        assert output_file.exists()
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["x"] == 1
        assert json.loads(lines[1])["x"] == 2

    def test_write_csv(self, runner, tmp_path):
        """Test writing NDJSON to CSV format."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.csv"

        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "data",
                    "driver": "exec",
                    "exec": {
                        "argv": [
                            "python", "-c",
                            "import json; "
                            "print(json.dumps({'name': 'Alice', 'age': 30})); "
                            "print(json.dumps({'name': 'Bob', 'age': 25}))"
                        ]
                    }
                }
            ],
            "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
            "targets": [
                {
                    "name": "file",
                    "driver": "file",
                    "file": {"path": "out/output.csv", "mode": "write", "create_parents": True}
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "data"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "file"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Check CSV output
        assert output_file.exists()
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "name,age" in lines[0]
        assert "Alice,30" in lines[1]
        assert "Bob,25" in lines[2]

    def test_write_yaml(self, runner, tmp_path):
        """Test writing NDJSON to YAML format."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.yaml"

        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "data",
                    "driver": "exec",
                    "exec": {
                        "argv": [
                            "python", "-c",
                            "import json; "
                            "print(json.dumps({'name': 'Alice', 'age': 30})); "
                            "print(json.dumps({'name': 'Bob', 'age': 25}))"
                        ]
                    }
                }
            ],
            "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
            "targets": [
                {
                    "name": "file",
                    "driver": "file",
                    "file": {"path": "out/output.yaml", "mode": "write", "create_parents": True}
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "data"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "file"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Check YAML output
        assert output_file.exists()
        content = output_file.read_text()
        assert "Alice" in content
        assert "Bob" in content

    def test_roundtrip_csv_to_yaml(self, runner, tmp_path, csv_file):
        """Test round-trip: CSV → NDJSON → YAML."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.yaml"

        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "csv_source",
                    "driver": "file",
                    "file": {
                        "path": str(csv_file),
                        "mode": "read", "allow_outside_config": True
                    }
                }
            ],
            "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
            "targets": [
                {
                    "name": "yaml_target",
                    "driver": "file",
                    "file": {"path": "out/output.yaml", "mode": "write", "create_parents": True}
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "csv_source"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "yaml_target"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Verify YAML output contains CSV data
        assert output_file.exists()
        content = output_file.read_text()
        assert "Alice" in content
        assert "Bob" in content

    def test_empty_input_json(self, runner, tmp_path):
        """Test writing empty input to JSON (should be empty array)."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.json"

        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "empty",
                    "driver": "exec",
                    "exec": {"argv": ["echo", ""]}
                }
            ],
            "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
            "targets": [
                {
                    "name": "file",
                    "driver": "file",
                    "file": {"path": "out/output.json", "mode": "write", "create_parents": True}
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "empty"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "file"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Should be empty array for .json
        assert output_file.exists()
        content = json.loads(output_file.read_text())
        assert content == []

    def test_empty_input_csv(self, runner, tmp_path):
        """Test writing empty input to CSV (should be empty)."""
        config_file = tmp_path / "jn.json"
        output_file = tmp_path / "out" / "output.csv"

        config = {
            "version": "0.1", "name": "test", "sources": [
                {
                    "name": "empty",
                    "driver": "exec",
                    "exec": {"argv": ["echo", ""]}
                }
            ],
            "converters": [{"name": "pass", "engine": "jq", "jq": {"expr": "."}}],
            "targets": [
                {
                    "name": "file",
                    "driver": "file",
                    "file": {"path": "out/output.csv", "mode": "write", "create_parents": True}
                }
            ],
            "pipelines": [
                {
                    "name": "test",
                    "steps": [
                        {"type": "source", "ref": "empty"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "file"}
                    ]
                }
            ]
        }
        config_file.write_text(json.dumps(config))

        result = runner.invoke(app, ["run", "test", "--jn", str(config_file)])
        assert result.exit_code == 0

        # Should be empty for CSV
        assert output_file.exists()
        content = output_file.read_text()
        assert content == ""
