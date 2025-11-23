# GenomOncology API Demo

Real-world HTTP profile example showing authenticated API access to precision oncology data.

## Setup

```bash
# 1. Set credentials
export GENOMONCOLOGY_URL="your-org.genomoncology.com"
export GENOMONCOLOGY_API_KEY="your-api-key"

# 2. Install profile
mkdir -p ~/.local/jn/profiles/http/
cp -r profile ~/.local/jn/profiles/http/genomoncology
```

## Available Endpoints

The profile includes 7 data sources:
- **alterations** - Genetic alterations
- **clinical_trials** - Clinical trials
- **diseases** - Disease ontology
- **genes** - Gene database
- **therapies** - Treatment data
- **annotations** - Clinical annotations

## Usage Examples

```bash
# Query BRAF alterations
jn cat @genomoncology/alterations?gene=BRAF

# Search clinical trials
jn cat @genomoncology/clinical_trials?gene=EGFR | \
  jn filter '.phase == "Phase 3"' | \
  jn put phase3_trials.json

# Get gene details
jn cat @genomoncology/genes?symbol=TP53
```

## Profile Structure

```
profile/
├── _meta.json           # Base URL and authentication
├── alterations.json     # Genetic alterations endpoint
├── clinical_trials.json # Clinical trials endpoint
└── ...                  # Other endpoints
```

See `example.sh` for more usage patterns.
