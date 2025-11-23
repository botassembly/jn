# GenomOncology API Demo

This demo shows how to use JN with the GenomOncology API for accessing clinical genomic data.

## What is GenomOncology?

GenomOncology provides precision oncology data including:
- Genetic alterations
- Clinical trials
- Disease information
- Gene databases
- Therapy recommendations
- Clinical annotations

## Setup

### 1. Set Required Environment Variables

```bash
export GENOMONCOLOGY_URL="your-org.genomoncology.com"
export GENOMONCOLOGY_API_KEY="your-api-key"
```

### 2. Install Profile

Copy the profile to your JN home:

```bash
mkdir -p ~/.local/jn/profiles/http/
cp -r profile ~/.local/jn/profiles/http/genomoncology
```

Or use it directly from this demo folder by setting:

```bash
export JN_HOME=/path/to/jn/demos/genomoncology
```

## Available Endpoints

The profile includes these data sources:

- **alterations** - Genetic alterations database
- **clinical_trials** - Clinical trials information
- **diseases** - Disease ontology and information
- **genes** - Gene database
- **therapies** - Treatment and therapy data
- **annotations** - Clinical annotations

## Usage Examples

### Query Genetic Alterations

```bash
# Find BRAF alterations
jn cat @genomoncology/alterations?gene=BRAF

# Filter by mutation type
jn cat @genomoncology/alterations?gene=EGFR&mutation_type=SNV&limit=10
```

### Search Clinical Trials

```bash
# Find trials for a specific gene
jn cat @genomoncology/clinical_trials?gene=EGFR

# Combine with filtering
jn cat @genomoncology/clinical_trials?gene=TP53 | \
  jn filter '.phase == "Phase 3"' | \
  jn put phase3_trials.json
```

### Gene Information

```bash
# Get gene details
jn cat @genomoncology/genes?symbol=BRAF
```

### Disease Information

```bash
# Query diseases
jn cat @genomoncology/diseases?name=Melanoma
```

## Pipeline Examples

### Find Trials for Multiple Genes

```bash
# Create gene list
echo '{"symbol":"BRAF"}
{"symbol":"EGFR"}
{"symbol":"TP53"}' > genes.ndjson

# Query trials for each gene
jn cat genes.ndjson | \
  jn filter '@uri "@genomoncology/clinical_trials?gene=\(.symbol)"' | \
  jn put all_trials.json
```

### Filter and Transform

```bash
# Get alterations and extract specific fields
jn cat @genomoncology/alterations?gene=BRAF | \
  jn filter '{gene: .gene, type: .mutation_type, significance: .clinical_significance}' | \
  jn put braf_summary.csv
```

## Profile Structure

```
profile/
├── _meta.json           # Base URL and authentication
├── alterations.json     # Genetic alterations endpoint
├── clinical_trials.json # Clinical trials endpoint
├── diseases.json        # Disease information endpoint
├── genes.json          # Gene database endpoint
├── therapies.json      # Therapy data endpoint
└── annotations.json    # Clinical annotations endpoint
```

## Notes

- This profile requires valid GenomOncology credentials
- Response format depends on the API endpoint
- Some endpoints support pagination via `page` and `limit` parameters
- See the GenomOncology API documentation for complete parameter lists
