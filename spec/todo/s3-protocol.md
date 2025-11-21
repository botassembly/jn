# S3 Protocol Plugin

## What
Read files from Amazon S3 buckets and S3-compatible services (MinIO, DigitalOcean Spaces, etc.).

## Why
Cloud storage is standard for data infrastructure. Enable seamless access to S3 data in pipelines.

## Key Features
- Read from S3 using `s3://bucket/key` URLs
- AWS authentication (profiles, credentials, IAM roles)
- Public bucket support (no credentials needed)
- Streaming (constant memory)
- Works with all format plugins (XLSX, CSV, JSON, etc.)

## Dependencies
- `aws` CLI (leverage existing tool, don't reimplement)

## Examples
```bash
# Public bucket
jn cat s3://public-data/sales.csv | jn filter '.revenue > 1000'

# Private bucket with profile
jn cat s3://my-bucket/data.xlsx --profile production | jn put output.json

# Combined with format plugins
jn cat s3://bucket/data.xlsx | jn filter '.active == true' | jn put filtered.csv
```

## Out of Scope
- Writing to S3 (add later)
- Bucket listing/management (use AWS CLI)
