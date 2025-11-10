#!/usr/bin/env python3
"""FTP GET plugin - Fetch files from FTP servers.

Fetches files from FTP/FTPS servers using curl.
Supports anonymous and authenticated access.
"""
# /// script
# dependencies = []
# ///
# META: type=source
# KEYWORDS: ftp, ftps, fetch, download, file
# DESCRIPTION: Fetch files from FTP servers via ftp:// URLs

import sys
import subprocess
from typing import Optional


def run(config: Optional[dict] = None) -> None:
    """Fetch file from FTP server via curl.

    Uses curl for FTP access. Writes raw bytes to stdout.
    Defaults to anonymous access (username: anonymous, password: anonymous@).

    Args:
        config: Configuration dict
            - url: str - FTP URL (ftp:// or ftps://) (required)
            - username: str - FTP username (default: "anonymous")
            - password: str - FTP password (default: "anonymous@")
            - timeout: int - Timeout in seconds (default: 60)
            - insecure: bool - Skip SSL verification for FTPS (default: False)

    Output:
        Raw bytes written to stdout (binary mode)

    Notes:
        - Anonymous FTP: Uses username "anonymous" and password "anonymous@"
        - Some servers expect email format for anonymous password
        - Passive mode (PASV) is used for firewall compatibility
    """
    if config is None:
        config = {}

    url = config.get('url')
    if not url:
        print("Error: FTP URL (ftp:// or ftps://) is required", file=sys.stderr)
        sys.exit(1)

    if not (url.startswith('ftp://') or url.startswith('ftps://')):
        print(f"Error: Invalid FTP URL: {url} (must start with ftp:// or ftps://)", file=sys.stderr)
        sys.exit(1)

    username = config.get('username', 'anonymous')
    password = config.get('password', 'anonymous@')
    timeout = config.get('timeout', 60)
    insecure = config.get('insecure', False)

    # Build curl command
    cmd = [
        'curl',
        '-s',  # Silent mode (no progress bar)
        '--ftp-pasv',  # Use passive mode (firewall-friendly)
        '--max-time', str(timeout)
    ]

    # Add authentication (curl format: -u username:password)
    # For anonymous, explicitly set credentials to be clear
    cmd.extend(['-u', f'{username}:{password}'])

    # Add FTPS options if needed
    if url.startswith('ftps://'):
        if insecure:
            cmd.append('--insecure')  # Skip SSL verification
        # curl handles FTPS automatically

    # Add URL
    cmd.append(url)

    try:
        # Execute curl
        # Use Popen for streaming (don't load entire file into memory)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Stream bytes from FTP to stdout
        # Read in chunks to handle large files efficiently
        chunk_size = 64 * 1024  # 64KB chunks
        while True:
            chunk = process.stdout.read(chunk_size)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

        # Wait for process to complete and check return code
        stderr_output = process.stderr.read()
        return_code = process.wait()

        if return_code != 0:
            error_msg = stderr_output.decode('utf-8', errors='replace')
            print(f"FTP fetch failed: {error_msg}", file=sys.stderr)

            # Provide helpful hints for common errors
            if 'Could not resolve host' in error_msg:
                print("Hint: Check that the FTP server hostname is correct", file=sys.stderr)
            elif 'Access denied' in error_msg or '530' in error_msg:
                print("Hint: Check username and password", file=sys.stderr)
                print("      For anonymous access, try: username='anonymous', password='user@example.com'", file=sys.stderr)
            elif '550' in error_msg:
                print("Hint: File not found or permission denied", file=sys.stderr)
                print("      Check that the file path is correct", file=sys.stderr)
            elif 'SSL' in error_msg or 'certificate' in error_msg:
                print("Hint: For FTPS with self-signed certs, try: --config '{\"insecure\": true}'", file=sys.stderr)
            elif 'Timeout' in error_msg or 'timed out' in error_msg:
                print("Hint: Connection timeout. Try increasing: --config '{\"timeout\": 120}'", file=sys.stderr)
            elif 'curl: not found' in error_msg or 'curl: command not found' in error_msg:
                print("Hint: curl not installed. Install via your package manager", file=sys.stderr)

            sys.exit(1)

    except FileNotFoundError:
        print("Error: curl not found. Install via your package manager (apt, yum, brew, etc.)", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """Return JSON schema for FTP GET configuration.

    FTP GET outputs raw bytes (not JSON), so schema describes config input.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "Configuration for FTP file fetch",
        "properties": {
            "url": {
                "type": "string",
                "pattern": "^ftps?://",
                "description": "FTP URL (ftp:// or ftps://)"
            },
            "username": {
                "type": "string",
                "description": "FTP username (default: anonymous)",
                "default": "anonymous"
            },
            "password": {
                "type": "string",
                "description": "FTP password (default: anonymous@)",
                "default": "anonymous@"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60)",
                "default": 60
            },
            "insecure": {
                "type": "boolean",
                "description": "Skip SSL verification for FTPS (default: false)",
                "default": False
            }
        },
        "required": ["url"]
    }


def examples() -> list[dict]:
    """Return example usage patterns."""
    return [
        {
            "description": "Anonymous FTP access (default)",
            "config": {
                "url": "ftp://ftp.example.com/pub/data/file.xlsx"
            },
            "note": "Uses anonymous:anonymous@ by default"
        },
        {
            "description": "Anonymous FTP with email as password",
            "config": {
                "url": "ftp://ftp.example.com/pub/data.xlsx",
                "username": "anonymous",
                "password": "user@example.com"
            },
            "note": "Some servers expect email format for anonymous password"
        },
        {
            "description": "Authenticated FTP access",
            "config": {
                "url": "ftp://ftp.example.com/private/data.xlsx",
                "username": "myuser",
                "password": "mypassword"
            },
            "note": "For non-anonymous access"
        },
        {
            "description": "FTPS with SSL verification",
            "config": {
                "url": "ftps://secure-ftp.example.com/data.xlsx",
                "username": "myuser",
                "password": "mypassword"
            },
            "note": "Uses FTPS (FTP over SSL/TLS)"
        },
        {
            "description": "FTPS with self-signed certificate",
            "config": {
                "url": "ftps://ftp.example.com/data.xlsx",
                "insecure": True
            },
            "note": "Skip SSL verification for self-signed certs"
        },
        {
            "description": "FTP with custom timeout",
            "config": {
                "url": "ftp://slow-ftp.example.com/large-file.xlsx",
                "timeout": 300
            },
            "note": "Increase timeout for large files or slow connections"
        }
    ]


def test() -> bool:
    """Run built-in tests with real public FTP servers.

    Tests against real public FTP servers (anonymous access).

    Returns:
        True if all tests pass
    """
    import tempfile
    import os

    print("Testing with REAL FTP servers (NO MOCKS)...", file=sys.stderr)

    # First, check if curl is available
    try:
        subprocess.run(['curl', '--version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("⚠ curl not installed - skipping FTP tests", file=sys.stderr)
        print("  Install via your package manager", file=sys.stderr)
        return True  # Don't fail if curl isn't installed

    passed = 0
    failed = 0

    # Test cases - using your provided public FTP URLs
    test_cases = [
        {
            "description": "NCBI dbGaP submission template (anonymous FTP)",
            "config": {
                "url": "ftp://ftp.ncbi.nlm.nih.gov/dbgap/dbGaP_Submission_Guide_Templates/Individual_Submission_Templates/Phenotype_Data/2b_SubjectConsent_DD.xlsx",
                "timeout": 30
            },
            "min_size": 1000  # XLSX should be >1KB
        },
        {
            "description": "EMBL-EBI ChEMBL dataset (anonymous FTP)",
            "config": {
                "url": "ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLNTD/set23_ucsd_GHCDL/GHCDL_Primary_Screen_Inhibition.xlsx",
                "timeout": 60  # Larger file, longer timeout
            },
            "min_size": 5000  # Dataset should be >5KB
        }
    ]

    for test_case in test_cases:
        desc = test_case['description']
        config = test_case['config']
        min_size = test_case.get('min_size', 100)

        try:
            print(f"Testing: {desc}", file=sys.stderr)

            # Create temp file for output
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name

            try:
                # Run FTP fetch
                old_stdout = sys.stdout
                sys.stdout = open(tmp_path, 'wb')

                run(config)

                sys.stdout.close()
                sys.stdout = old_stdout

                # Check file size
                file_size = os.path.getsize(tmp_path)
                if file_size >= min_size:
                    print(f"  ✓ {desc} ({file_size} bytes)", file=sys.stderr)
                    passed += 1
                else:
                    print(f"  ✗ {desc}: File too small ({file_size} bytes, expected >={min_size})", file=sys.stderr)
                    failed += 1

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except SystemExit as e:
            if e.code != 0:
                print(f"  ✗ {desc}: FTP fetch failed", file=sys.stderr)
                failed += 1
        except Exception as e:
            print(f"  ✗ {desc}: {e}", file=sys.stderr)
            failed += 1

    total = passed + failed
    if total > 0:
        print(f"\n{passed}/{total} FTP tests passed", file=sys.stderr)
    else:
        print("\nNo FTP tests run (curl not available)", file=sys.stderr)
        return True  # Don't fail if we couldn't run tests

    return failed == 0


if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description='Fetch files from FTP servers via ftp:// or ftps:// URLs'
    )
    parser.add_argument(
        'url',
        nargs='?',
        help='FTP URL (ftp:// or ftps://)'
    )
    parser.add_argument(
        '--url',
        dest='url_flag',
        help='FTP URL (alternative)'
    )
    parser.add_argument(
        '--username', '-u',
        default='anonymous',
        help='FTP username (default: anonymous)'
    )
    parser.add_argument(
        '--password', '-p',
        default='anonymous@',
        help='FTP password (default: anonymous@)'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=60,
        help='Timeout in seconds (default: 60)'
    )
    parser.add_argument(
        '--insecure',
        action='store_true',
        help='Skip SSL verification for FTPS'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show usage examples'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run built-in tests with real FTP servers'
    )
    parser.add_argument(
        '--schema',
        action='store_true',
        help='Output JSON schema'
    )

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
        sys.exit(0)

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    # Get URL from either positional or flag
    url = args.url or args.url_flag
    if not url:
        parser.error("FTP URL (ftp:// or ftps://) is required")

    # Build config
    config = {
        'url': url,
        'username': args.username,
        'password': args.password,
        'timeout': args.timeout,
    }

    if args.insecure:
        config['insecure'] = True

    # Run fetcher
    run(config)
