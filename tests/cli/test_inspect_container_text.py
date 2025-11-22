"""Outside-in tests for 'jn inspect' container text output.

Exercises container listing for HTTP profiles and human-readable formatting.
"""

import re


def test_inspect_http_container_text(invoke):
    """Inspect @testapi container and verify text output formatting."""
    # Profiles are provided under tests/jn_home/profiles/http/testapi
    # via the global JN_HOME fixture in tests/conftest.py.
    res = invoke(["inspect", "@testapi"])  # default format=text
    assert res.exit_code == 0, res.output

    out = res.output
    # New generic format: "Container: testapi (http)"
    assert "Container: testapi" in out
    assert "(http)" in out
    # Should list sources defined in test fixture
    assert re.search(r"\n\s*•\s*users\b", out)
    assert re.search(r"\n\s*•\s*projects\b", out)
