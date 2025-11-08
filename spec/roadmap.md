# Roadmap — Outside‑In CLI Build (JN vNext)

> Rule: write the CLI test first (Typer CliRunner), watch it fail, implement the smallest slice underneath (config/drivers), keep tests green, repeat. ≤3 imports per CLI module.

* [x] Bootstrap checks — `make check`
* [x] Pytest smoke — `make test`
* [x] CLI skeleton — `jn --help`
* [x] Init command — `jn init`
* [x] List items — `jn list <kind>`
* [x] Show item — `jn show <kind> <name>`
* [x] New source — `jn new source <driver>` (exec implemented end-to-end; other drivers parsed only)
* [x] New converter — `jn new converter`
* [x] New target — `jn new target <driver>` (exec implemented end-to-end)
* [x] New pipeline — `jn new pipeline <name> --steps <steps>`
* [x] Explain plan — `jn explain <pipeline>`
* [x] Explain env — `jn explain <pipeline> --show-env`
* [x] Explain cmds — `jn explain <pipeline> --show-commands`
* [x] Run pipeline — `jn run <pipeline>` (exec → jq → exec happy-path)
* [x] Run with env — `jn run <pipeline> --env <K=V>` (CLI flag working, tests passing)
* [x] Run with params — `jn run <pipeline> --param <k=v>` (CLI flag working, tests passing)
* [x] Exec source extras — support `cwd`/`env` interpolation in run/explain (fully working)
* [x] Shell driver — implement safe execution + opt-in flag (PR #7: src/jn/drivers/shell.py with --unsafe-shell guard)
* [ ] Curl driver — streaming HTTP client for sources/targets (architecture: spec/arch/http-client.md)
* [x] File driver — streaming file read/write with confinement (src/jn/drivers/file.py, 81% coverage)
* [ ] CSV/delimited source — `jn new source <name> --driver file --adapter csv` (architecture: spec/arch/csv-delimited.md)
* [x] JC source adapter — wrap shell output to JSON (PR #7: adapter="jc" prepends jc to argv, 9 tests)
* [x] Pipeline params/env templating — `${params.*}` and `${env.*}` expansion (src/jn/config/utils.py:substitute_template)
* [ ] Plan mode — `jn run <pipeline> --plan` dry-run introspection (architecture: spec/arch/plan-mode.md)
* [ ] Try command — `jn try source/converter/target` ad-hoc testing (architecture: spec/arch/try-command.md)
* [ ] Help improvements — example-driven help text for all commands (architecture: spec/arch/help-system.md)
* [ ] Exit code conventions — standardized exit codes for automation (architecture: spec/arch/exit-codes.md)
* [ ] Doctor check — `jn doctor` (scope TBD: health checks for jq/jc, config validation, pipeline refs)
* [ ] Discover list — `jn discover` (scope TBD: parsers? tools? data files?)
* [ ] Shape stream — `jn shape --in <path>` (architecture: spec/arch/shape-command.md + spec/arch/shallow-json.md ADR)
* [ ] MCP import — `jn mcp import <server>`
* [ ] MCP driver — `jn new source|target <name> --driver mcp`
* [ ] Edit item — `jn edit <kind> <name>`
* [ ] Remove item — `jn rm <kind> <name>`
* [ ] Release smoke — `jn --version`

> Keep each step green: commit after each passing test; do not add new commands without a failing test that names the exact CLI you’re about to build.

