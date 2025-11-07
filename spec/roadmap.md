# Roadmap — Outside‑In CLI Build (JN vNext)

> Rule: write the CLI test first (Typer CliRunner), watch it fail, implement the smallest slice underneath (service/drivers), keep tests green, repeat. 2–3 imports max per CLI module.

* [ ] Bootstrap checks — `make check`
* [ ] Pytest smoke — `pytest <first-test>`
* [ ] CLI skeleton — `jn --help`
* [ ] Init command — `jn init`
* [ ] List items — `jn list <kind>`
* [ ] Show item — `jn show <kind> <name>`
* [ ] New source — `jn new source <name> --driver <driver>`
* [ ] New converter — `jn new converter <name> --engine <engine>`
* [ ] New target — `jn new target <name> --driver <driver>`
* [ ] New pipeline — `jn new pipeline <name> --steps <steps>`
* [ ] Explain plan — `jn explain <pipeline>`
* [ ] Explain env — `jn explain <pipeline> --show-env`
* [ ] Explain cmds — `jn explain <pipeline> --show-commands`
* [ ] Run pipeline — `jn run <pipeline>`
* [ ] Run with env — `jn --env <K=V> run <pipeline>`
* [ ] Run with params — `jn run <pipeline> --param <k=v>`
* [ ] Source run — `jn source run <name>`
* [ ] Target run — `jn target run <name>`
* [ ] Convert run — `jn convert <name>`
* [ ] Edit item — `jn edit <kind> <name>`
* [ ] Remove item — `jn rm <kind> <name>`
* [ ] File source — `jn new source <name> --driver file`
* [ ] File target — `jn new target <name> --driver file`
* [ ] Curl source — `jn new source <name> --driver curl`
* [ ] Curl target — `jn new target <name> --driver curl`
* [ ] Exec source — `jn new source <name> --driver exec`
* [ ] Exec target — `jn new target <name> --driver exec`
* [ ] JC CSV conv — `jn new converter <name> --engine jc --parser csv-s`
* [ ] JC other conv — `jn new converter <name> --engine jc --parser <parser>`
* [ ] Jiter recover — `jn new converter <name> --engine jiter`
* [ ] Delimited conv — `jn new converter <name> --engine delimited`
* [ ] CSV pipeline — `jn new pipeline <name> --steps <csv-steps>`
* [ ] Doctor check — `jn doctor`
* [ ] Discover list — `jn discover`
* [ ] Shape stream — `jn shape --in <path>`
* [ ] Try building — `jn try <kind> <name>`
* [ ] MCP import — `jn mcp import <server>`
* [ ] MCP source — `jn new source <name> --driver mcp`
* [ ] MCP target — `jn new target <name> --driver mcp`
* [ ] Redacted env — `jn explain <pipeline> --show-env`
* [ ] Lint imports — `uv run lint-imports --config importlinter.ini`
* [ ] Coverage run — `make coverage`
* [ ] Release smoke — `jn --version`

> Keep each step green: commit after each passing test; do not add new commands without a failing test that names the exact CLI you’re about to build.

