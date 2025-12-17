#!/bin/bash
# Shell Commands Demo - Converting Shell Output to NDJSON
# Requires: jc (JSON Convert) - pip install jc
set -e
cd "$(dirname "$0")"

rm -f actual.txt

# Check if uv is installed (we run jc via uv for reproducibility)
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not installed. Install uv: https://github.com/astral-sh/uv"
    exit 1
fi

echo "=== Shell Commands Demo ===" >> actual.txt
echo "" >> actual.txt

echo "1. Parse ls output (from fixed input):" >> actual.txt
echo '-rw-r--r--  1 user  staff  1234 Jan  1 12:00 file1.txt
-rw-r--r--  1 user  staff  5678 Jan  2 14:30 file2.csv
drwxr-xr-x  3 user  staff    96 Jan  3 09:15 subdir' | uv run jc --ls | jn cat -~json | jn filter '{filename, size}' >> actual.txt
echo "" >> actual.txt

echo "2. Parse env output (from fixed input):" >> actual.txt
echo 'HOME=/home/user
USER=testuser
SHELL=/bin/bash' | uv run jc --env | jn cat -~json | jn filter '{name, value}' >> actual.txt
echo "" >> actual.txt

echo "3. Parse df output (from fixed input):" >> actual.txt
echo 'Filesystem     1K-blocks     Used Available Use% Mounted on
/dev/sda1       10485760  5242880   5242880  50% /
/dev/sda2       20971520 10485760  10485760  50% /data' | uv run jc --df | jn cat -~json | jn filter '{filesystem, use_percent, mounted_on}' >> actual.txt
echo "" >> actual.txt

echo "4. Parse ps output (from fixed input):" >> actual.txt
echo 'USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169584 13284 ?        Ss   Dec15   0:02 /sbin/init
user      1234  1.5  2.0 500000 20480 pts/0    S    10:00   0:30 python app.py' | uv run jc --ps | jn cat -~json | jn filter '{user, pid, cpu_percent, command}' >> actual.txt
echo "" >> actual.txt

echo "=== Done ===" >> actual.txt

if diff -q expected.txt actual.txt > /dev/null 2>&1; then
    echo "PASS"; cat actual.txt
else
    echo "FAIL"; diff expected.txt actual.txt || true; exit 1
fi
