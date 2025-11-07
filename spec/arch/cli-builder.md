# ADR-001: Use the CLI to Build the CLI (JN “Junction” as a self-hosted pipeline builder)

**Status:** Proposed
**Owner:** JN core
**Date:** 2025-11-06

## Context

Anthropic’s “code execution with MCP” pattern argues for turning tools into code on disk so agents avoid shuttling giant schemas/results through model context. We’re building **jn** (Junction) to do that with a tiny, file-light, JSON/NDJSON + `jq` approach.
We also want **jn** to *build itself*: the same CLI should create, list, edit, test, and run **sources**, **targets**, **converters (jq)**, and **pipelines**. That keeps tokens and human effort low: the agent (or human) asks for short `jn ...` operations; the heavy lifting happens locally in code.

## Decision

1. **Single config file (`jn.json`) as source-of-truth**

   * Sections: `sources[]`, `targets[]`, `converters[]`, `pipelines[]`, optional `mcp.servers`.
   * JSON only; NDJSON over stdin/stdout between steps.

2. **CLI-first authoring workflow** (self-hosting)

   * `jn new source <name> --driver shell|curl|mcp --cmd/--url/--mcp-args`
   * `jn new target <name> ...`
   * `jn new converter <name> --jq-expr '...'` or `--file jq/filters/<name>.jq`
   * `jn new pipeline <name> --source S --convert C* --target T` (scaffold with params)
   * `jn edit <kind> <name>` (opens $EDITOR, validates on save)
   * `jn list/show <kind>` to browse inventory
   * `jn try <kind> <name> --param k=v` does a one-shot dry run with sample I/O
   * `jn test` runs jq goldens + pipeline smoke tests over dummy data

3. **Minimal, composable execution model**

   * `jn run <pipeline> --param k=v`: runs `source → (converter|pipeline)* → target` linearly.
   * Anything not JSON becomes JSON via an explicit **source wrapper** (e.g., `jc` or a `jq` prefilter), not by magic.
   * Parameters interpolate (`${params.x}`, `${env.X}`) into shell/curl templates and jq `--arg/--argjson`.

4. **Built-in scaffolds & docs**

   * Each `jn new` writes a stub plus embedded examples.
   * `jn explain <pipeline>` prints the resolved plan (no execution) for code review and agent visibility.

5. **Testing baked in**

   * `tests/data/*.ndjson` dummy fixtures; `jq --run-tests` goldens for converters; `jn test` runs end-to-end offline.

## Rationale

* **Token & latency savings:** the model asks for `jn` subcommands (tiny) instead of ingesting tool schemas and giant payloads. Intermediate data never enters the prompt.
* **Repeatability:** sources/targets/converters/pipelines are artifacts on disk, versioned, tested, and diffable.
* **Speed of iteration:** `jn new ...` scaffolds 90% of boilerplate; `jn try` accelerates local feedback loops for humans *and* agents.

## Alternatives Considered

* Heavy orchestrators (Airflow/Kestra/etc.): powerful, but overkill for ad-hoc, MCP-aware JSON pipes; also YAML-heavy and less agent-friendly.
* “Just let the agent write bash each time”: fast to start, brittle to reproduce, no shared library, no tests.

## Consequences

* A tiny CLI surface becomes the stable “API” that agents learn.
* Teams converge on **JSON/NDJSON + jq** as the only transform layer—easy to lint, test, and review.
* We can add optional features (schemas, validation gates, caching) without changing the basic authoring loop.

## Example UX

```bash
# create building blocks
jn new source github.repos --driver shell \
  --cmd 'curl -s https://api.github.com/users/${params.user}/repos'
jn new converter repos_to_post --jq-expr '{repos: map({name, html_url, stargazers_count})}'
jn new target httpbin.post --driver shell \
  --cmd "curl -s https://httpbin.org/post -H 'Content-Type: application/json' -d @-"

# stitch a pipeline
jn new pipeline github_to_httpbin --source github.repos --convert repos_to_post --target httpbin.post
jn run github_to_httpbin --param user=octocat | jq '.json.repos | length'
```
