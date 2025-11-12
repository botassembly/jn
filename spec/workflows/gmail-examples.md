# Gmail Plugin Examples

## Overview

The Gmail plugin enables reading Gmail messages via the Gmail API with powerful server-side filtering using Gmail's search operators. All searches are pushed down to Google's servers for optimal performance.

## Setup

### 1. Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing
3. Enable the Gmail API
4. Create OAuth 2.0 Client ID (Desktop app type)
5. Download credentials JSON

### 2. Save Credentials

```bash
# Create JN config directory
mkdir -p ~/.jn

# Save downloaded credentials
mv ~/Downloads/client_secret_*.json ~/.jn/gmail-credentials.json
```

### 3. First Run (Authentication)

```bash
# First time - opens browser for OAuth consent
jn cat @gmail/inbox | head -n 1

# Token saved to ~/.jn/gmail-token.json for future use
# Subsequent runs use cached token automatically
```

## Parameter Syntax

Gmail supports two ways to pass search parameters:

**1. Query String (Recommended)**
```bash
jn cat "@gmail/inbox?from=boss&is=unread"
jn cat "@gmail/attachments?filename=pdf&newer_than=7d"
```

**2. -p Parameters (Alternative)**
```bash
jn cat @gmail/inbox -p from=boss -p is=unread
jn cat @gmail/attachments -p filename=pdf -p newer_than=7d
```

**3. Mixed (Query String + -p)**
```bash
jn cat "@gmail/inbox?from=boss" -p is=unread -p newer_than=7d
```

Both syntaxes work identically. Query strings are more concise; `-p` is easier for scripting.

## Basic Usage

### Read All Messages

```bash
# Fetch all messages (uses pagination automatically)
jn cat @gmail/messages

# Limit to first 10
jn cat @gmail/messages | head -n 10

# Output to JSON file
jn cat @gmail/messages | jn put messages.json
```

### Pre-configured Profiles

```bash
# Inbox messages only
jn cat @gmail/inbox

# Unread messages
jn cat @gmail/unread

# Starred messages
jn cat @gmail/starred

# Sent messages
jn cat @gmail/sent

# Messages with attachments
jn cat @gmail/attachments
```

## Filtering with -p (Server-Side Pushdown)

### Filter by Sender

```bash
# From specific sender
jn cat @gmail/messages -p from=boss@company.com

# Multiple senders (OR logic)
jn cat @gmail/messages -p from=boss@company.com -p from=colleague@example.com

# From domain
jn cat @gmail/messages -p from=@company.com
```

### Filter by Recipient

```bash
# To specific recipient
jn cat @gmail/messages -p to=client@example.com

# CC specific person
jn cat @gmail/messages -p cc=teammate@company.com
```

### Filter by Subject

```bash
# Subject contains keyword
jn cat @gmail/messages -p subject=invoice

# Subject with multiple keywords
jn cat @gmail/messages -p subject="quarterly report"
```

### Filter by Status

```bash
# Unread messages
jn cat @gmail/messages -p is=unread

# Starred messages
jn cat @gmail/messages -p is=starred

# Important messages
jn cat @gmail/messages -p is=important

# Read messages
jn cat @gmail/messages -p is=read
```

### Filter by Location

```bash
# Inbox
jn cat @gmail/messages -p in=inbox

# Sent
jn cat @gmail/messages -p in=sent

# Trash
jn cat @gmail/messages -p in=trash

# Spam
jn cat @gmail/messages -p in=spam
```

### Filter by Attachments

```bash
# Any attachment
jn cat @gmail/messages -p has=attachment

# PDF attachments
jn cat @gmail/messages -p has=attachment -p filename=pdf

# Specific filename
jn cat @gmail/messages -p filename=invoice.pdf

# Google Drive attachments
jn cat @gmail/messages -p has=drive

# Spreadsheet attachments
jn cat @gmail/messages -p has=spreadsheet

# Document attachments
jn cat @gmail/messages -p has=document
```

### Filter by Date

```bash
# After specific date
jn cat @gmail/messages -p after=2024/01/01

# Before specific date
jn cat @gmail/messages -p before=2024/12/31

# Date range
jn cat @gmail/messages -p after=2024/01/01 -p before=2024/01/31

# Relative dates
jn cat @gmail/messages -p newer_than=7d    # Last 7 days
jn cat @gmail/messages -p newer_than=1m    # Last month
jn cat @gmail/messages -p newer_than=1y    # Last year

jn cat @gmail/messages -p older_than=30d   # Older than 30 days
```

### Filter by Size

