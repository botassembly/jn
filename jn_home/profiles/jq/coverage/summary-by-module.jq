# Aggregate coverage statistics by module/directory
# Usage: jn cat coverage.json | jn filter '@coverage/summary-by-module'
#
# Output: Module-level aggregated statistics
#
# Example:
#   Output: {"module":"addressing","files":3,"statements":692,"covered":573,"coverage":83}
#           {"module":"checker","files":7,"statements":605,"covered":479,"coverage":79}

.files
| to_entries
| map({
    module: (.key | split("/") | if length > 2 then .[0:3] | join("/") else .[0] end),
    file: .key,
    statements: .value.summary.num_statements,
    covered: .value.summary.covered_lines,
    branches: .value.summary.num_branches,
    covered_branches: .value.summary.covered_branches
  })
| group_by(.module)
| map({
    module: .[0].module,
    files: length,
    statements: (map(.statements) | add),
    covered: (map(.covered) | add),
    coverage: ((map(.covered) | add) * 100.0 / (map(.statements) | add) | floor),
    branches: (map(.branches) | add),
    branch_coverage: (
      if (map(.branches) | add) > 0
      then ((map(.covered_branches) | add) * 100.0 / (map(.branches) | add) | floor)
      else 100
      end
    )
  })
| sort_by(.coverage) | reverse | .[]
