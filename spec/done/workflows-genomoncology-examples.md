# GenomOncology API Workflows - Practical Examples

## Overview

This document provides complete, real-world examples of using JN with the GenomOncology Precision Medicine API. All examples use the hierarchical profile structure with filters.

**Prerequisites:**
```bash
export GENOMONCOLOGY_URL="your-server.genomoncology.io"
export GENOMONCOLOGY_API_KEY="your-api-token-here"
```

---

## Workflow 1: Variant Discovery Pipeline

**Scenario:** Find all BRAF alterations and extract key fields for analysis.

```bash
# Fetch BRAF alterations and extract normalized fields
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '@genomoncology/extract-alterations' | \
  jn put braf_alterations.csv

# Preview results as table
jn cat braf_alterations.csv | \
  jn filter '{gene, name, mutation_type, aa_change, position}' | \
  jn put --plugin tabulate --tablefmt grid -
```

**Output:**
```
+------+----------------+-------------------------+-----------+----------+
| gene | name           | mutation_type           | aa_change | position |
+======+================+=========================+===========+==========+
| BRAF | BRAF V600E     | Substitution - Missense | V600E     | 600      |
| BRAF | BRAF V600K     | Substitution - Missense | V600K     | 600      |
| BRAF | BRAF V600R     | Substitution - Missense | V600R     | 600      |
+------+----------------+-------------------------+-----------+----------+
```

**Key Points:**
- API-level filtering (`?gene=BRAF`) reduces data transfer
- `extract-alterations` normalizes response structure
- Output to CSV for downstream analysis
- Tabulate for human-readable display

---

## Workflow 2: HGVS Nomenclature Extraction

**Scenario:** Annotate a variant and extract all HGVS notations (genomic, coding, protein).

```bash
# Fetch annotation for BRAF V600E (genomic coordinates)
jn cat "@genomoncology/annotations?hgvs_g=chr7:g.140453136A>T" | \
  jn filter '@genomoncology/extract-hgvs' | \
  jn put hgvs_notations.json
```

**Output (hgvs_notations.json):**
```json
{"uuid":"abc123","gene":"BRAF","hgvs_type":"genomic","hgvs":"chr7:g.140453136A>T","chr":"chr7","notation":"g.140453136A>T"}
{"uuid":"abc123","gene":"BRAF","hgvs_type":"coding","hgvs":"NM_004333.4:c.1799T>A","accession":"NM_004333.4","notation":"c.1799T>A"}
{"uuid":"abc123","gene":"BRAF","hgvs_type":"coding","hgvs":"NM_004333.5:c.1799T>A","accession":"NM_004333.5","notation":"c.1799T>A"}
{"uuid":"abc123","gene":"BRAF","hgvs_type":"protein","hgvs":"NP_004324.2:p.Val600Glu","accession":"NP_004324.2","notation":"p.Val600Glu"}
{"uuid":"abc123","gene":"BRAF","hgvs_type":"protein","hgvs":"NP_004324.3:p.Val600Glu","accession":"NP_004324.3","notation":"p.Val600Glu"}
```

**Analysis:**
```bash
# Count HGVS types
jn cat hgvs_notations.json | jn filter '.hgvs_type' | sort | uniq -c

# Extract unique protein changes
jn cat hgvs_notations.json | \
  jn filter 'select(.hgvs_type == "protein") | .notation' | \
  sort -u
```

**Key Points:**
- `extract-hgvs` explodes arrays to individual records
- Each HGVS notation becomes a separate row
- Parses accession numbers and nomenclature
- Maintains traceability with uuid and gene

---

## Workflow 3: Transcript Pivot Analysis

**Scenario:** Get all transcript variants for a gene and analyze by transcript.

```bash
# Fetch EGFR annotations and pivot by transcript
jn cat "@genomoncology/annotations?gene=EGFR" | \
  jn filter '@genomoncology/by_transcript' | \
  jn put egfr_by_transcript.csv

# Count variants per transcript
jn cat egfr_by_transcript.csv | \
  jn filter '.nm' | \
  sort | uniq -c | sort -rn | head -10
```

