# XLSX Multi-Transport Support

This document describes JN's support for reading and writing Excel files (XLSX/XLSM) from multiple transport sources including HTTP/HTTPS, S3, and FTP.

## Overview

JN provides a composable pipeline architecture for working with Excel files from various sources:

- **XLSX Reader** (`xlsx_reader.py`): Converts XLSX → NDJSON
- **XLSX Writer** (`xlsx_writer.py`): Converts NDJSON → XLSX
- **Transport Plugins**: Fetch files from HTTP, S3, FTP

## Quick Start

### Read XLSX from Local File

```bash
# Read XLSX, output as NDJSON
python3 plugins/readers/xlsx_reader.py data.xlsx

# Convert XLSX to CSV
python3 plugins/readers/xlsx_reader.py data.xlsx | python3 plugins/writers/csv_writer.py > output.csv

# Convert XLSX to JSON
python3 plugins/readers/xlsx_reader.py data.xlsx | python3 plugins/writers/json_writer.py > output.json
```

### Read XLSX from HTTP/HTTPS

Most public S3 buckets are accessible via HTTPS and work with standard curl + xlsx_reader:

```bash
# Wall Street Prep sample model
curl -sL "https://s3.amazonaws.com/wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | head -n 5

# Panorama Education survey
curl -sL "https://panorama-www.s3.amazonaws.com/files/family-school-survey/Family-School-Relationships-Survey.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | python3 plugins/writers/csv_writer.py \
  > survey.csv

# GitHub repository XLSX
curl -sL "https://raw.githubusercontent.com/hubmapconsortium/dataset-metadata-spreadsheet/main/sample-section/latest/sample-section.xlsx" \
  | python3 plugins/readers/xlsx_reader.py
```

### Read XLSX from Private S3 Buckets

For private S3 buckets using `s3://` URLs:

```bash
# Uses default AWS credentials (AWS_PROFILE, AWS_ACCESS_KEY_ID, etc.)
python3 plugins/http/s3_get.py s3://my-bucket/data.xlsx \
  | python3 plugins/readers/xlsx_reader.py

# Use specific AWS profile
python3 plugins/http/s3_get.py s3://my-bucket/data.xlsx --profile work-account \
  | python3 plugins/readers/xlsx_reader.py

# Public bucket via s3:// URL (no credentials)
python3 plugins/http/s3_get.py s3://public-bucket/data.xlsx --no-sign-request \
  | python3 plugins/readers/xlsx_reader.py
```

### Read XLSX from FTP

```bash
# Anonymous FTP (default)
python3 plugins/http/ftp_get.py "ftp://ftp.example.com/data.xlsx" \
  | python3 plugins/readers/xlsx_reader.py

# Anonymous FTP with email password
python3 plugins/http/ftp_get.py "ftp://ftp.ncbi.nlm.nih.gov/path/to/file.xlsx" \
  --username anonymous \
  --password user@example.com \
  | python3 plugins/readers/xlsx_reader.py

# Authenticated FTP
python3 plugins/http/ftp_get.py "ftp://ftp.example.com/private/data.xlsx" \
  --username myuser \
  --password mypassword \
  | python3 plugins/readers/xlsx_reader.py

# FTPS (FTP over SSL)
python3 plugins/http/ftp_get.py "ftps://secure-ftp.example.com/data.xlsx" \
  --username myuser \
  --password mypassword
```

## XLSX Reader Options

### Sheet Selection

```bash
# Read first sheet (default)
python3 plugins/readers/xlsx_reader.py data.xlsx

# Read specific sheet by name
python3 plugins/readers/xlsx_reader.py data.xlsx --sheet "Summary"

# Read specific sheet by index (0-based)
python3 plugins/readers/xlsx_reader.py data.xlsx --sheet 1
```

### Skip Rows and Limit

```bash
# Skip first 2 rows before header
python3 plugins/readers/xlsx_reader.py data.xlsx --skip-rows 2

# Read only first 100 rows
python3 plugins/readers/xlsx_reader.py data.xlsx --max-rows 100
```

### Formula Evaluation

```bash
# Evaluate formulas to values (default)
python3 plugins/readers/xlsx_reader.py data.xlsx --data-only

# Keep formulas as-is (not evaluated)
python3 plugins/readers/xlsx_reader.py data.xlsx --no-data-only
```

## XLSX Writer Options

### Basic Usage

