#!/bin/bash
# HTTP API Demo - Fetching Data from REST APIs
#
# Demonstrates:
# - Fetching JSON from HTTP URLs with format hints (~json)
# - Filtering and transforming API responses
# - Converting API data to local files
# - Handling nested JSON structures

set -e

echo "=== JN HTTP API Demo ==="
echo ""

# Clean up previous output
rm -f user.json repos.json countries.json cat_facts.json

# Example 1: Fetch user data from GitHub API
# ~json format hint tells JN to expect JSON response
# jn filter reshapes the data, jn put saves as JSON array
echo "1. Fetch GitHub user info..."
jn cat "https://api.github.com/users/octocat~json" | \
  jn filter '{login: .login, name: .name, repos: .public_repos, followers: .followers}' | \
  jn put user.json
echo "   ✓ Created user.json"
echo ""

# Example 2: Fetch array of repos
# GitHub API returns JSON array, JN converts to NDJSON stream
# jn head limits to first 10 repos (early termination!)
echo "2. Fetch user's repositories..."
jn cat "https://api.github.com/users/octocat/repos~json" | \
  jn filter '{name: .name, stars: .stargazers_count, language: .language}' | \
  jn head -n 10 | \
  jn put repos.json
echo "   ✓ Created repos.json (top 10)"
echo ""

# Example 3: Fetch from different API
# REST Countries API, extract nested fields with .capital[0]
# // "N/A" provides fallback for missing values
echo "3. Fetch European countries..."
jn cat "https://restcountries.com/v3.1/region/europe~json" | \
  jn filter '{
    name: .name.common,
    capital: (.capital[0] // "N/A"),
    population: .population,
    area: .area
  }' | \
  jn head -n 10 | \
  jn put countries.json
echo "   ✓ Created countries.json (top 10)"
echo ""

# Example 4: Extract nested data
# API returns {data: [...]} structure
# jn filter '.data[]' extracts array elements
echo "4. Fetch cat facts..."
jn cat "https://catfact.ninja/facts?limit=5~json" | \
  jn filter '.data[]' | \
  jn filter '{fact: .fact, length: .length}' | \
  jn put cat_facts.json
echo "   ✓ Created cat_facts.json"
echo ""

# Show results - note how we query the JSON array outputs
echo "=== Results ==="
echo ""
echo "GitHub user:"
jq -r '.[0] | "\(.login) (\(.name)) - \(.repos) public repos"' user.json
echo ""

echo "Top repository by stars:"
jq 'sort_by(.stars) | reverse | .[0] | "\(.name): \(.stars) stars (\(.language // "N/A"))"' repos.json
echo ""

echo "Largest European country (by area):"
jq 'sort_by(.area) | reverse | .[0] | "\(.name): \(.area) km²"' countries.json
echo ""

echo "Random cat fact:"
jq -r '.[0].fact' cat_facts.json
echo ""

echo "All examples completed! Check the output files."
