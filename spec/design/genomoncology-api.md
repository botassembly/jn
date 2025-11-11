# GenomOncology API Integration - Design

## Overview

Real-world example of JN's sources/filters/targets architecture using the GenomOncology Precision Medicine API. Demonstrates:
- **Sources:** API endpoints that fetch data
- **Filters:** Transformations and pivots
- **Targets:** Output formats (CSV, tables, JSON)
- **Profiles:** Clean `@genomoncology/endpoint` syntax

## GenomOncology API

Precision medicine platform providing:
- **Alterations:** Genetic variants database (55,000+ entries)
- **Annotations:** Variant clinical significance
- **Clinical Trials:** Trial matching for biomarkers
- **Therapies:** Treatment options by alteration
- **Genes, Diseases:** Ontologies and relationships

**Base URL:** `https://${GENOMONCOLOGY_URL}/api`

## Sources/Filters/Targets Architecture

### Core Concept

**Source** = Endpoint + Method + Optional Built-in Filter

```
Source: @genomoncology/alterations
  ├─ URL: https://${GENOMONCOLOGY_URL}/api/alterations
  ├─ Method: GET
  ├─ Params: gene, mutation_type, ...
  └─ Filters: extract-fields, filter-by-gene, ...
```

**Pipeline:**
```
source → filter → filter → filter → target
```

**Example:**
```bash
jn cat @genomoncology/alterations | \          # Source
  jn filter '.gene == "BRAF"' | \               # Filter 1
  jn filter '{name, mutation_type}' | \         # Filter 2
  jn put results.csv                            # Target
```

### Sources vs Filters vs Targets

| Component | Role | Example |
|-----------|------|---------|
| **Source** | Fetch data | `jn cat @genomoncology/alterations` |
| **Filter** | Transform | `jn filter '.gene == "BRAF"'` |
| **Target** | Output | `jn put results.csv` |

**Chaining:**
- Source + Filter = Still conceptually a "source" (emits data)
- Multiple filters can chain
- Target is always last (consumes data)

## GenomOncology Profile

### Basic Profile Structure

```json
{
  "base_url": "https://${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}",
    "Accept": "application/json"
  },
  "timeout": 60
}
```

**Environment Variables:**
```bash
export GENOMONCOLOGY_URL="your-server.genomoncology.io"
export GENOMONCOLOGY_API_KEY="your-api-token-here"
```

### Sources Configuration

```json
{
  "base_url": "https://${GENOMONCOLOGY_URL}/api",
  "headers": {...},
  "sources": {
    "alterations": {
      "path": "/alterations",
      "method": "GET",
      "params": ["gene", "mutation_type", "biomarker"],
      "description": "Genetic alterations database (55,000+ entries)",
      "filters": {
        "extract-fields": "@genomoncology/filters/extract-alterations"
      }
    },
    "annotations": {
      "path": "/annotations",
      "method": "GET",
      "description": "Variant annotations with clinical significance",
      "filters": {
        "pivot-transcripts": "@genomoncology/filters/pivot-transcripts",
        "extract-hgvs": "@genomoncology/filters/extract-hgvs"
      }
    },
    "annotations_match": {
      "path": "/annotations/match",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "description": "Batch variant matching",
      "note": "POST due to large batch parameter in body"
    },
    "clinical_trials": {
      "path": "/clinical_trials",
      "method": "GET",
      "params": ["disease", "alteration", "status"],
      "description": "Clinical trial matching"
    }
  }
}
```

## Source Examples

### 1. Alterations Source

**Simple fetch:**
```bash
jn cat @genomoncology/alterations | head -n 10
```

**With API filtering:**
```bash
# Filter at API level (efficient - less data transferred)
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense"
```

**With JN filtering:**
```bash
# Filter after fetch (flexible - can filter on any field)
jn cat @genomoncology/alterations | \
  jn filter '.gene == "BRAF" and .mutation_type_group == "Missense"'
```

