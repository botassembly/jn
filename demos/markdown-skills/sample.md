---
title: API Reference
version: 2.1.0
author: Bot Assembly
tags: [api, documentation, v2]
date: "2024-01-15"
---

# API Reference

This document describes the REST API endpoints.

## Authentication

All requests require a bearer token.

```bash
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/v2
```

## Endpoints

### GET /users

Returns a list of users.

```json
{
  "users": [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"}
  ]
}
```

### POST /users

Creates a new user.

```python
import requests
requests.post("/users", json={"name": "Charlie"})
```

## Rate Limits

- 100 requests per minute
- 10,000 requests per day
