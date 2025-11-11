# RESTful API Dev Profile

## What
Example HTTP profile demonstrating `@profile/path` syntax for RESTful APIs. Uses restful-api.dev (free public test API).

## Why
Show how profile system works: reusable connection configs with path resolution. Template for other API profiles (GitHub, Stripe, etc.).

## Key Features
- Base URL + path composition (`@restful-api-dev/objects` → `https://api.restful-api.dev/objects`)
- Header configuration (Content-Type, Accept, Authorization)
- Path and query parameters
- GET and POST support

## Profile Config
```json
{
  "base_url": "https://api.restful-api.dev",
  "headers": {
    "Content-Type": "application/json",
    "Accept": "application/json"
  },
  "timeout": 30
}
```

## Examples
```bash
# List resources
jn cat @restful-api-dev/objects | jn filter '.data.year > 2020'

# Get specific resource
jn cat @restful-api-dev/objects/3 | jn put object.json

# Create resource
echo '{"name": "Device", "data": {"year": 2024}}' | jn put @restful-api-dev/objects
```

## Future Templates
Once working, create similar profiles for GitHub, Stripe, internal APIs with authentication.