```bash
# Larger than 5MB
jn cat @gmail/messages -p larger=5M

# Smaller than 1MB
jn cat @gmail/messages -p smaller=1M

# Exact size (in bytes)
jn cat @gmail/messages -p size=1048576
```

### Filter by Label

```bash
# By label name
jn cat @gmail/messages -p label=work

# By category
jn cat @gmail/messages -p category=primary
jn cat @gmail/messages -p category=social
jn cat @gmail/messages -p category=promotions
```

## Complex Queries (Multiple Filters)

### Unread from Specific Sender

```bash
jn cat @gmail/messages -p from=boss@company.com -p is=unread
```

### Recent Invoices with Attachments

```bash
jn cat @gmail/messages \
  -p subject=invoice \
  -p has=attachment \
  -p newer_than=30d
```

### Large Attachments from Last Week

```bash
jn cat @gmail/attachments \
  -p larger=5M \
  -p newer_than=7d
```

### Unread Important Messages

```bash
jn cat @gmail/messages \
  -p is=unread \
  -p is=important
```

### Work Emails from Specific Period

```bash
jn cat @gmail/messages \
  -p from=@company.com \
  -p after=2024/01/01 \
  -p before=2024/03/31
```

## Pipeline Examples

### Extract Email Subjects

```bash
jn cat @gmail/unread | jq -r '.subject' | sort | uniq
```

### Count Emails by Sender

```bash
jn cat @gmail/messages -p newer_than=30d \
  | jq -r '.from' \
  | sort \
  | uniq -c \
  | sort -rn
```

### Export to CSV

```bash
jn cat @gmail/messages -p is=unread \
  | jq '{from: .from, subject: .subject, date: .date}' \
  | jn put unread-emails.csv
```

### Find Emails with PDFs

```bash
jn cat @gmail/attachments -p filename=pdf \
  | jq '{from: .from, subject: .subject, attachments: [.attachments[]? | select(.filename | endswith(".pdf")) | .filename]}' \
  | jn put pdf-emails.json
```

### Extract All Attachment Names

```bash
jn cat @gmail/attachments -p newer_than=7d \
  | jq -r '.attachments[]? | .filename' \
  | sort \
  | uniq
```

### Search for Keywords in Body

```bash
# Note: Full-text search happens server-side via subject/from filters
# For body search, fetch messages and filter client-side
jn cat @gmail/messages -p subject=contract \
  | jq 'select(.body_text | contains("NDA"))' \
  | jq '{from: .from, subject: .subject, date: .date}'
```

### Group by Date

```bash
jn cat @gmail/messages -p newer_than=30d \
  | jq -r '.date | split("T")[0]' \
  | sort \
  | uniq -c
```

## Output Format Control

### Minimal Format (IDs only - fast)

```bash
# Fastest - only fetches message IDs
jn cat @gmail/messages --format minimal | head -n 100
```

### Metadata Format (headers only)

```bash
# Medium speed - headers but no body
jn cat @gmail/messages --format metadata
```

### Full Format (everything)

```bash
# Slowest - complete message with body and attachments
jn cat @gmail/messages --format full
```

## Performance Tips

### 1. Use Server-Side Filtering

```bash
# ✅ GOOD - Filter pushed to API (fast)
jn cat @gmail/messages -p from=boss@company.com -p newer_than=7d

# ❌ BAD - Fetch all then filter client-side (slow)
jn cat @gmail/messages | jq 'select(.from | contains("boss@company.com"))'
```

### 2. Use Minimal Format When Possible

```bash
# ✅ GOOD - Just need IDs
jn cat @gmail/messages --format minimal -p is=unread | wc -l

# ❌ BAD - Fetching full messages just to count
jn cat @gmail/messages -p is=unread | wc -l
```

### 3. Combine with head/tail

```bash
# ✅ GOOD - Stops after 10 messages
jn cat @gmail/messages -p is=unread | head -n 10

# Early termination via SIGPIPE - doesn't fetch entire inbox
```

### 4. Use Specific Profiles

```bash
# ✅ GOOD - Profile has preset filter
jn cat @gmail/inbox

# Same as
jn cat @gmail/messages -p in=inbox
```

## Advanced Usage

### Multiple Accounts

```bash
# Use different token paths for multiple accounts
jn cat @gmail/messages --token-path ~/.jn/gmail-work-token.json
jn cat @gmail/messages --token-path ~/.jn/gmail-personal-token.json
```

### Include Spam/Trash

```bash
# By default, spam/trash are excluded
# Include them explicitly
jn cat @gmail/messages --include-spam-trash
```

### Custom Max Results

