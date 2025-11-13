# Getting up to speed quickly

This page distills the steps new contributors (agents or humans) keep repeating when they sit down with JN for the first time. Pair it with [`AGENTS.md`](../AGENTS.md) and [`CLAUDE.md`](../CLAUDE.md) for the bigger picture.

## 1. Snapshot the lay of the land

1. **Skim `CLAUDE.md`** for the architecture, goals, and project map.
2. **Read the first half of `README.md`** (through "Core Commands") so you can answer "what does JN do?" in your own words.
3. **Take a peek at `docs/inspect.md`** to see what a polished `jn inspect` run looks like.

## 2. Install the tooling once

```bash
# Ensure uv is on PATH (installs it if missing)
pip install uv  # skip if uv is already present

# Clone and enter the repo
 git clone https://github.com/yourusername/jn.git
 cd jn

# Resolve dependencies and pre-commit hooks
make setup
```

`make setup` installs uv (when needed), syncs dependencies declared in `pyproject.toml`, and ensures shell helpers exist.

## 3. Daily workflow cheatsheet

```bash
# Lint, unit/integration tests, and coverage rollup
make check
make test
make coverage

# Run a single integration test module
PYTHONPATH=src uv run pytest tests/cli/test_inspect_integration.py -q

# Exercise the inspect CLI the way stakeholders expect
PYTHONPATH=src python -m jn.cli.main \
  inspect "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz~csv?delimiter=auto" \
  --limit 1000 --format text
```

If any of the `make` targets fail because of pre-existing lint/test flakes, capture the failure snippet (or chunk id) and include it in your status update. That transparency is preferred over silently skipping the command.

## 4. Known quirks (so you don't rediscover them)

| Area | Symptom | Mitigation |
| --- | --- | --- |
| Lint | `ruff` errors inside `checker/whitelist.py` and `cat.py` | They are tracked upstream; run `make check` anyway and mention the failure in your notes. |
| Tests | Watchfiles integration tends to hang in CI-like containers | Re-run with `pytest -k "not watchfiles"` if you need fast feedback; still report the original failure. |
| Plugins | When a fixture overrides `JN_HOME`, bundled plugins disappear | Use `PYTHONPATH=src python -m jn.cli.main ...` which re-injects bundled plugins automatically. |

## 5. When you touch UX

* Add or update the relevant doc in `docs/` (for example `docs/inspect.md`).
* Cross-link it from `README.md` so future explorers can find it.
* Mention any new smoke tests folks should run locally.

Keep this page honest—if you learn a better shortcut, amend it so the next person saves the time you just spent.
