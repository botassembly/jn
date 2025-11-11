# Extract and normalize alteration records from GenomOncology alterations API
# Handles both wrapped (.results[]) and unwrapped responses
#
# Usage:
#   jn cat @genomoncology/alterations | jn filter '@genomoncology/extract-alterations'
#
# Example Input:
#   {"results": [{"gene": "BRAF", "name": "BRAF V600E", "mutation_type": "Substitution - Missense",
#                 "aa_change": "V600E", "biomarkers": ["BRAF"], "p_start": 600}]}
#
# Example Output:
#   {"gene": "BRAF", "name": "BRAF V600E", "mutation_type": "Substitution - Missense",
#    "aa_change": "V600E", "biomarker": "BRAF", "position": 600}

# Handle wrapped (.results) or unwrapped records
(if .results then .results[] else . end) |

# Extract and normalize fields
{
  # Core identification
  gene: .gene,
  name: .name,
  alteration_id: (.id // .alteration_id // null),

  # Mutation classification
  mutation_type: .mutation_type,
  mutation_type_group: (.mutation_type_group // null),
  consequence: (.consequence // .variant_classification // null),

  # Amino acid change
  aa_change: (.aa_change // .protein_change // null),

  # Position information
  position: (
    if .p_start then .p_start
    elif .position then .position
    elif .start then .start
    else null
    end
  ),

  # Genomic coordinates (if available)
  chromosome: (.chr // .chromosome // null),
  ref: (.ref // .reference_allele // null),
  alt: (.alt // .alternate_allele // null),

  # Biomarkers - normalize to single string
  biomarker: (
    if .biomarkers then
      (if (.biomarkers | type) == "array" then
        (.biomarkers | join(", "))
      else
        .biomarkers
      end)
    else null
    end
  ),

  # Clinical significance
  clinical_significance: (.clinical_significance // null),

  # Additional context
  transcript: (.transcript // null),
  exon: (.exon // null)
} |

# Remove null fields for cleaner output
with_entries(select(.value != null))