**Combined (API + JN filters):**
```bash
# API filter reduces data transfer
# JN filter adds complex logic
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '.p_start >= 600 and .p_start <= 700'
```

### 2. Annotations Source with Pivot

**Challenge:** Annotations return nested structure:
```json
{
  "uuid": "abc123",
  "gene": ["BRAF"],
  "hgvs_g": "chr7:g.140453136A>T",
  "hgvs_c": ["NM_004333.4:c.1799T>A", "NM_004333.5:c.1799T>A"],
  "hgvs_p": ["NP_004324.2:p.Val600Glu", "NP_004324.3:p.Val600Glu"],
  "transcript_id": ["NM_004333.4", "NM_004333.5"]
}
```

**Goal:** Pivot to one row per transcript.

**Pivot filter:** `@genomoncology/filters/pivot-transcripts`

```bash
jn cat @genomoncology/annotations | \
  jn filter '@genomoncology/filters/pivot-transcripts'
```

**Output:**
```json
{"uuid": "abc123", "gene": "BRAF", "transcript": "NM_004333.4", "hgvs_c": "NM_004333.4:c.1799T>A", "hgvs_p": "NP_004324.2:p.Val600Glu"}
{"uuid": "abc123", "gene": "BRAF", "transcript": "NM_004333.5", "hgvs_c": "NM_004333.5:c.1799T>A", "hgvs_p": "NP_004324.3:p.Val600Glu"}
```

**Why source-specific filter?**
- Pivot logic only makes sense for annotations
- Complex transformation (nested arrays → rows)
- Tied to API response structure

### 3. Clinical Trials Source

**Match trials by alteration:**
```bash
# Find trials for BRAF V600E in melanoma
jn cat "@genomoncology/clinical_trials?alteration=BRAF+V600E&disease=Melanoma"
```

**Chain filters for complex matching:**
```bash
jn cat "@genomoncology/clinical_trials?alteration=BRAF+V600E" | \
  jn filter '.disease_details | contains("melanoma")' | \
  jn filter '.status == "Recruiting"' | \
  jn filter '{nct_id, title, status, phase}'
```

### 4. POST Source (Annotations Match)

**Challenge:** Batch matching requires POST with large body.

**Example:**
```bash
# Create batch payload
echo 'batch=chr7|140453136|A|T|GRCh37&batch=NM_005228.3:c.2239_2241delTTA' | \
  jn cat @genomoncology:annotations_match --method POST
```

**Why POST?** Can submit hundreds of variants in body, exceeds URL length limits.

## Source-Specific Filters

### Concept

Some filters only apply to specific sources. These are tied to the API's response structure.

**Example: Annotations Filters**

```json
{
  "sources": {
    "annotations": {
      "filters": {
        "pivot-transcripts": {
          "filter": "@genomoncology/filters/pivot-transcripts",
          "description": "Pivot to one row per transcript (HGVS c/p pairs)"
        },
        "extract-hgvs": {
          "filter": "@genomoncology/filters/extract-hgvs",
          "description": "Extract HGVS notations (g, c, p)"
        }
      }
    }
  }
}
```

**Usage:**
```bash
# Apply source-specific filter
jn cat @genomoncology/annotations | \
  jn filter '@genomoncology/annotations:pivot-transcripts'

# Chain multiple source-specific filters
jn cat @genomoncology/annotations | \
  jn filter '@genomoncology/annotations:pivot-transcripts' | \
  jn filter '@genomoncology/annotations:extract-hgvs'
```

**Why?**
- Annotations have complex nested arrays
- Pivot/extract logic is specific to this API
- Wouldn't make sense to apply to alterations or clinical trials

### Bundled Filters

Located in: `jn_home/profiles/jq/genomoncology/filters/`

