import io


def test_put_stdout_xlsx(invoke, sample_ndjson):
    """Writing XLSX to stdout works under Click runner."""
    res = invoke(["put", "--", "-~xlsx"], input_data=sample_ndjson)
    assert res.exit_code == 0, res.output

    # Validate bytes look like an XLSX zip (PK header)
    out_bytes = (
        res.stdout_bytes
        if hasattr(res, "stdout_bytes")
        else res.output.encode("latin-1")
    )
    assert out_bytes[:2] == b"PK"
