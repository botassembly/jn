# S3 Protocol Plugin

## Overview
Implement a protocol plugin to read files from Amazon S3 (and S3-compatible services). Leverages AWS CLI for authentication and access, enabling secure cloud storage access.

## Goals
- Read files from S3 buckets using `s3://` URLs
- Support AWS authentication (credentials, profiles, IAM roles)
- Stream file contents (don't download entire file first)
- Handle S3 errors gracefully (NoSuchKey, AccessDenied, etc.)
- Support S3-compatible services (MinIO, DigitalOcean Spaces, etc.)

## Resources
**Test URLs (Public S3 buckets):**
- Wall Street Prep: `s3://wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx`
- Panorama Education: `s3://panorama-www/files/family-school-survey/Family-School-Relationships-Survey.xlsx`
- Statistics Iceland: `s3://hagstofan/media/public/2019/c464faa7-dbd0-41c7-b37c-8984d23abd8a.xlsx`
- CMS QPP: `s3://qpp-cm-prod-content/uploads/1668/2021 CMS Web Interface Excel Template with Sample Data.xlsx`

**Note:** These are public buckets accessible without credentials.

## Dependencies
- `aws` CLI (Amazon Web Services CLI)
- Must be installed separately: `pip install awscli` or system package
- Check availability: `which aws`
- DO NOT implement S3 protocol from scratch - use AWS CLI

## Technical Approach
- Implement `reads()` function to fetch from S3
- Pattern matching: `^s3://.*` to detect S3 URLs
- Use `aws s3 cp s3://bucket/key -` to stream to stdout
- Pipe output through format plugins (CSV, XLSX, JSON, etc.)
- Respect AWS CLI configuration (~/.aws/config, ~/.aws/credentials)
- Support `--profile` flag to select AWS profile
- Handle `--no-sign-request` for public buckets

## Usage Examples
```bash
# Public bucket (no auth)
jn cat s3://wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx | jn put local.xlsx

# With AWS profile
jn cat s3://my-private-bucket/data.csv --profile production | jn filter '.active == true'

# Combined with XLSX format plugin
jn cat s3://panorama-www/files/family-school-survey/Family-School-Relationships-Survey.xlsx | jn put survey.json

# Pipeline: S3 → XLSX → Filter → CSV
jn cat s3://qpp-cm-prod-content/uploads/1668/2021%20CMS%20Web%20Interface%20Excel%20Template%20with%20Sample%20Data.xlsx | jn filter '.score > 80' | jn put results.csv
```

## Out of Scope
- Writing to S3 (writes() function) - add later
- Listing bucket contents - separate command/plugin
- Multipart uploads - not needed for reads
- S3 Select (server-side filtering) - add later
- Glacier storage classes - stick to standard S3
- Bucket management (create, delete) - use AWS CLI directly
- IAM policy management - use AWS CLI/Console
- CloudFront integration - use HTTPS URLs instead
- S3 event notifications - out of scope
- Cross-region replication - AWS concern, not JN

## Success Criteria
- Can read from public S3 buckets without credentials
- Can read from private buckets with AWS CLI configuration
- Properly handles S3 errors with clear messages
- Streams data (constant memory usage)
- Works with format plugins (XLSX, CSV, JSON)
- Respects AWS CLI profiles and configuration
