from click.testing import CliRunner

from jn.cli import cli


def test_http_profile_invalid_json_in_meta(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create project profile path: .jn/profiles/http/myapi/_meta.json (invalid JSON)
        from pathlib import Path

        profile_dir = Path(".jn/profiles/http/myapi")
        profile_dir.mkdir(parents=True, exist_ok=True)
        meta = profile_dir / "_meta.json"
        meta.write_text("{ invalid json }")

        result = runner.invoke(cli, ["cat", "@myapi/source"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Profile" in result.output or "Invalid JSON" in result.output


def test_http_profile_missing_source(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Valid _meta, missing source file
        from pathlib import Path

        profile_dir = Path(".jn/profiles/http/myapi")
        profile_dir.mkdir(parents=True, exist_ok=True)
        meta = profile_dir / "_meta.json"
        meta.write_text("{" "base_url" ": " "https://example.com" "}")

        result = runner.invoke(cli, ["cat", "@myapi/missing"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert (
            "Source not found" in result.output or "Profile" in result.output
        )


def test_http_profile_missing_env_var_in_headers(tmp_path, monkeypatch):
    runner = CliRunner()
    with runner.isolated_filesystem():
        # _meta uses env var substitution in headers
        from pathlib import Path

        profile_dir = Path(".jn/profiles/http/secureapi")
        profile_dir.mkdir(parents=True, exist_ok=True)
        meta = profile_dir / "_meta.json"
        meta.write_text(
            '{"base_url": "https://example.com", "headers": {"Authorization": "${MISSING_TOKEN}"}}'
        )
        # Provide a minimal source so loader doesn't fail for missing source
        (profile_dir / "source.json").write_text("{}")

        # No env var set

        result = runner.invoke(cli, ["cat", "@secureapi/source"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Environment variable" in result.output
