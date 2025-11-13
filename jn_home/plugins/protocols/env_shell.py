#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jc>=1.23.0"]
# [tool.jn]
# matches = ["^shell://env$", "^shell://env\\?.*"]
# ///

"""
JN Shell Plugin: env

Execute `env` command to list environment variables as NDJSON.

Usage:
    jn cat shell://env
    jn cat shell://env | jn filter '.name == "PATH"'
    jn cat shell://env | jn filter '.value | contains("/usr/local")'

Output schema:
    {
        "name": string,
        "value": string
    }
"""

import subprocess
import sys
import json
import shutil
from urllib.parse import urlparse, parse_qs


def parse_config_from_url(url=None):
    """Parse configuration from shell:// URL."""
    if not url:
        return {}

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    config = {k: v[0] if v else None for k, v in params.items()}
    return config


def reads(config=None):
    """Execute env command and stream NDJSON records."""
    if config is None:
        config = {}

    # Check if jc is available
    if not shutil.which('jc'):
        error = {"_error": "jc not found. Install: pip install jc"}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)

    # Build commands
    env_cmd = ['env']
    jc_cmd = ['jc', '--env']

    try:
        # Chain: env | jc
        env_proc = subprocess.Popen(env_cmd, stdout=subprocess.PIPE, stderr=sys.stderr)
        jc_proc = subprocess.Popen(jc_cmd, stdin=env_proc.stdout, stdout=subprocess.PIPE, stderr=sys.stderr, text=True)

        # CRITICAL: Close env stdout in parent
        env_proc.stdout.close()

        # Read and output
        output = jc_proc.stdout.read()
        jc_proc.wait()
        env_proc.wait()

        # Parse JSON and convert to NDJSON
        records = json.loads(output) if output.strip() else []
        for record in records:
            print(json.dumps(record))

    except Exception as e:
        error = {"_error": str(e)}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='JN env shell plugin')
    parser.add_argument('--mode', default='read')
    parser.add_argument('--url', help='Shell URL')
    parser.add_argument('--config', help='JSON config')
    args = parser.parse_args()

    if args.mode == 'read':
        config = {}
        if args.url:
            config = parse_config_from_url(args.url)
        elif args.config:
            config = json.loads(args.config)
        reads(config)
    else:
        sys.exit(1)
