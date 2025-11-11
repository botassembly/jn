# Google Sheets Plugin

## What
Read and write Google Sheets via Google Sheets API. Cloud-based spreadsheet collaboration.

## Why
Google Sheets is ubiquitous for team collaboration and shared data. Enable pipelines to read/write shared spreadsheets.

## Key Features
- Read Google Sheets (by ID or URL)
- Write NDJSON to Google Sheets
- Multiple sheet support (tabs)
- Range selection (A1 notation)
- Authentication (OAuth, service account)
- Batch read/write for performance

## Dependencies
- `google-auth` (authentication)
- `google-auth-oauthlib` (OAuth flow)
- `google-api-python-client` (Sheets API)

## Profile Structure
**Config:** `profiles/gsheets/mysheets.json`
```json
{
  "driver": "google_sheets",
  "credentials": "${GOOGLE_SHEETS_CREDENTIALS}",
  "auth_method": "service_account"
}
```

## Examples
```bash
# Read by URL
jn cat "https://docs.google.com/spreadsheets/d/SHEET_ID/edit" | jn filter '.status == "active"' | jn jtbl

# Read specific sheet/range
jn cat "gsheets://SHEET_ID/Sales Data!A1:D100" | jn put sales.csv

# Write to sheet
jn cat data.json | jn put "gsheets://SHEET_ID/Output"

# Sync with profile
jn cat @mysheets/weekly-report | jn filter '.revenue > 10000' | jn put high-value.csv

# Update sheet
jn cat processed.csv | jn put @mysheets/processed-data
```

## URL Syntax
- `gsheets://SHEET_ID` - Entire spreadsheet (first sheet)
- `gsheets://SHEET_ID/Sheet1` - Specific sheet by name
- `gsheets://SHEET_ID/Sheet1!A1:D100` - Range in A1 notation
- Full URL also supported: `https://docs.google.com/spreadsheets/d/SHEET_ID`

## Authentication
**Service Account** (recommended for automation):
1. Create service account in Google Cloud Console
2. Download JSON credentials
3. Share sheet with service account email
4. Set `GOOGLE_SHEETS_CREDENTIALS` env var

**OAuth** (for user access):
1. Create OAuth credentials in Google Cloud Console
2. Run OAuth flow to get refresh token
3. Store credentials in profile

## Out of Scope
- Complex formatting (colors, fonts) - data only
- Charts and visualizations - use Sheets UI
- Formulas preservation - read computed values only
- Cell comments - data only
- Permissions management - use Sheets UI
