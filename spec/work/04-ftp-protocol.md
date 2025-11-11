# FTP Protocol Plugin

## Overview
Implement a protocol plugin to read files from FTP servers. Uses command-line FTP tools to access scientific and government data repositories that still use FTP.

## Goals
- Read files from FTP servers using `ftp://` URLs
- Support anonymous and authenticated FTP
- Stream file contents (don't download entire file first)
- Handle FTP errors gracefully
- Support FTPS (FTP over SSL/TLS) if possible

## Resources
**Test URLs (Public FTP servers):**
- NCBI dbGaP template: `ftp://ftp.ncbi.nlm.nih.gov/dbgap/dbGaP_Submission_Guide_Templates/Individual_Submission_Templates/Phenotype_Data/2b_SubjectConsent_DD.xlsx`
- EMBL-EBI ChEMBL: `ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLNTD/set23_ucsd_GHCDL/GHCDL_Primary_Screen_Inhibition.xlsx`

**Note:** FTP access may be restricted in containerized environments.

## Dependencies
- `curl` command (supports FTP protocol)
- Alternative: `wget` (also supports FTP)
- Check availability: `which curl`
- DO NOT implement FTP protocol from scratch - use existing tools

## Technical Approach
- Implement `reads()` function to fetch from FTP
- Pattern matching: `^ftp://.*` or `^ftps://.*`
- Use `curl -s ftp://host/path` to stream to stdout
- Support authentication: `curl -u username:password ftp://...`
- Handle passive mode (usually automatic with curl)
- Check if FTP access is available in environment (may fail in sandbox)

## Usage Examples
```bash
# Anonymous FTP
jn cat ftp://ftp.ncbi.nlm.nih.gov/dbgap/.../2b_SubjectConsent_DD.xlsx | jn put template.xlsx

# With authentication
jn cat ftp://user:pass@ftp.example.com/data.csv | jn filter '.active == true'

# Combined with XLSX format plugin
jn cat ftp://ftp.ebi.ac.uk/pub/databases/chembl/.../GHCDL_Primary_Screen_Inhibition.xlsx | jn put screen.json
```

## Out of Scope
- Writing to FTP (writes() function) - add later
- Directory listing - separate command/plugin
- SFTP (SSH File Transfer Protocol) - different protocol, separate plugin
- Recursive directory downloads - use FTP CLI directly
- Resume/restart downloads - add later if needed
- Custom ports - use URL syntax `ftp://host:2121/path`
- Active vs passive mode configuration - rely on curl defaults

## Known Issues & Risks
- **Sandbox restrictions**: FTP may be blocked in containerized environments
- **Fallback**: If FTP is unavailable, document limitation and suggest HTTPS alternatives
- **Error handling**: Check curl exit code and provide helpful message if FTP blocked

## Success Criteria
- Can read from public FTP servers (NCBI, EMBL-EBI)
- Properly handles FTP errors with clear messages
- Streams data (constant memory usage)
- Works with format plugins (XLSX, CSV, JSON)
- Gracefully handles environment restrictions (clear error if FTP blocked)

## Alternative Approach
If FTP access is blocked:
- Document the limitation
- Suggest using HTTPS URLs where available (many FTP sites mirror on HTTP)
- Create stub plugin that explains FTP is unavailable
- Users can implement custom version if they have FTP access