**Sample Output:**
```
  45 NM_005228.5
  42 NM_005228.4
  38 NM_005228.3
  12 NM_001346897.2
   8 NM_001346898.2
```

**Combined with HGVS extraction:**
```bash
# Pivot and extract HGVS in one pipeline
jn cat "@genomoncology/annotations?gene=EGFR" | \
  jn filter '@genomoncology/by_transcript' | \
  jn filter '@genomoncology/extract-hgvs' | \
  jn filter 'select(.hgvs_type == "coding")' | \
  jn put egfr_coding_variants.csv
```

**Key Points:**
- `by_transcript` converts nested arrays to flat rows
- One record per transcript-variant combination
- Can chain with `extract-hgvs` for detailed nomenclature
- Useful for transcript-level analysis

---

## Workflow 4: Clinical Trial Matching

**Scenario:** Find recruiting clinical trials for BRAF V600E in melanoma.

```bash
# Fetch trials and filter by status
jn cat "@genomoncology/clinical_trials?alteration=BRAF+V600E&disease=Melanoma" | \
  jn filter 'select(.status == "Recruiting")' | \
  jn filter '{nct_id, title, phase, status, sponsor}' | \
  jn put --plugin tabulate --tablefmt psql -
```

**Output:**
```
+-----------+----------------------------------+--------+-----------+--------------------+
| nct_id    | title                            | phase  | status    | sponsor            |
|-----------+----------------------------------+--------+-----------+--------------------|
| NCT12345  | Dabrafenib in BRAF+ Melanoma     | Phase3 | Recruiting| Novartis           |
| NCT67890  | Vemurafenib + Cobimetinib Study  | Phase2 | Recruiting| Genentech          |
+-----------+----------------------------------+--------+-----------+--------------------+
```

**Advanced filtering:**
```bash
# Find phase 3 trials only
jn cat "@genomoncology/clinical_trials?alteration=BRAF+V600E" | \
  jn filter 'select(.phase == "Phase3" and .status == "Recruiting")' | \
  jn filter '{nct_id, title, locations}' | \
  jn put phase3_trials.json
```

**Key Points:**
- API parameters for initial filtering
- JQ filters for complex logic (phase, status)
- Extract specific fields for reports
- Output to different formats (table, JSON, CSV)

---

## Workflow 5: Multi-Source Integration

**Scenario:** Combine alterations and clinical trials for a comprehensive report.

```bash
#!/bin/bash
# Find EGFR alterations and matching trials

GENE="EGFR"

# Step 1: Get alterations
echo "Fetching ${GENE} alterations..."
jn cat "@genomoncology/alterations?gene=${GENE}" | \
  jn filter '@genomoncology/extract-alterations' | \
  jn filter '{gene, name, mutation_type, aa_change, biomarker}' | \
  jn put ${GENE}_alterations.csv

# Step 2: Get clinical trials
echo "Fetching ${GENE} clinical trials..."
jn cat "@genomoncology/clinical_trials?alteration=${GENE}" | \
  jn filter 'select(.status == "Recruiting")' | \
  jn filter '{nct_id, title, alterations, phase}' | \
  jn put ${GENE}_trials.csv

# Step 3: Summary report
echo ""
echo "=== ${GENE} Summary Report ==="
echo ""
echo "Alterations found: $(jn cat ${GENE}_alterations.csv | wc -l)"
echo "Active trials: $(jn cat ${GENE}_trials.csv | wc -l)"
echo ""
echo "Top alterations:"
jn cat ${GENE}_alterations.csv | \
  jn filter '.name' | \
  sort | uniq -c | sort -rn | head -5
```

**Sample Output:**
```
=== EGFR Summary Report ===

Alterations found: 127
Active trials: 23

Top alterations:
  15 EGFR Exon 19 Deletion
  12 EGFR L858R
   8 EGFR T790M
   5 EGFR Exon 20 Insertion
   3 EGFR G719X
```

**Key Points:**
- Combines multiple sources (alterations + trials)
- Automated report generation
- Unix tools (wc, sort, uniq) for aggregation
- Scalable to multiple genes

---

## Workflow 6: Batch Variant Annotation (POST)

**Scenario:** Annotate multiple variants in a single request using POST.

