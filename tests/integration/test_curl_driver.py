"""End-to-end tests for curl driver (HTTP sources and targets)."""

import json
import os

import pytest

from jn.cli import app
from tests.helpers import add_converter, add_pipeline, init_config


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_curl_source_httpbin_get(runner, tmp_path):
    """Test curl source with simple GET request to httpbin."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create curl source for httpbin /json endpoint
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "httpbin-json",
                "--url",
                "https://httpbin.org/json",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pass-through converter
        add_converter(runner, jn_path, "pass", ".")

        # Create cat target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "httpbin_test",
            ["source:httpbin-json", "converter:pass", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "httpbin_test", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "slideshow" in data


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_curl_source_with_headers(runner, tmp_path):
    """Test curl source with custom headers."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create curl source with custom headers
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "httpbin-headers",
                "--url",
                "https://httpbin.org/headers",
                "--header",
                "X-Custom-Header: test-value",
                "--header",
                "Accept: application/json",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create jq converter to extract headers
        add_converter(runner, jn_path, "extract-headers", ".headers")

        # Create cat target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "headers_test",
            [
                "source:httpbin-headers",
                "converter:extract-headers",
                "target:cat",
            ],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "headers_test", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        headers = json.loads(result.output.strip())
        assert headers["X-Custom-Header"] == "test-value"


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_curl_target_httpbin_post(runner, tmp_path):
    """Test curl target with POST to httpbin."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create echo source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "echo-data",
                "--argv",
                "echo",
                "--argv",
                '{"test":"data","value":42}',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pass-through converter
        add_converter(runner, jn_path, "pass", ".")

        # Create curl POST target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "curl",
                "httpbin-post",
                "--url",
                "https://httpbin.org/post",
                "--method",
                "POST",
                "--header",
                "Content-Type: application/json",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "post_test",
            ["source:echo-data", "converter:pass", "target:httpbin-post"],
        )

        # Run pipeline
        result = runner.invoke(app, ["run", "post_test", "--jn", str(jn_path)])

        assert result.exit_code == 0
        response = json.loads(result.output.strip())
        # httpbin echoes back the posted data
        posted_data = json.loads(response["data"])
        assert posted_data["test"] == "data"
        assert posted_data["value"] == 42


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_hn_to_httpbin_pipeline(runner, tmp_path):
    """Test end-to-end: HN Algolia API → jq filter → httpbin POST."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Source: HN Algolia API (top stories with > 100 points)
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "hn-top",
                "--url",
                "https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=points>100&hitsPerPage=5",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Converter: Extract just title, url, points from hits array
        add_converter(
            runner,
            jn_path,
            "hn-compact",
            ".hits[] | {title, url, points, author}",
        )

        # Target: POST to httpbin
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "curl",
                "httpbin",
                "--url",
                "https://httpbin.org/post",
                "--method",
                "POST",
                "--header",
                "Content-Type: application/x-ndjson",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "hn-to-httpbin",
            ["source:hn-top", "converter:hn-compact", "target:httpbin"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "hn-to-httpbin", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        response = json.loads(result.output.strip())
        # httpbin should have received NDJSON data
        assert "data" in response
        # The data should contain newline-separated JSON objects
        assert "\\n" in response["data"] or response["data"].count("{") >= 2


def test_curl_source_with_retry(runner, tmp_path):
    """Test curl source with retry configuration."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create curl source with retry settings
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "httpbin-retry",
                "--url",
                "https://httpbin.org/get",
                "--retry",
                "3",
                "--retry-delay",
                "1",
                "--timeout",
                "10",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Verify the config was saved with retry settings
        config_data = json.loads((tmp_path / "jn.json").read_text())
        source = next(
            s for s in config_data["sources"] if s["name"] == "httpbin-retry"
        )
        assert source["curl"]["retry"] == 3
        assert source["curl"]["retry_delay"] == 1
        assert source["curl"]["timeout"] == 10


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_curl_streaming_source(runner, tmp_path):
    """Test curl source with streaming endpoint (httpbin /stream/N)."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Source: httpbin streaming endpoint (10 JSON objects)
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "httpbin-stream",
                "--url",
                "https://httpbin.org/stream/10",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Converter: Pass through
        add_converter(runner, jn_path, "pass", ".")

        # Target: cat
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "stream-test",
            ["source:httpbin-stream", "converter:pass", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "stream-test", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        lines = [
            line for line in result.output.strip().split("\n") if line.strip()
        ]
        # Should have 10 JSON objects
        assert len(lines) == 10
        # Each should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "url" in data
            assert "headers" in data


def test_curl_source_404_error(runner, tmp_path):
    """Test curl source fails on 404 error."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create curl source that will return 404
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "httpbin-404",
                "--url",
                "https://httpbin.org/status/404",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create minimal pipeline
        add_converter(runner, jn_path, "pass", ".")
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        add_pipeline(
            runner,
            jn_path,
            "error-test",
            ["source:httpbin-404", "converter:pass", "target:cat"],
        )

        # Run pipeline - should fail
        result = runner.invoke(
            app, ["run", "error-test", "--jn", str(jn_path)]
        )

        assert result.exit_code == 1
        assert "404" in result.output or "error" in result.output.lower()


def test_curl_source_allow_errors(runner, tmp_path):
    """Test curl source with --allow-errors flag accepts 4xx/5xx."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create curl source with allow-errors flag
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "curl",
                "httpbin-404-ok",
                "--url",
                "https://httpbin.org/status/404",
                "--allow-errors",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Verify the config was saved with fail_on_error=false
        config_data = json.loads((tmp_path / "jn.json").read_text())
        source = next(
            s for s in config_data["sources"] if s["name"] == "httpbin-404-ok"
        )
        assert source["curl"]["fail_on_error"] is False


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_curl_source_template_substitution(runner, tmp_path):
    """Test curl source with ${env.*} template substitution in headers."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Manually create source with template in config
        config_data = json.loads((tmp_path / "jn.json").read_text())
        config_data["sources"].append(
            {
                "name": "httpbin-auth",
                "driver": "curl",
                "mode": "stream",
                "adapter": None,
                "curl": {
                    "method": "GET",
                    "url": "https://httpbin.org/bearer",
                    "headers": {"Authorization": "Bearer ${env.TEST_TOKEN}"},
                    "body": None,
                    "timeout": 30,
                    "follow_redirects": True,
                    "retry": 0,
                    "retry_delay": 2,
                    "fail_on_error": True,
                },
            }
        )
        (tmp_path / "jn.json").write_text(json.dumps(config_data, indent=2))

        # Create converter to extract token
        add_converter(runner, jn_path, "extract-token", ".token")

        # Create cat target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "auth-test",
            ["source:httpbin-auth", "converter:extract-token", "target:cat"],
        )

        # Run pipeline with env var
        result = runner.invoke(
            app,
            [
                "run",
                "auth-test",
                "--env",
                "TEST_TOKEN=my-secret-token-123",
                "--jn",
                str(jn_path),
            ],
        )

        assert result.exit_code == 0
        # httpbin /bearer should echo back the token
        assert "my-secret-token-123" in result.output


@pytest.mark.skipif(
    os.getenv("JN_OFFLINE") == "1",
    reason="Network test disabled in offline mode",
)
def test_curl_source_with_body(runner, tmp_path):
    """Test curl source with POST method and request body (e.g., GraphQL)."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Manually create POST source with body in config
        config_data = json.loads((tmp_path / "jn.json").read_text())
        config_data["sources"].append(
            {
                "name": "graphql-mock",
                "driver": "curl",
                "mode": "stream",
                "adapter": None,
                "curl": {
                    "method": "POST",
                    "url": "https://httpbin.org/post",
                    "headers": {"Content-Type": "application/json"},
                    "body": '{"query":"${params.query}","variables":{}}',
                    "timeout": 30,
                    "follow_redirects": True,
                    "retry": 0,
                    "retry_delay": 2,
                    "fail_on_error": True,
                },
            }
        )
        (tmp_path / "jn.json").write_text(json.dumps(config_data, indent=2))

        # Create converter to extract posted data
        add_converter(runner, jn_path, "extract-data", ".data")

        # Create cat target
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "exec",
                "cat",
                "--argv",
                "cat",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "post-source-test",
            ["source:graphql-mock", "converter:extract-data", "target:cat"],
        )

        # Run pipeline with query param
        result = runner.invoke(
            app,
            [
                "run",
                "post-source-test",
                "--param",
                "query={ viewer { login } }",
                "--jn",
                str(jn_path),
            ],
        )

        assert result.exit_code == 0
        # httpbin /post echoes back the posted body in the "data" field
        # Verify our templated query made it through
        assert "viewer" in result.output
        assert "login" in result.output
