# FTP Protocol Plugin

## What
Read files from FTP/FTPS servers for accessing legacy scientific and government data repositories.

## Why
Some data sources (NCBI, EMBL-EBI, etc.) still use FTP. Enable access to these repositories.

## Key Features
- Read from FTP using `ftp://` URLs
- Anonymous and authenticated access
- Streaming (constant memory)
- Works with all format plugins

## Dependencies
- `curl` command (has built-in FTP support)

## Examples
```bash
# Anonymous FTP
jn cat ftp://ftp.ncbi.nlm.nih.gov/path/to/data.xlsx | jn put local.xlsx

# With authentication
jn cat ftp://user:pass@ftp.example.com/data.csv | jn filter '.active == true'
```

## Known Risks
- FTP may be blocked in containerized/sandbox environments
- Provide clear error message if unavailable
- Document HTTPS alternatives where available