```bash
# Create batch payload (form-encoded)
cat > batch_variants.txt <<'EOF'
batch=chr7|140453136|A|T|GRCh37&batch=NM_005228.3:c.2239_2241delTTA&batch=chr17|7577548|C|T|GRCh37
EOF

# Submit batch annotation request
cat batch_variants.txt | \
  jn cat @genomoncology/annotations_match | \
  jn filter '@genomoncology/extract-hgvs' | \
  jn put batch_annotations.json
```

**Why POST?**
- Handles large batch sizes (hundreds of variants)
- Exceeds URL length limits for GET
- Form-encoded body with multiple `batch=` parameters

**Output processing:**
```bash
# Group by gene
jn cat batch_annotations.json | \
  jn filter '{gene, hgvs_type, notation}' | \
  jn put --plugin tabulate --tablefmt simple -
```

**Key Points:**
- POST method for batch operations
- Form-encoded payload
- Same filters work on POST responses
- Efficient for large variant sets

---

## Workflow 7: Complex Filtering Chains

**Scenario:** Find missense BRAF alterations at position 600 with clinical significance.

```bash
# Multi-stage filtering pipeline
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '@genomoncology/extract-alterations' | \
  jn filter 'select(.mutation_type | contains("Missense"))' | \
  jn filter 'select(.position == 600)' | \
  jn filter 'select(.clinical_significance != null)' | \
  jn filter '{name, aa_change, mutation_type, clinical_significance}' | \
  jn put --plugin tabulate --tablefmt grid -
```

**Output:**
```
+-------------+-----------+-------------------------+-------------------------+
| name        | aa_change | mutation_type           | clinical_significance   |
+=============+===========+=========================+=========================+
| BRAF V600E  | V600E     | Substitution - Missense | Pathogenic              |
| BRAF V600K  | V600K     | Substitution - Missense | Pathogenic              |
+-------------+-----------+-------------------------+-------------------------+
```

**Key Points:**
- Chain multiple filters for complex logic
- Each filter operates on previous output
- Incremental refinement of data
- Final projection selects display fields

---

## Workflow 8: Gene Panel Analysis

**Scenario:** Analyze a panel of genes for actionable alterations.

```bash
#!/bin/bash
# Analyze NCCN melanoma gene panel

GENES=(BRAF NRAS KIT CDKN2A PTEN TP53)

echo "Gene,Alterations,Trials" > panel_summary.csv

for GENE in "${GENES[@]}"; do
  echo "Processing ${GENE}..."

  # Count alterations
  ALT_COUNT=$(jn cat "@genomoncology/alterations?gene=${GENE}" | \
    jn filter '@genomoncology/extract-alterations' | \
    wc -l)

  # Count trials
  TRIAL_COUNT=$(jn cat "@genomoncology/clinical_trials?alteration=${GENE}" | \
    jn filter 'select(.status == "Recruiting")' | \
    wc -l)

  echo "${GENE},${ALT_COUNT},${TRIAL_COUNT}" >> panel_summary.csv
done

# Display results
cat panel_summary.csv | column -t -s,
```

**Sample Output:**
```
Gene     Alterations  Trials
BRAF     127          45
NRAS     89           23
KIT      56           12
CDKN2A   34           8
PTEN     78           15
TP53     203          34
```

**Key Points:**
- Automated panel analysis
- Parallel gene processing
- Aggregated metrics
- Exportable summary table

---

## Workflow 9: Data Quality Validation

**Scenario:** Validate annotation data completeness and quality.

```bash
# Check for records with missing HGVS nomenclature
jn cat "@genomoncology/annotations?gene=BRAF" | \
  jn filter 'select(
    (.hgvs_g == null or .hgvs_g == "") and
    ((.hgvs_c | length) == 0 or .hgvs_c == null) and
    ((.hgvs_p | length) == 0 or .hgvs_p == null)
  )' | \
  jn filter '{uuid, gene, chr, position}' | \
  jn put incomplete_annotations.json

# Check completion rate
TOTAL=$(jn cat "@genomoncology/annotations?gene=BRAF" | wc -l)
INCOMPLETE=$(jn cat incomplete_annotations.json | wc -l)
COMPLETE=$((TOTAL - INCOMPLETE))
echo "Complete: ${COMPLETE}/${TOTAL} ($(( COMPLETE * 100 / TOTAL ))%)"
```

