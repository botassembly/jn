#!/bin/bash
# HTTP API Demo - Run Examples

set -e

echo "=== JN HTTP API Demo ==="
echo ""

# Clean up previous output
rm -f user.json repos.json countries.json cat_facts.json

echo "1. Fetch GitHub user info..."
jn cat "https://api.github.com/users/octocat~json" | \
  jn filter '{login: .login, name: .name, repos: .public_repos, followers: .followers}' | \
  jn put user.json
echo "   ✓ Created user.json"
echo ""

echo "2. Fetch user's repositories..."
jn cat "https://api.github.com/users/octocat/repos~json" | \
  jn filter '{name: .name, stars: .stargazers_count, language: .language}' | \
  jn head -n 10 | \
  jn put repos.json
echo "   ✓ Created repos.json (top 10)"
echo ""

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

echo "4. Fetch cat facts..."
jn cat "https://catfact.ninja/facts?limit=5~json" | \
  jn filter '.data[]' | \
  jn filter '{fact: .fact, length: .length}' | \
  jn put cat_facts.json
echo "   ✓ Created cat_facts.json"
echo ""

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