**`pivot-transcripts.jq`:**
```jq
# Pivot nested transcript arrays to rows
. as $base |
.transcript_id as $transcripts |
.hgvs_c as $hgvs_c_list |
.hgvs_p as $hgvs_p_list |
$transcripts | to_entries | map({
  uuid: $base.uuid,
  gene: ($base.gene[0] // null),
  chr: $base.chr,
  position: $base.position,
  ref: $base.ref,
  alt: ($base.alt // null),
  transcript: .value,
  hgvs_c: ($hgvs_c_list[.key] // null),
  hgvs_p: ($hgvs_p_list[.key] // null)
}) | .[]
```

**`extract-hgvs.jq`:**
```jq
# Extract clean HGVS notations
{
  hgvs_g: .hgvs_g,
  hgvs_c: (.hgvs_c[0] // null),
  hgvs_p: (.hgvs_p[0] // null),
  gene: (.gene[0] // null)
}
```

**`extract-alterations.jq`:**
```jq
# Extract key alteration fields
.results[] | {
  gene: .gene,
  name: .name,
  mutation_type: .mutation_type,
  aa_change: .aa_change,
  biomarkers: (.biomarkers | join(", "))
}
```

## Complete Workflows

### 1. Alteration Discovery

```bash
# Find BRAF V600E alterations
jn cat "@genomoncology/alterations?name=BRAF+V600E" | \
  jn filter '@genomoncology/filters/extract-alterations' | \
  jn put --plugin tabulate --tablefmt grid -
```

**Output:**
```
+------+-------------+-------------------------+-----------+--------------+
| gene | name        | mutation_type           | aa_change | biomarkers   |
+======+=============+=========================+===========+==============+
| BRAF | BRAF V600E  | Substitution - Missense | V600E     | BRAF         |
+------+-------------+-------------------------+-----------+--------------+
```

### 2. Variant Annotation Pipeline

```bash
# Annotate variant and pivot by transcript
jn cat "@genomoncology/annotations?hgvs_g=chr7:g.140453136A>T" | \
  jn filter '@genomoncology/annotations:pivot-transcripts' | \
  jn put annotations.csv
```

**Result:** CSV with one row per transcript.

### 3. Clinical Trial Matching

```bash
# Find melanoma trials for BRAF V600E
jn cat "@genomoncology/clinical_trials?alteration=BRAF+V600E&disease=Melanoma" | \
  jn filter '.status == "Recruiting"' | \
  jn filter '{nct_id, title, phase, status}' | \
  jn put --plugin tabulate --tablefmt psql -
```

**Output:**
```
+-----------+--------------------------------+--------+-----------+
| nct_id    | title                          | phase  | status    |
|-----------+--------------------------------+--------+-----------|
| NCT12345  | Dabrafenib in BRAF+ Melanoma   | Phase3 | Recruiting|
+-----------+--------------------------------+--------+-----------+
```

### 4. Multi-Source Analysis

```bash
#!/bin/bash
# Find all EGFR alterations and matching trials

# Step 1: Get EGFR alterations
jn cat "@genomoncology/alterations?gene=EGFR" | \
  jn filter '@genomoncology/filters/extract-alterations' | \
  jn put egfr_alterations.csv

# Step 2: Find trials for EGFR
jn cat "@genomoncology/clinical_trials?alteration=EGFR" | \
  jn filter '.status == "Recruiting"' | \
  jn filter '{nct_id, title, alterations}' | \
  jn put egfr_trials.csv

# Step 3: Combine and display
echo "EGFR Alterations:"
cat egfr_alterations.csv | head -n 10

echo "\nEGFR Clinical Trials:"
cat egfr_trials.csv | head -n 10
```

## API Parameter Filtering

### API-Level vs JN-Level Filtering

**API-level (efficient - less data transfer):**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense"
```

**JN-level (flexible - any field, complex logic):**
```bash
jn cat @genomoncology/alterations | \
  jn filter '.gene == "BRAF" and .mutation_type_group == "Missense"'
```

**Combined (best of both):**
```bash
# Reduce data transfer with API filter
# Add complex logic with JN filter
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '.p_start >= 600 and .p_end <= 700' | \
  jn filter '{name, aa_change, mutation_type}'
