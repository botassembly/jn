# Agent Onboarding + Working Agreements

This repository already contains detailed context in [`CLAUDE.md`](CLAUDE.md). This `AGENTS.md` summarizes the fastest way for AI agents (and humans) to get productive plus a few workflow conventions.

## TL;DR expectations

1. **Start here** – Skim `CLAUDE.md`, then the top half of `README.md` so you know what JN does.
2. **Run commands from the repo root** – Most helper scripts assume `$PWD` is `/workspace/jn`. Use `PYTHONPATH=src` when invoking modules directly (e.g. `PYTHONPATH=src python -m jn.cli.main ...`).
3. **Prefer `uv` for Python tooling** – The project is wired for [uv](https://github.com/astral-sh/uv). You almost never need `pip`. Examples: `uv run pytest ...`, `uv run ruff check ...`.
4. **Baseline verification** – When the environment allows, run `make check`, `make test`, and `make coverage`. If one fails for unrelated long-standing reasons, note it in your summary instead of silently skipping it.
5. **Outside-in testing is valued** – Favor CLI/integration tests before drilling into unit tests. See `tests/cli/test_inspect_integration.py` for style cues.
6. **Document user-visible behavior** – If you add or change CLI UX, mention it in `README.md` or an appropriate doc inside `docs/` so newcomers can find it quickly.

## Handy commands

```bash
# Bootstrap dependencies (installs uv if missing, then resolves project deps)
make setup

# Lint, unit tests, and coverage rollups
make check
make test
make coverage

# Smoke-test inspect on the Homo sapiens gene-info dataset
PYTHONPATH=src python -m jn.cli.main \
  inspect "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz~csv?delimiter=auto" \
  --limit 1000 --format text
```

Keep this file updated whenever you discover a quicker path to productivity—the next agent will thank you.
