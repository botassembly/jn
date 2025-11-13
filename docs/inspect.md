# `jn inspect` quick look

`jn inspect` is the Swiss army knife for peeking at remote MCP servers, HTTP APIs, Gmail, or boring flat files. It figures out whether you pointed it at a container ("what tools/endpoints do you have?") or a data stream ("what does this data actually look like?") and renders a textual dashboard by default.

The command below inspects the public Homo sapiens gene info file from NCBI, trims it to 1,000 rows, and renders the default text view:

```bash
jn inspect \
  "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz~csv?delimiter=auto" \
  --limit 1000 --format text
```

Which produces (abridged):

```
Resource: https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz~csv?delimiter=auto
Transport: protocol
Format: csv
Rows: 1000
Columns: 16

Schema:
  #tax_id: string (1 unique)
  GeneID: string (1000 unique)
  ...

Facet candidates:
  • #tax_id (1 values) — top: 9606 (1000)
  • type_of_gene (5 values) — top: protein-coding (875), pseudo (93), unknown (24)
  • Nomenclature_status (2 values) — top: O (980), - (20)

Flat fields (low variation):
  • #tax_id — constant
  • GeneID — unique IDs
  • Symbol — unique IDs

MCP / domain hints:
  • Gene-centric columns detected — explore BioMCP tools via `jn inspect @biomcp` or call `mcp+uvx://biomcp-python/biomcp`
  • Chromosome facets found — try BioMCP's chromosome browsers or build MCP workflows against those facets

Facets:
  chromosome:
    1: 108
    11: 78
    19: 74
    ...

Statistics:
  GeneID:
    Count: 1000 (nulls: 0)
    Min: 1.00
    Max: 1243.00
    Mean: 614.58
    StdDev: 355.36
```

You can still ask for `--format json` if you need the raw schema/stats structure for downstream tooling, but the text version now surfaces facet suggestions, flat fields, and BioMCP jumping-off points without having to scroll through JSON blobs.
