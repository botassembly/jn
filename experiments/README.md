# JN Experiments

This directory contains experimental profiles and plugins for JN that are not yet ready for bundled release.

## What's in Here

**HTTP Profiles:**
- `jn_home/profiles/http/genomoncology/` - GenomOncology API profile with sources for clinical trials, genetic alterations, diseases, genes, therapies, and annotations

## How to Use Experiments

There are two ways to use experimental profiles and plugins:

### Option 1: Set JN_HOME Environment Variable

Set `JN_HOME` to point to the `experiments/jn_home/` directory:

```bash
# One-time for current shell
export JN_HOME=/path/to/jn/experiments/jn_home

# Test it works
jn cat @genomoncology/alterations?gene=BRAF
```

To make it permanent, add the export to your shell rc file (`~/.bashrc`, `~/.zshrc`, etc.).

### Option 2: Copy to User Profile Directory

Copy profiles you want to use to your user profile directory:

```bash
# Copy genomoncology profile to user directory
mkdir -p ~/.local/jn/profiles/http/
cp -r experiments/jn_home/profiles/http/genomoncology ~/.local/jn/profiles/http/

# Now it's available without JN_HOME
jn cat @genomoncology/alterations?gene=BRAF
```

User profiles in `~/.local/jn/profiles/` take precedence over bundled profiles.

## Profile Search Order

JN searches for profiles in this order (highest to lowest priority):

1. **Project profiles**: `.jn/profiles/` (in current working directory)
2. **User profiles**: `~/.local/jn/profiles/`
3. **Bundled profiles**: `$JN_HOME/profiles/` or `jn_home/profiles/`
4. **Experiments**: Only if `JN_HOME=experiments/jn_home`

## Why These Are Experimental

Profiles in this directory are experimental because they:

- **Lack complete curation**: Missing pre-filled defaults, adapters, or target definitions
- **Need real credentials**: Require API keys or OAuth tokens that vary by user
- **Under active development**: API structure or profile design may change
- **Not production-ready**: Haven't been tested thoroughly with real-world usage patterns

## GenomOncology Profile Example

The GenomOncology profile demonstrates HTTP API profile structure:

**Meta file** (`_meta.json`):
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

**Source file** (e.g., `alterations.json`):
```json
{
  "path": "/alterations",
  "method": "GET",
  "type": "source",
  "params": ["gene", "mutation_type", "biomarker", "page", "limit"],
  "description": "Genetic alterations database"
}
```

**Usage:**
```bash
# Set required environment variables
export GENOMONCOLOGY_URL="your-org.genomoncology.com"
export GENOMONCOLOGY_API_KEY="your-api-key"

# Use the profile
jn cat @genomoncology/alterations?gene=BRAF&limit=10
jn cat @genomoncology/clinical_trials?gene=EGFR
```

## Contributing Experimental Profiles

To add new experimental profiles:

1. Create profile structure in `experiments/jn_home/profiles/`
2. Follow the hierarchical profile structure:
   - `_meta.json` - Connection config (base_url, auth, timeout)
   - `{source}.json` - Source endpoint definitions
3. Test with `JN_HOME=experiments/jn_home jn cat @yourprofile/source`
4. Document any required environment variables
5. Add to this README

## Moving to Bundled Release

For a profile to graduate from experiments to bundled release (`jn_home/profiles/`):

- [ ] Add pre-filled defaults for enum differentiation (multiple profiles from same endpoint)
- [ ] Create adapters in `filters/` subdirectory for common transformations
- [ ] Define targets for write operations (if applicable)
- [ ] Add comprehensive tests
- [ ] Document all parameters and usage patterns
- [ ] Remove any hardcoded credentials (use env vars only)
- [ ] Test with multiple real-world use cases

See `spec/design/profile-usage.md` for complete profile design guidance.
