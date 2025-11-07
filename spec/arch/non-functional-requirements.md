1. **True streaming, O(1) memory**

* **Must:** Pass bytes through OS pipes end-to-end; never materialize full payloads in Python.
* **Accept:** Run a 10+ GiB CSV → jc(csv-s) → jq → sink; RSS stays <150 MB, no Python buffering.

2. **Backpressure propagation**

* **Must:** Use connected pipes so slow downstream throttles upstream automatically.
* **Accept:** Throttle target to <1 MB/s; source throughput drops accordingly without internal queues.

3. **Binary-safe I/O**

* **Must:** Read/write **bytes** only on hot paths; no `decode()` during streaming.
* **Accept:** Inject non-UTF-8 bytes; pipeline completes; only transforms that require UTF-8 (jq) surface errors, not JN.

4. **Encoding & Unicode discipline**

* **Must:** Default UTF-8 for text decodes; support explicit `--encoding` on file reads; preserve BOM; normalize line endings.
* **Accept:** Files with UTF-8, UTF-16LE/BE (with BOM), ISO-8859-1 round-trip or decode per flag; CRLF handled.

5. **Large file & long-lived stream robustness**

* **Must:** No duration-based degradation; file driver uses chunked read/write; retryable writes for targets when safe.
* **Accept:** 24-hour stream shows no memory creep; open FDs stable; log rotation doesn’t break runs.

6. **Determinism & reproducibility**

* **Must:** Deterministic plans and outputs for same inputs; stable key ordering in machine outputs intended for diffing.
* **Accept:** `explain --json` identical across runs; shape/sampler (when present) uses fixed seed.

7. **Structured failures by default**

* **Must:** Emit compact JSON error envelopes (`step,name,exit,stderr,hint`); human pretty mode opt-in.
* **Accept:** Kill any stage; CLI returns envelope with actionable “Next:” hints; exit codes non-zero.

8. **Timeouts & retries**

* **Must:** Per-step configurable timeouts; optional small retry policy for curl/exec targets with backoff.
* **Accept:** Induced network stall triggers timeout within configured window; target retries N times then fails.

9. **Resource limits & safety rails**

* **Must:** Bounded buffering for **batch** stages (`JN_BUFFER_LIMIT_BYTES`, default 256 MiB); FD, subprocess limits; safe cleanup.
* **Accept:** Oversized batch exceeds limit → clear error before OOM; no zombie processes after failure.

10. **Secret hygiene**

* **Must:** No secrets in plan/trace unless explicitly allowed; automatic redaction in `explain --show-env`; masked logs.
* **Accept:** Provide `--env FOO=secret` and `--show-env`; output shows `FOO: ******`.

11. **Exec-first, shell-guarded**

* **Must:** Prefer `driver: exec`; `driver: shell` requires explicit `--unsafe-shell` flag in run context; argv shown verbatim in explain.
* **Accept:** Attempt shell without flag → fails with remediation; exec paths work by default.

12. **Path confinement for file driver**

* **Must:** Option to confine reads/writes to project dir; default deny traversal outside unless opt-in.
* **Accept:** `../../` path rejected when confinement enabled; enabling flag allows with explicit warning.

13. **Dependency hardening**

* **Must:** Preflight checks (`jn doctor`): presence/versions of `jq` (required), optional `jc` (source adapter)/`curl` (HTTP driver); clear remediation.
* **Accept:** Missing `jq` → preflight stops before run with single-screen checklist.
* **Note:** `jc` is a source adapter (shell → JSON), not a converter. See `spec/arch/adapters.md`.

14. **Observability & minimal metrics**

* **Must:** Print compact flow stats: per-step records/bytes and total elapsed; optional JSON metrics.
* **Accept:** `source: N | jc: N | jq: N | target: M (t=1.8s, bytes=…)` at end of run; toggle off via flag.

15. **Concurrency & isolation**

* **Must:** Multiple pipelines may run concurrently without state collision; temp files uniquely named; no global mutables.
* **Accept:** Launch 4 parallel runs; outputs correct; no temp-file clashes; CPU scales linearly until saturation.

16. **Config precedence & testability**

* **Must:** `--jn` > `JN_PATH` > `./.jn.json|jn.json` > `~/.jn.json`; `config.set_config()` for tests; no hidden state.
* **Accept:** Unit test can inject a Project object; all CLI commands honor it.

17. **Format coverage via source adapters**

* **Must:** Support CSV/TSV/etc. as **sources** (via file driver with CSV parser or jc streaming parsers); not as converters.
* **Accept:** CSV with quoted commas and multiline fields parses correctly; TSV via delimiter config works; error rows flagged.
* **Note:** CSV/delimited is a source type, not a converter. jq is the only converter.

18. **Partial JSON recovery (jiter)**

* **Status:** Deferred / not planned for initial releases
* **Note:** Jiter is NOT a converter. It would be a recovery tool for malformed JSON, but is not currently in scope.

19. **Cross-platform portability**

* **Must:** Linux/macOS/Windows (including WSL) support; no bash-isms in tests; path handling normalized.
* **Accept:** Core e2e tests pass on all three; file driver respects platform semantics.

20. **Architecture contract & linting**

* **Must:** Enforce `cli → config → home` layering; no upward imports from `home`; max imports per CLI file (≤3).
* **Accept:** Import-linter passes; CI fails on violations; spot checks show CLI files are thin.

If you want, I can turn this into a `spec/nfr.md` with a one-line “how to test” under each item and wire a small `jn doctor` checklist to enforce #10–#13 automatically.

