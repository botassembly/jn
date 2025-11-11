# Extract key alteration fields from GenomOncology API results
.results[] | {
  gene: .gene,
  name: .name,
  mutation_type: .mutation_type,
  aa_change: .aa_change,
  biomarkers: .biomarkers | join(", ")
}