```

### When to Use API Parameters

**Use API parameters when:**
- Field is indexed (gene, disease, alteration)
- Reduces data transfer significantly
- API supports the filter

**Use JN filters when:**
- Complex logic (ranges, combinations, calculations)
- Fields not supported by API
- Need to transform response structure

## Design Decisions

### 1. Sources in Profile vs Separate Files

**Option A: All in one file**
```json
{
  "sources": {
    "alterations": {...},
    "annotations": {...},
    "clinical_trials": {...}
  }
}
```

**Option B: Hierarchical (recommended for large APIs)**
```
genomoncology/
├── _profile.json          # Base (URL, auth)
├── alterations.json       # Alterations source
├── annotations.json       # Annotations source
├── clinical_trials.json   # Trials source
└── filters/
    ├── pivot-transcripts.jq
    └── extract-hgvs.jq
```

**Recommendation:** Option B for APIs with 5+ endpoints.

### 2. Source-Specific Filters vs Generic Filters

**Source-specific:**
- Tied to API response structure
- Referenced as `@genomoncology/annotations:pivot-transcripts`
- Only applicable to that source

**Generic:**
- Work on any NDJSON
- Standard jq filters
- Referenced as `jn filter '.field > 100'`

**When to use source-specific:**
- Complex API-specific transforms (pivot, extract)
- Nested/complex response structures
- Domain-specific logic (HGVS parsing, trial matching)

### 3. GET vs POST Sources

**GET for:**
- Simple queries
- URL parameters sufficient
- Idempotent reads

**POST for:**
- Large payloads (batch matching)
- Complex query structures
- API design requires it

**Example:**
```json
{
  "annotations_match": {
    "path": "/annotations/match",
    "method": "POST",
    "content_type": "application/x-www-form-urlencoded",
    "note": "POST due to large batch size"
  }
}
```

## Risks & Challenges

### 1. API Response Changes
**Risk:** API changes response structure, breaks filters.

**Mitigation:**
- Version profiles (`genomoncology-v1`, `genomoncology-v2`)
- Document API version in profile
- Fail fast with clear error messages

### 2. Rate Limiting
**Risk:** Too many requests hit rate limits.

**Mitigation:**
- Document rate limits in profile
- Add retry logic with exponential backoff
- Cache frequent queries

### 3. Complex Nested Structures
**Risk:** Annotations have deeply nested arrays → hard to work with.

**Mitigation:**
- Provide source-specific pivot filters
- Document structure transformation patterns
- Examples for common use cases

### 4. Parameter Validation
**Risk:** Invalid parameters passed to API.

**Mitigation:**
- Document valid parameters in source config
- API returns clear error messages
- Future: JSON schema validation

## Future Enhancements

### 1. Auto-Complete for Sources

```bash
$ jn cat @genomoncology/<TAB>
alterations
annotations
annotations_match
clinical_trials
genes
diseases
therapies
```

### 2. Source Discovery

```bash
$ jn profile sources genomoncology
Available sources:
- alterations: Genetic alterations database (55,000+ entries)
- annotations: Variant annotations with clinical significance
- clinical_trials: Clinical trial matching
- genes: Gene information and ontology
```

### 3. Filter Suggestions

```bash
$ jn profile filters genomoncology/annotations
Available filters:
- pivot-transcripts: Pivot to one row per transcript
- extract-hgvs: Extract HGVS notations (g, c, p)
```

### 4. Schema Validation

```bash
# Validate response against expected schema
jn cat @genomoncology/alterations --validate-schema
```

## Related Documents

- `http-design.md` - HTTP plugin architecture
- `rest-api-profiles.md` - Profile system design
- `format-design.md` - Format plugins (CSV, tables)

## Next Steps

1. **Implement hierarchical profiles** - `_profile.json` + subfiles
2. **Create pivot-transcripts filter** - Real JQ implementation
3. **Add clinical trials examples** - Trial matching workflows
4. **Document POST batch matching** - Annotations match endpoint
5. **Profile generator** - Auto-create from OpenAPI spec