```bash
# Fetch more messages per page (API limit: 500)
jn cat @gmail/messages --max-results 500
```

## Common Workflows

### Daily Unread Summary

```bash
#!/bin/bash
# daily-unread.sh

echo "Unread emails from last 24 hours:"
jn cat @gmail/unread -p newer_than=1d \
  | jq -r '"\(.from)\t\(.subject)"' \
  | column -t -s $'\t'
```

### Archive Large Attachments

```bash
# Find emails with large attachments
jn cat @gmail/attachments -p larger=10M \
  | jq '{
      id: .id,
      from: .from,
      subject: .subject,
      date: .date,
      total_size: ([.attachments[]?.size] | add),
      files: [.attachments[]? | {name: .filename, size: .size}]
    }' \
  | jn put large-attachments.json
```

### Invoice Tracker

```bash
# Track all invoices received
jn cat @gmail/messages -p subject=invoice -p has=attachment \
  | jq '{
      date: .date,
      from: .from,
      subject: .subject,
      attachments: [.attachments[]? | select(.filename | test("(?i)invoice|pdf")) | .filename]
    }' \
  | jn put invoices.json
```

### Email Analytics

```bash
# Email volume by sender domain
jn cat @gmail/messages -p newer_than=30d \
  | jq -r '.from | split("@")[1]' \
  | sort \
  | uniq -c \
  | sort -rn \
  | head -n 20
```

## Troubleshooting

### Authentication Issues

```bash
# Delete token to re-authenticate
rm ~/.jn/gmail-token.json

# Next run will open browser for OAuth
jn cat @gmail/inbox
```

### Rate Limiting

Gmail API has quota limits. If you hit rate limits:

```bash
# Reduce max-results to make smaller requests
jn cat @gmail/messages --max-results 100

# Use more specific filters to reduce result count
jn cat @gmail/messages -p newer_than=7d
```

### Missing Credentials

```bash
# Error: Credentials not found
# Solution: Download from Google Cloud Console
# https://console.cloud.google.com/apis/credentials
# Save to ~/.jn/gmail-credentials.json
```

## Search Operator Reference

| Operator | Description | Example |
|----------|-------------|---------|
| `from` | Sender email/name | `-p from=boss@company.com` |
| `to` | Recipient email/name | `-p to=client@example.com` |
| `subject` | Subject keywords | `-p subject=invoice` |
| `cc` | CC email/name | `-p cc=teammate@company.com` |
| `bcc` | BCC email/name | `-p bcc=archive@company.com` |
| `has` | Attachment type | `-p has=attachment` |
| `filename` | Attachment filename | `-p filename=report.pdf` |
| `is` | Message status | `-p is=unread` |
| `in` | Folder/location | `-p in=inbox` |
| `label` | Label name | `-p label=important` |
| `after` | After date | `-p after=2024/01/01` |
| `before` | Before date | `-p before=2024/12/31` |
| `newer_than` | Relative newer | `-p newer_than=7d` |
| `older_than` | Relative older | `-p older_than=30d` |
| `size` | Exact size (bytes) | `-p size=1048576` |
| `larger` | Larger than | `-p larger=5M` |
| `smaller` | Smaller than | `-p smaller=1M` |
| `category` | Category | `-p category=primary` |

## Integration with Other Plugins

### Gmail + CSV

```bash
# Export to CSV
jn cat @gmail/unread \
  | jq '{from: .from, subject: .subject, date: .date}' \
  | jn put emails.csv
```

### Gmail + Markdown

```bash
# Create markdown report
jn cat @gmail/unread -p newer_than=1d \
  | jq -r '"- [\(.subject)](\(.id)) - \(.from) - \(.date)"' \
  > daily-emails.md
```

### Gmail + HTTP (webhook notifications)

```bash
# Send unread count to webhook
COUNT=$(jn cat @gmail/unread --format minimal | wc -l)
echo "{\"unread_count\": $COUNT}" \
  | jn cat - \
  | curl -X POST -H "Content-Type: application/json" -d @- https://webhook.site/...
```

## Notes

- **Server-side filtering:** All `-p` parameters are converted to Gmail's `q` query parameter and processed server-side
- **Streaming:** Messages are fetched and yielded one at a time (constant memory usage)
- **Pagination:** Automatic - continues until all matching messages are retrieved
- **Early termination:** Using `| head -n 10` stops fetching after 10 messages (SIGPIPE)
- **OAuth2:** Credentials cached in `~/.jn/gmail-token.json` and auto-refreshed
- **Read-only:** This plugin only reads messages (no write/delete/modify operations)
