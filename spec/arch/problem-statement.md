# Tool Usage Context Challenge — Introduction

Agents need to execute real tools without dragging excessive context into the model window. This document explores patterns that let JN serve as a thin orchestration layer—composing existing CLIs and jq filters—while keeping prompts small and behavior deterministic.

We frame the challenge as: how can an agent discover available operations, preview exact execution (argv/env/cwd), and stream JSONL safely end-to-end, all without requiring the model to memorize tool-specific options or produce brittle shell strings?

Principles we adopt:
- Progressive disclosure: list only relevant items; show concrete next steps.
- Determinism: NDJSON boundaries; jq-only transforms; no hidden state.
- Exec-first safety: argv over shell; explicit env/cwd; redaction at display time.
- Streaming by default: OS pipes, no in-memory buffering.

The remainder of this doc details usage patterns, pitfalls (quoting, non-JSON chatter), and the design decisions in JN to make tool use reliable for agents.

