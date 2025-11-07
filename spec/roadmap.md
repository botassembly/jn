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
* [ ] Run with env — `jn --env <K=V> run <pipeline>`
* [ ] Run with params — `jn run <pipeline> --param <k=v>`
* [ ] Exec source extras — support `cwd`/`env` interpolation in run/explain (partial today)
* [ ] Shell driver — implement safe execution + opt-in flag
* [ ] Curl driver — streaming HTTP client for sources/targets
* [ ] File driver — streaming file read/write with confinement
* [ ] CSV/delimited source — `jn new source <name> --driver file --format csv`
* [ ] JC source adapter — wrap shell output to JSON (registered parsers, "magic" syntax)
* [ ] Pipeline params/env templating — `${params.*}` and `${env.*}` expansion
* [ ] Doctor check — `jn doctor`
* [ ] Discover list — `jn discover`
* [ ] Shape stream — `jn shape --in <path>`
* [ ] Try building — `jn try <kind> <name>`
* [ ] MCP import — `jn mcp import <server>`
* [ ] MCP driver — `jn new source|target <name> --driver mcp`
* [ ] Edit item — `jn edit <kind> <name>`
* [ ] Remove item — `jn rm <kind> <name>`
* [ ] Release smoke — `jn --version`

> Keep each step green: commit after each passing test; do not add new commands without a failing test that names the exact CLI you’re about to build.

