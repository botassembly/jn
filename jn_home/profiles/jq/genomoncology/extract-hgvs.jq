# Extract and normalize HGVS nomenclature from GenomOncology annotations
# Works with both raw annotation records (arrays) or by_transcript output (single values)
#
# HGVS (Human Genome Variation Society) nomenclature includes:
#   g. = genomic reference (chr7:g.140453136A>T)
#   c. = coding DNA reference (NM_004333.4:c.1799T>A)
#   p. = protein reference (NP_004324.2:p.Val600Glu)
#
# Usage:
#   jn cat @genomoncology/annotations | jn filter '@genomoncology/extract-hgvs'
#   jn cat @genomoncology/annotations | jn filter '@genomoncology/by_transcript' | jn filter '@genomoncology/extract-hgvs'
#
# Example Input (raw):
#   {"uuid": "abc123", "gene": ["BRAF"], "hgvs_g": "chr7:g.140453136A>T",
#    "hgvs_c": ["NM_004333.4:c.1799T>A"], "hgvs_p": ["NP_004324.2:p.Val600Glu"]}
#
# Example Output:
#   {"uuid": "abc123", "gene": "BRAF", "hgvs_type": "genomic", "hgvs": "chr7:g.140453136A>T", "chr": "chr7", "notation": "g.140453136A>T"}
#   {"uuid": "abc123", "gene": "BRAF", "hgvs_type": "coding", "hgvs": "NM_004333.4:c.1799T>A", "accession": "NM_004333.4", "notation": "c.1799T>A"}
#   {"uuid": "abc123", "gene": "BRAF", "hgvs_type": "protein", "hgvs": "NP_004324.2:p.Val600Glu", "accession": "NP_004324.2", "notation": "p.Val600Glu"}

# Capture base fields for context
. as $base |

# Helper: extract gene (handle both array and string)
($base.gene | if type == "array" then .[0] else . end) as $gene |

# Helper: get uuid for traceability
($base.uuid // null) as $uuid |

# Create array of HGVS records
[
  # Genomic (hgvs_g) - usually single value, not array
  (if $base.hgvs_g and $base.hgvs_g != "" and $base.hgvs_g != null then
    ($base.hgvs_g | capture("^(?<chr>[^:]+):(?<notation>.+)$")) as $parsed |
    {
      uuid: $uuid,
      gene: $gene,
      hgvs_type: "genomic",
      hgvs: $base.hgvs_g,
      chr: $parsed.chr,
      notation: $parsed.notation
    }
  else empty end),

  # Coding (hgvs_c) - can be array or single value
  (if $base.hgvs_c then
    (if ($base.hgvs_c | type) == "array" then $base.hgvs_c[] else $base.hgvs_c end) |
    select(. != null and . != "") |
    (capture("^(?<accession>[^:]+):(?<notation>.+)$") // {accession: null, notation: .}) as $parsed |
    {
      uuid: $uuid,
      gene: $gene,
      hgvs_type: "coding",
      hgvs: .,
      accession: $parsed.accession,
      notation: $parsed.notation
    }
  else empty end),

  # Protein (hgvs_p) - can be array or single value
  (if $base.hgvs_p then
    (if ($base.hgvs_p | type) == "array" then $base.hgvs_p[] else $base.hgvs_p end) |
    select(. != null and . != "") |
    (capture("^(?<accession>[^:]+):(?<notation>.+)$") // {accession: null, notation: .}) as $parsed |
    {
      uuid: $uuid,
      gene: $gene,
      hgvs_type: "protein",
      hgvs: .,
      accession: $parsed.accession,
      notation: $parsed.notation
    }
  else empty end)
] |

# If no HGVS found, return original record
if length == 0 then
  $base
else
  # Otherwise yield each HGVS record
  .[]
end
