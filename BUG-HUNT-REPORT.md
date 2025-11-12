Bug Hunt Report — branch: bug-hunt

Summary
- Baseline: main is green (tests pass). Created fresh branch `bug-hunt`.
- Focus: exercise CLI, addressability, plugins, and profile flows with odd/edge inputs and remote data.
- Status: Several concrete issues found with clear repros below.

Findings (with repro)

1) run with stdin fails: missing ndjson plugin
- Repro:
  - printf '{"a":1}\n' | uv run python -m jn.cli.main run -- "-" "out.json"
  - Expected: convert NDJSON from stdin to out.json
  - Actual: Error: Plugin not found for format: ndjson
- Cause: AddressResolver treats stdio as format "ndjson" and tries to resolve a non-existent plugin. For stdin, the read side should be pass-through (no format plugin) or reuse json_ in an ndjson mode.

2) Parameter parsing misclassifies NaN/Inf and blames address syntax
- Repro:
  - printf '{"x":1}\n' | uv run python -m jn.cli.main put -- "-~json?indent=nan"
  - Actual: Error: Invalid address syntax: invalid literal for int() with base 10: 'nan'
- Cause: _build_config treats strings recognized by float() as numeric but then attempts int() if string lacks '.' or 'e'. 'nan'/'inf' pass float() but then int() raises. Also, the CLI catches ValueError as “Invalid address syntax,” which is misleading.
- Fix ideas: Treat nan/inf as floats or reject them explicitly; catch configuration-conversion errors separately from address parsing and surface helpful messages.

3) plugin call swallows stderr on failures (poor UX)
- Repro:
  - uv run python -m jn.cli.main plugin call xlsx_ --mode read  # no input
  - Exit code: 1, but no error output shown to the user.
- Cause: service.call_plugin pipes stderr but never streams/prints it when non‑zero exit; CLI just exits with the code.
- Impact: Hard to debug plugin invocation.
- Fix idea: On non‑zero, read and print stderr (or stream stderr to the terminal by default).

4) Negative counts for head/tail silently produce no output
- Repro:
  - printf '{"a":1}\n{"a":2}\n' | uv run python -m jn.cli.main head -n -5
  - Exit 0, no lines, no guidance.
- Suggestion: Validate n >= 0 and print a helpful error (discoverability/UX).

5) Dash addressing in examples requires `--` but help doesn’t mention it
- Repro:
  - printf '{"a":1}\n' | uv run python -m jn.cli.main put "-~json"
  - Click parses "-~" as an option → Error: No such option: -~
- Workaround: Use `--` before the argument: put -- "-~json" …
- Suggestion: Add `--` to examples and/or accept an explicit `--stdin` flag.

6) Plugin checker flags remain for gmail_/mcp_
- Repro:
  - uv run python -m jn.cli.main check plugins --verbose --format text
- Issues:
  - gmail_: missing_dependency for 'google' and 'googleapiclient' (PEP 723 name mapping mismatch)
  - mcp_: framework_import (imports jn.*) + missing_dependency for 'jn'
- Note: These look like intentional constraints/design tradeoffs but remain red in the checker.

7) Cross‑platform path assumptions in scanning and resolution
- Locations:
  - checker/scanner.py checks for "/__pycache__/" substring
  - addressing/resolver.py checks '"/formats/" in meta.path'
- On Windows, backslashes will bypass these string checks. Use Path.parts or os.sep-aware logic.

8) run: potential deadlock/hidden output for remote writer
- Code path: When writing to a protocol/profile destination, run() sets writer stdout to PIPE but never consumes it.
- Risk: If a writer emits output, it is lost; large output could fill the pipe and block.
- Suggestion: Stream or explicitly drain and log writer stdout.

9) run: binary writers vs text-mode file handles (cross‑platform)
- Code path: For local destinations, run() opens output files with "w" (text). Some writers (e.g., xlsx_) emit binary.
- On POSIX this typically works via FD redirection; on Windows, text mode could cause corruption (newline translation). Prefer binary mode when the writer is binary or when unknown.

10) AddressResolver.format fallback path search uses forward slashes
- Code path: _find_plugin_by_format() checks for "/formats/{name}" in meta.path. Backslashes on Windows may fail this test.
- Suggestion: Use Path(meta.path).parts and test directory names semantically.

Validated fixes in main
- XLSX-over-HTTP now works via two-stage pipeline (http raw → xlsx read). Re-tested CSV and XLSX URLs; both stream NDJSON as expected.
- http timeouts are returned as data for read mode; raw mode returns non‑zero (sensible distinction).

Next up (queued)
- Coverage + dead code sweep; propose deletions (outside-in philosophy).
- More adverse network trials: csv.gz, large JSONL, slow streams, flaky endpoints.
- Deeper profile exercising (http/jq/mcp) with malformed/missing configs.
- CLI discoverability pass: help text/HATEOAS, suggest next steps/errors.