```bash
# Convert NDJSON to XLSX
cat data.ndjson | python3 plugins/writers/xlsx_writer.py output.xlsx

# Convert JSON array to XLSX
python3 plugins/readers/json_reader.py data.json \
  | python3 plugins/writers/xlsx_writer.py output.xlsx

# Convert CSV to XLSX
python3 plugins/readers/csv_reader.py data.csv \
  | python3 plugins/writers/xlsx_writer.py output.xlsx
```

### Customization

```bash
# Custom sheet name
cat data.ndjson | python3 plugins/writers/xlsx_writer.py output.xlsx --sheet-name "Sales Data"

# No bold headers
cat data.ndjson | python3 plugins/writers/xlsx_writer.py output.xlsx --no-header-bold

# Disable auto-filter
cat data.ndjson | python3 plugins/writers/xlsx_writer.py output.xlsx --no-auto-filter

# Don't freeze header row
cat data.ndjson | python3 plugins/writers/xlsx_writer.py output.xlsx --no-freeze-panes
```

## Transport Plugins

### HTTP/HTTPS Transport

Uses `curl` for HTTP/HTTPS requests. Works with public S3 buckets via HTTPS URLs.

**No additional plugin needed** - just use curl directly:

```bash
curl -sL "https://example.com/file.xlsx" | python3 plugins/readers/xlsx_reader.py
```

### S3 Transport

Uses AWS CLI for private S3 bucket access.

**Requirements:**
- AWS CLI installed (`aws` command)
- AWS credentials configured (environment variables, `~/.aws/credentials`, or IAM role)

**Authentication:**

AWS CLI automatically uses credentials from:
1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
2. `--profile` parameter (overrides `AWS_PROFILE`)
3. `~/.aws/credentials` and `~/.aws/config`
4. IAM role (if running on EC2/ECS/Lambda)

**Options:**

```bash
# Default credentials
python3 plugins/http/s3_get.py s3://bucket/file.xlsx

# Specific profile
python3 plugins/http/s3_get.py s3://bucket/file.xlsx --profile prod

# Specific region
python3 plugins/http/s3_get.py s3://bucket/file.xlsx --region us-west-2

# Public bucket (no credentials)
python3 plugins/http/s3_get.py s3://public-bucket/file.xlsx --no-sign-request

# S3-compatible service (MinIO, etc.)
python3 plugins/http/s3_get.py s3://bucket/file.xlsx --endpoint-url https://minio.example.com
```

### FTP Transport

Uses `curl` for FTP/FTPS access.

**Requirements:**
- curl installed

**Authentication:**

Defaults to anonymous access (`username: anonymous`, `password: anonymous@`).

**Options:**

```bash
# Anonymous FTP
python3 plugins/http/ftp_get.py ftp://ftp.example.com/file.xlsx

# Anonymous with email password (some servers require this)
python3 plugins/http/ftp_get.py ftp://ftp.example.com/file.xlsx \
  --password user@example.com

# Authenticated FTP
python3 plugins/http/ftp_get.py ftp://ftp.example.com/file.xlsx \
  --username myuser \
  --password mypass

# FTPS with self-signed certificate
python3 plugins/http/ftp_get.py ftps://ftp.example.com/file.xlsx --insecure

# Custom timeout (default: 60 seconds)
python3 plugins/http/ftp_get.py ftp://ftp.example.com/file.xlsx --timeout 300
```

## Real-World Examples

### Example 1: Wall Street Prep Financial Model

```bash
# Download and preview
curl -sL "https://s3.amazonaws.com/wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | head -n 10

# Convert to CSV
curl -sL "https://s3.amazonaws.com/wsp_sample_file/excel-templates/financial-statement-model-sample.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | python3 plugins/writers/csv_writer.py \
  > financial-model.csv
```

### Example 2: UK ONS Statistics

```bash
# UK Internet Users dataset
curl -sL "https://www.ons.gov.uk/file?uri=/businessindustryandtrade/itandinternetindustry/datasets/internetusers/current/internetusers2020.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | python3 plugins/writers/json_writer.py \
  > uk-internet-users.json
```

### Example 3: GitHub Repository Templates

```bash
# HuBMAP sample metadata template
curl -sL "https://raw.githubusercontent.com/hubmapconsortium/dataset-metadata-spreadsheet/main/sample-section/latest/sample-section.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | jq '.'

# EBI EVA submission template
curl -sL "https://raw.githubusercontent.com/EBIvariation/eva-sub-cli/main/eva_sub_cli/etc/EVA_Submission_Example.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  --sheet "Files" \
  | head -n 5
```