**Key Points:**
- Data quality checks in pipelines
- Identify incomplete records
- Calculate completion metrics
- Quality assurance reporting

---

## Workflow 10: Export to Multiple Formats

**Scenario:** Generate reports in multiple formats for different audiences.

```bash
# Fetch and process data once
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '@genomoncology/extract-alterations' | \
  jn filter 'select(.mutation_type | contains("Missense"))' > braf_missense.ndjson

# Export to CSV for Excel
jn cat braf_missense.ndjson | jn put braf_missense.csv

# Export to formatted table for reports
jn cat braf_missense.ndjson | \
  jn filter '{gene, name, aa_change, position}' | \
  jn put --plugin tabulate --tablefmt grid - > braf_missense_table.txt

# Export to JSON for downstream tools
jn cat braf_missense.ndjson | jn put braf_missense.json

# Export to YAML for config files
jn cat braf_missense.ndjson | jn put braf_missense.yaml
```

**Key Points:**
- Process once, export many times
- NDJSON as intermediate format
- Different formats for different use cases
- Efficient pipeline design

---

## Common Patterns and Best Practices

### 1. API Filtering vs JN Filtering

**API-level filtering (efficient):**
```bash
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense"
```
- Reduces data transfer
- Faster for indexed fields
- Limited to API capabilities

**JN-level filtering (flexible):**
```bash
jn cat @genomoncology/alterations | \
  jn filter '.gene == "BRAF" and (.p_start >= 600 and .p_start <= 700)'
```
- Complex logic (ranges, calculations)
- Any field, any condition
- More data transferred

**Combined (best):**
```bash
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '.p_start >= 600 and .p_start <= 700'
```

### 2. Filter Ordering for Performance

**Inefficient (filters last):**
```bash
jn cat @genomoncology/alterations | \
  jn filter '@genomoncology/extract-alterations' | \
  jn filter 'select(.gene == "BRAF")'  # Too late!
```

**Efficient (filter early):**
```bash
jn cat "@genomoncology/alterations?gene=BRAF" | \
  jn filter '@genomoncology/extract-alterations'
```

### 3. Reusable Intermediate Files

**Store NDJSON for reprocessing:**
```bash
# Fetch once
jn cat "@genomoncology/alterations?gene=BRAF" > braf_raw.ndjson

# Process multiple ways
jn cat braf_raw.ndjson | jn filter '@genomoncology/extract-alterations' | jn put alterations.csv
jn cat braf_raw.ndjson | jn filter '.results[0:10]' | jn put sample.json
jn cat braf_raw.ndjson | jn filter '.results | length' # Count
```

### 4. Error Handling

**Check for error records:**
```bash
jn cat @genomoncology/alterations | \
  jn filter 'select(._error == true)' > errors.json

# Exit if errors found
if [ -s errors.json ]; then
  echo "Errors encountered:"
  cat errors.json
  exit 1
fi
```

---

## Reference

### Available Sources
- `@genomoncology/alterations` - Genetic alterations database
- `@genomoncology/annotations` - Variant annotations
- `@genomoncology/annotations_match` - Batch annotation (POST)
- `@genomoncology/genes` - Gene information
- `@genomoncology/diseases` - Disease ontology
- `@genomoncology/therapies` - Treatment options
- `@genomoncology/clinical_trials` - Clinical trials

### Available Filters
- `@genomoncology/by_transcript` - Pivot annotations by transcript
- `@genomoncology/extract-hgvs` - Extract HGVS nomenclature
- `@genomoncology/extract-alterations` - Normalize alteration fields

### Environment Variables
```bash
export GENOMONCOLOGY_URL="your-server.genomoncology.io"
export GENOMONCOLOGY_API_KEY="your-api-token-here"
```

### Related Documentation
- `spec/design/genomoncology-api.md` - API integration design
- `spec/design/rest-api-profiles.md` - Profile system
- `jn_home/profiles/http/genomoncology/` - Profile files
