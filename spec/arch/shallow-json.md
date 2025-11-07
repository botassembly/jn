# ADR-002: Automated “Shallow JSON Shape” + Schema/Preview Generation (deterministic, no LLM)

**Status:** Proposed
**Owner:** JN core
**Date:** 2025-11-06

## Problem

We often receive unseen JSON/NDJSON with large blobs (e.g., `content`), long arrays, and noisy fields. We need a **deterministic**, **automated** way (no LLM) to:

* infer a **schema** (types, nullability, enums, date/number detection),
* produce a **shallow preview** that trims heavy fields while conveying structure and examples,
* summarize arrays/objects compactly (first/mid/last), and
* emit outputs suitable for docgen, diffs, and quick human review (and agent consumption).

## Decision

Ship a Python utility (`jn shape`) that **streams** JSON/NDJSON and produces:

1. **Profile:** counts, type cardinalities, example values per field, min/max/avg lengths, histogram buckets (for numbers/lengths).
2. **Shallow Preview:** input structure with:

   * strings **truncated** (e.g., keep first 24 chars + `…` + `(len=NNN, sha256=…)`),
   * arrays **sampled** deterministically (first, middle, last; show counts),
   * objects pruned by depth (configurable), preserving keys,
   * binary/base64 heuristics replaced with `(bytes, len=..., sha256=...)`.
3. **Inferred JSON Schema** (Draft 2020-12):

   * union of observed simple types per field,
   * required vs optional,
   * format detection (date/datetime/uri/email/ip), numeric vs string-number,
   * enums for low-cardinality strings (≤K distinct),
   * additionalProperties policy configurable.

Everything is **deterministic**: stable key ordering (canonical JSON), seeded sampling (default seed 0), and fixed truncation rules.

## How (Implementation Notes)

* **Parsing/streaming:** `ijson` (streaming) or `orjson` for speed; support NDJSON line-by-line.
* **Schema inference:** start with **genson**-like merge logic or implement a simple merger; finalize with `jsonschema` for validation.
* **Date/number detection:** `python-dateutil` (strict parse with whitelist formats) + regex; treat ambiguous numerics conservatively.
* **Canonicalization:** emit **JCS**-like canonical JSON (sorted keys, no insignificant whitespace) for previews.
* **Hashing:** `sha256` of full original values when truncated to preserve referential identity.
* **Performance:** process N records with O(1) memory using streaming stats (Welford for mean/variance; HyperLogLog optional via `datasketch` for cardinality on large streams).

## Trimming & Summarization Strategies (mix-and-match)

1. **String truncation with metadata:** keep first *k* chars; add `(… len=, sha256=)`.
2. **Middle elision:** keep first *a*, last *b* chars (`"abc…xyz"`), annotate.
3. **Array abridgement:** `[ head, "… 30 skipped …", tail ]` + `(len=)`.
4. **Object depth cap:** show up to depth *D*; replace deeper levels with `{ … } (depth>D, keys=[k1,k2])`.
5. **Type collapsing:** show `"<number>"`, `"<boolean>"` for noisy leaves, with counts elsewhere in profile.
6. **Enum sampling:** if ≤K unique strings, show full set; else show top-N by frequency.
7. **Pattern hints:** detect email/phone/uuid and replace with tokens (`[EMAIL]`, `[PHONE]`, etc.) in preview only.
8. **Date bucketing:** bucket datetimes by day/hour; store min/max; preview shows representative ISO stubs.
9. **Numeric ranges:** show min/max/quantiles; replace long decimals with rounded preview.
10. **Blob heuristics:** base64/binary detectors → show `(bytes, len, sha256)` instead of payload.

## CLI UX

```bash
# Generate profile + schema + preview from NDJSON
jn shape --in tests/data/gdrive_docs.ndjson \
         --out profile.json --schema out.schema.json --preview preview.json \
         --truncate 24 --array-sample 1,mid,1 --depth 3 --seed 0

# Validate a stream against inferred schema (or provide your own)
cat data.ndjson | jn shape --validate schema.json
```

## Outputs

* **profile.json**: per-field metrics `{types, count, nulls, examples[], str_len{min/avg/max}, num{min/max}, enums?}`
* **preview.json**: one or a few representative “shallow” examples with annotations, canonicalized.
* **schema.json**: JSON Schema Draft 2020-12, with `type`, `oneOf`, `format`, `required`, `properties`.

## Libraries & Building Blocks (Python-first; others optional)

* Parse/stream: `ijson`, `orjson`
* Schema: `genson` (inference), `jsonschema` (validation)
* Dates: `dateutil`, `pendulum` (strict parsing)
* Cardinality/estimation: `datasketch` (HyperLogLog)
* Speedups (optional): `msgspec` (struct parsing), Rust FFI (e.g., simdjson via `pysimdjson`)

**Note:** jc is NOT a converter — it's a **source adapter** that converts shell output to JSON. See `spec/arch/adapters.md`.

## Determinism & Safety

* Stable seed controls sampling; previews are reproducible.
* No PII leaves the machine; previews can optionally **tokenize** detected sensitive fields.
* Previews annotate loss (`len=, skipped=, sha256=`) so you can reason about what was removed.

## Consequences

* Teams get a **compact, faithful picture** of unseen JSON—shape + key examples—without exposing payloads to a model.
* Agents can request “show me the shape of X” and receive a tiny, deterministic artifact (low token cost), then decide which fields to wire into converters.
* The same utility powers **tests** (assert schema hasn’t drifted) and **docs** (auto-generated “shape cards”).

---

If you want, I can turn both ADRs into repo files (`docs/adr-001.md`, `docs/adr-002.md`) and add a tiny `jn shape` Python prototype that streams NDJSON and emits the three artifacts exactly as specified.