### Example 4: Private S3 Bucket Workflow

```bash
# Scenario: Download from private S3, filter data, upload to different bucket

# Download from private bucket (uses default AWS credentials)
python3 plugins/http/s3_get.py s3://my-data-bucket/raw/sales-2024.xlsx \
  | python3 plugins/readers/xlsx_reader.py \
  | jq 'select(.revenue > 10000)' \
  | python3 plugins/writers/xlsx_writer.py /tmp/filtered-sales.xlsx

# Upload result to different bucket
aws s3 cp /tmp/filtered-sales.xlsx s3://my-reports-bucket/processed/
```

### Example 5: FTP to S3 Migration

```bash
# Download from public FTP, convert, upload to S3
python3 plugins/http/ftp_get.py "ftp://ftp.example.com/legacy/data.xlsx" \
  | python3 plugins/readers/xlsx_reader.py \
  | python3 plugins/writers/json_writer.py \
  > /tmp/data.json

aws s3 cp /tmp/data.json s3://my-bucket/migrated/
```

## Testing

All plugins include built-in tests that use real public URLs (no mocks):

```bash
# Test XLSX reader with real public files
python3 plugins/readers/xlsx_reader.py --test

# Test XLSX writer with round-trip validation
python3 plugins/writers/xlsx_writer.py --test

# Test S3 transport (requires AWS CLI)
python3 plugins/http/s3_get.py --test

# Test FTP transport (requires network access to FTP servers)
python3 plugins/http/ftp_get.py --test
```

## Plugin Details

### XLSX Reader (`plugins/readers/xlsx_reader.py`)

**Type:** Source plugin
**Handles:** `.xlsx`, `.xlsm`
**Streaming:** Yes (reads stdin or file)
**Dependencies:** `openpyxl>=3.1.0`

**Features:**
- Sheet selection (by name or index)
- Formula evaluation (default: true)
- Merged cell handling
- Auto-header detection (first row)
- Skip rows before header
- Limit max rows read

**Output:** NDJSON with column headers as keys

### XLSX Writer (`plugins/writers/xlsx_writer.py`)

**Type:** Target plugin
**Handles:** `.xlsx`
**Dependencies:** `openpyxl>=3.1.0`

**Features:**
- Auto-type detection (numbers, dates, strings)
- Bold headers (configurable)
- Auto-filter on headers (configurable)
- Freeze top row (configurable)
- Auto-column width (approximate)
- Custom sheet names

**Input:** NDJSON from stdin

### S3 Transport (`plugins/http/s3_get.py`)

**Type:** Source plugin
**URL Pattern:** `s3://bucket/key`
**Dependencies:** AWS CLI (`aws` command)

**Features:**
- AWS credential chain support
- Profile selection
- Region override
- Public bucket access (no credentials)
- S3-compatible services (MinIO, etc.)

**Output:** Raw bytes to stdout

### FTP Transport (`plugins/http/ftp_get.py`)

**Type:** Source plugin
**URL Pattern:** `ftp://` or `ftps://`
**Dependencies:** `curl`

**Features:**
- Anonymous FTP (default)
- Authenticated FTP
- FTPS (FTP over SSL/TLS)
- Passive mode (firewall-friendly)
- Custom timeouts
- SSL verification skip (for self-signed certs)

**Output:** Raw bytes to stdout

## Architecture Notes

### Composable Pipeline Design

JN's architecture follows the Unix philosophy of composing small, focused tools:

```
Transport Plugin → Format Reader → Transform → Format Writer
(fetch bytes)      (parse to NDJSON)  (filter)   (output format)
```

**Example pipeline:**

```bash
curl -sL "https://example.com/data.xlsx" \  # Transport: HTTP
  | python3 plugins/readers/xlsx_reader.py \  # Parse: XLSX → NDJSON
  | jq 'select(.status == "active")' \        # Transform: Filter
  | python3 plugins/writers/csv_writer.py     # Output: CSV
```

### Why Subprocess-Based Transports?

S3 and FTP plugins use subprocess calls (`aws`, `curl`) rather than Python libraries:

