"""Integration tests for shell driver."""

import json

from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_target,
    add_pipeline,
    init_config,
)


def test_shell_source_blocked_without_unsafe_flag(
    runner, tmp_path, pass_converter, cat_target
):
    """Test that shell source fails without --unsafe-shell flag."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create shell source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "shell",
                "echo_shell",
                "--cmd",
                "echo '{\"x\": 1}'",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "shell_pipeline",
            ["source:echo_shell", "converter:pass", "target:cat"],
        )

        # Run without --unsafe-shell (should fail)
        result = runner.invoke(
            app, ["run", "shell_pipeline", "--jn", str(jn_path)]
        )

    assert result.exit_code == 1
    assert "shell driver requires --unsafe-shell" in result.output


def test_shell_source_works_with_unsafe_flag(
    runner, tmp_path, pass_converter, cat_target
):
    """Test that shell source works with --unsafe-shell flag."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create shell source that outputs JSON
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "shell",
                "echo_shell",
                "--cmd",
                'python -c "import json; print(json.dumps({\\"x\\": 1})); print(json.dumps({\\"x\\": 2}))"',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "shell_pipeline",
            ["source:echo_shell", "converter:pass", "target:cat"],
        )

        # Run with --unsafe-shell (should succeed)
        result = runner.invoke(
            app,
            ["run", "shell_pipeline", "--unsafe-shell", "--jn", str(jn_path)],
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"x": 1}
    assert json.loads(lines[1]) == {"x": 2}


def test_shell_target_works_with_unsafe_flag(
    runner, tmp_path, echo_source, pass_converter
):
    """Test that shell target works with --unsafe-shell flag."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        output_file = tmp_path / "output.txt"
        init_config(runner, jn_path)

        # Create exec source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "echo",
                "--argv",
                "python",
                "--argv",
                "-c",
                "--argv",
                'import json; print(json.dumps({"test": "value"}))',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")

        # Create shell target that writes to file
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "shell",
                "write_shell",
                "--cmd",
                f"cat > {output_file}",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_pipeline(
            runner,
            jn_path,
            "shell_target_pipeline",
            ["source:echo", "converter:pass", "target:write_shell"],
        )

        # Run with --unsafe-shell
        result = runner.invoke(
            app,
            [
                "run",
                "shell_target_pipeline",
                "--unsafe-shell",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    assert output_file.exists()
    content = output_file.read_text().strip()
    assert json.loads(content) == {"test": "value"}


def test_shell_source_with_templating(
    runner, tmp_path, pass_converter, cat_target
):
    """Test that shell source supports ${params.*} templating."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create shell source with parameter templating
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "shell",
                "echo_param",
                "--cmd",
                'python -c "import json; print(json.dumps({\\"msg\\": \\"${params.message}\\"}))"',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "param_pipeline",
            ["source:echo_param", "converter:pass", "target:cat"],
        )

        # Run with --param
        result = runner.invoke(
            app,
            [
                "run",
                "param_pipeline",
                "--param",
                "message=hello from shell",
                "--unsafe-shell",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"msg": "hello from shell"}


def test_shell_source_with_env_templating(
    runner, tmp_path, pass_converter, cat_target
):
    """Test that shell source supports ${env.*} templating."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create shell source with env templating
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "shell",
                "echo_env",
                "--cmd",
                'python -c "import json; print(json.dumps({\\"token\\": \\"${env.SECRET}\\"}))"',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "env_pipeline",
            ["source:echo_env", "converter:pass", "target:cat"],
        )

        # Run with --env
        result = runner.invoke(
            app,
            [
                "run",
                "env_pipeline",
                "--env",
                "SECRET=my_secret_value",
                "--unsafe-shell",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"token": "my_secret_value"}


def test_shell_source_with_jc_adapter(
    runner, tmp_path, pass_converter, cat_target
):
    """Test that shell source with jc adapter prepends 'jc' to command."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create a mock 'jc' command that simulates jc's behavior
        mock_jc_dir = tmp_path / "bin"
        mock_jc_dir.mkdir()
        mock_jc_script = mock_jc_dir / "jc"
        mock_jc_script.write_text(
            """#!/usr/bin/env python3
import sys
import json
import subprocess

# Get the command (everything after 'jc')
command = " ".join(sys.argv[1:])

# Run the command via shell
result = subprocess.run(command, shell=True, capture_output=True, text=True)

# Wrap output as if jc parsed it
output_lines = result.stdout.strip().split('\\n')
json_output = [{"line": line} for line in output_lines if line]
print(json.dumps(json_output))
"""
        )
        mock_jc_script.chmod(0o755)

        # Create shell source with jc adapter
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "shell",
                "echo_with_jc",
                "--adapter",
                "jc",
                "--cmd",
                "echo hello",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_converter(runner, jn_path, "pass", pass_converter.jq.expr or ".")
        add_exec_target(runner, jn_path, "cat", cat_target.exec.argv)
        add_pipeline(
            runner,
            jn_path,
            "jc_shell_pipeline",
            ["source:echo_with_jc", "converter:pass", "target:cat"],
        )

        # Run with --unsafe-shell and our mock jc in PATH
        import os

        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{mock_jc_dir}:{old_path}"
        try:
            result = runner.invoke(
                app,
                [
                    "run",
                    "jc_shell_pipeline",
                    "--unsafe-shell",
                    "--jn",
                    str(jn_path),
                ],
            )
        finally:
            os.environ["PATH"] = old_path

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    output = result.output.strip()
    # The output should be JSON array with one object containing "line": "hello"
    parsed = json.loads(output)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["line"] == "hello"