**Advantages:**
- ✅ No heavy Python dependencies (boto3 is ~50MB)
- ✅ Respects existing user configurations (AWS profiles, curl config)
- ✅ Handles authentication complexity automatically
- ✅ Streaming support (don't load large files into memory)
- ✅ Simpler testing (no library mocking needed)
- ✅ Consistent with existing `http_get.py` pattern

**Trade-offs:**
- ❌ Requires external tools (`aws`, `curl`)
- ❌ Slightly less control over low-level behavior

For most use cases, the advantages outweigh the trade-offs.

### Public S3 via HTTPS vs s3://

**Public S3 buckets** are typically accessed via HTTPS:
- ✅ Use: `https://s3.amazonaws.com/bucket/key` or `https://bucket.s3.amazonaws.com/key`
- ✅ No AWS CLI needed
- ✅ No credentials needed
- ✅ Works everywhere

**Private S3 buckets** require `s3://` URLs:
- ⚠️ Use: `s3://bucket/key`
- ⚠️ Requires AWS CLI
- ⚠️ Requires credentials
- ✅ Supports all AWS features (versioning, KMS, etc.)

## Troubleshooting

### XLSX Reader Issues

**Error: "openpyxl not installed"**
```bash
pip install openpyxl>=3.1.0
```

**Error: "Sheet 'X' not found"**
```bash
# List available sheets
python3 -c "import openpyxl; wb = openpyxl.load_workbook('file.xlsx'); print([ws.title for ws in wb.worksheets])"

# Use correct sheet name or index
python3 plugins/readers/xlsx_reader.py file.xlsx --sheet "Sheet2"
```

**Empty output:**
- Check if file has headers in first row
- Try `--skip-rows N` if headers are not in first row

### S3 Transport Issues

**Error: "AWS CLI not found"**
```bash
# Install AWS CLI
# See: https://aws.amazon.com/cli/

# Verify installation
aws --version
```

**Error: "Access Denied" or "Forbidden"**
```bash
# Check credentials
aws sts get-caller-identity

# For public buckets, use --no-sign-request
python3 plugins/http/s3_get.py s3://bucket/file.xlsx --no-sign-request

# Use specific profile
python3 plugins/http/s3_get.py s3://bucket/file.xlsx --profile myprofile
```

**Error: "NoSuchBucket" or "NoSuchKey"**
- Verify bucket name and file path
- Check region (some buckets are region-specific)

### FTP Transport Issues

**Error: "Could not resolve host"**
- Check FTP server hostname
- Verify network connectivity
- Some environments block FTP ports

**Error: "Access denied" (530)**
```bash
# Try with email-format password
python3 plugins/http/ftp_get.py ftp://ftp.example.com/file.xlsx \
  --password user@example.com
```

**Error: SSL certificate verification failed**
```bash
# Use --insecure for self-signed certs
python3 plugins/http/ftp_get.py ftps://ftp.example.com/file.xlsx --insecure
```

**Timeout errors:**
```bash
# Increase timeout
python3 plugins/http/ftp_get.py ftp://ftp.example.com/file.xlsx --timeout 300
```

## Future Enhancements

Potential improvements for future versions:

- [ ] Multi-sheet XLSX writer (write multiple sheets to one workbook)
- [ ] Streaming XLSX reader (for very large files)
- [ ] XLSB support (binary Excel format)
- [ ] CSV/TSV to XLSX with formatting
- [ ] Excel chart/image extraction
- [ ] Direct JN CLI integration (`jn cat s3://bucket/file.xlsx`)
- [ ] Parallel sheet reading (process multiple sheets concurrently)
- [ ] Azure Blob Storage transport
- [ ] Google Cloud Storage transport
- [ ] SFTP support (in addition to FTP/FTPS)

## Contributing

To add a new transport plugin:

1. Create plugin in `plugins/http/`
2. Follow pattern: read URL → write raw bytes to stdout
3. Add to registry URL patterns in `src/jn/registry.py`
4. Include `test()` function with real public URLs
5. Add examples to this documentation

To improve XLSX support:

1. Add features to `xlsx_reader.py` or `xlsx_writer.py`
2. Update `examples()` and `test()` functions
3. Ensure backward compatibility
4. Update this documentation

## License

Same as JN project (see main README).

## Related Documentation

- [Architecture](ARCHITECTURE.md)
- [Plugin Development](CONTRIBUTING.md)
- [Roadmap](../spec/ROADMAP.md)
