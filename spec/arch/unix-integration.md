# Integrating JN with Unix Tools

## Philosophy

**JN does one thing well**: Transform data between formats with pipelines.

**Unix tools do everything else**: Watching, scheduling, branching, parallelization, error handling, retries, orchestration.

**The power is in composition**: Chain JN with battle-tested Unix tools to build robust ETL workflows without reinventing the wheel.

---

## 1. File Watching with `watchmedo`

**Tool**: [watchdog](https://github.com/gorakhargosh/watchdog) - Cross-platform file system event monitoring

**Use case**: Process files as they arrive in a folder

```bash
# Install
pip install watchdog[watchmedo]

# Watch folder, run pipeline on new CSV files
watchmedo shell-command \
  --patterns="*.csv" \
  --recursive \
  --command='jn run process.json --input-file "${watch_src_path}" --output-file "${watch_dest_path%.csv}.json"' \
  ./inbox/
```

**Advanced**: Move processed files to archive
```bash
watchmedo shell-command \
  --patterns="*.csv" \
  --command='jn run process.json --input-file "${watch_src_path}" && mv "${watch_src_path}" ./archive/' \
  ./inbox/
```

---

## 2. Streaming Log Files with `tail`

**Tool**: tail - Output the last part of files, follow for new lines

**Use case**: Monitor log files in real-time and transform with JN

```bash
# Follow log file and filter errors
tail -f /var/log/app.log | jn cat - --parser json_s | jq 'select(.level == "ERROR")'

# Follow and send alerts
tail -f access.log | jn cat - --parser apache_log_s | \
  jq 'select(.status >= 500)' | \
  while read line; do
    curl -X POST -d "$line" https://hooks.slack.com/services/YOUR/WEBHOOK
  done

# Follow with file rotation support (tail -F)
tail -F /var/log/app.log | jn cat - | jq 'select(.amount > 1000)'

# Start from last 100 lines, then follow
tail -n 100 -f metrics.log | jn cat - --parser csv | \
  jq '{timestamp, value}' > live-metrics.json

# Follow multiple files
tail -f /var/log/*.log | jn cat - | jq 'select(.priority == "high")'
```

**Folder monitoring** (using ls/find with JN):
```bash
# List files in folder (using JC's ls parser via JN)
jn cat ls ./inbox/ | jq -r '.filename'

# Find CSV files recursively (using JC's find parser via JN)
jn cat find ./data/ -name "*.csv" | jq -r '.path'

# Process all files in folder
jn cat ls ./inbox/ | jq -r '.filename' | while read file; do
  jn cat "./inbox/$file" | jq '...' > "./output/$file"
done
```

---

## 3. Scheduled Jobs with `cron`

**Tool**: cron - Time-based job scheduler

**Use case**: Daily data export from database to Excel

```bash
# Edit crontab
crontab -e

# Run daily at 2 AM
0 2 * * * jn run /home/user/pipelines/daily-export.json --date $(date +\%Y-\%m-\%d) >> /var/log/jn-daily.log 2>&1

# Run every 15 minutes
*/15 * * * * jn cat https://api.example.com/metrics | jn put /data/metrics/$(date +\%Y\%m\%d-\%H\%M).json

# Run on first day of month
0 3 1 * * jn run /home/user/pipelines/monthly-report.json --output-file /reports/$(date +\%Y-\%m).xlsx
```

---

## 3. Branching Outputs with `tee`

**Tool**: tee - Read from stdin and write to multiple outputs

**Use case**: Send same data to multiple destinations

```bash
# Write to both file and stdout (for further processing)
jn cat data.csv | tee intermediate.json | jq 'select(.amount > 1000)' | jn put high-value.json

# Branch to multiple files
jn cat api-data.json | tee >(jn put backup.json) >(jn put archive.json) | jq '.' > processed.json

# Send to file and external API
jn cat events.csv | tee events.json | curl -X POST -d @- https://api.example.com/ingest
```

---

## 4. Parallel Processing with `xargs`

**Tool**: xargs - Build and execute command lines from stdin

**Use case**: Process multiple files in parallel

```bash
# Process all CSV files in folder
jn cat ls ./inbox/ | jq -r '.filename' | \
  xargs -I {} -P 4 jn run process.json --input-file ./inbox/{} --output-file ./output/{}.json

# Parallel with progress
jn cat find ./data/ -name "*.csv" | jq -r '.path' | \
  xargs -I {} -P 8 bash -c 'jn run transform.json --input-file "{}" && echo "✓ {}"'

# Process in batches of 10
ls *.csv | xargs -n 10 -P 4 -I {} jn cat {} | jn put combined.json
```

---

## 5. True Parallel Execution with `parallel`

**Tool**: [GNU Parallel](https://www.gnu.org/software/parallel/) - Better than xargs for complex jobs

**Use case**: Process 100 files with progress bar and retries

```bash
# Install
brew install parallel  # macOS
apt-get install parallel  # Linux

# Parallel processing with progress
jn cat ls ./inbox/ | jq -r '.filename' | \
  parallel --bar --jobs 8 \
  jn run process.json --input-file ./inbox/{} --output-file ./output/{.}.json

# With retries and logging
parallel --jobs 4 --retry 3 --joblog process.log \
  jn run pipeline.json --input-file {} --output-file {.}.json \
  ::: *.csv

# Resume failed jobs
parallel --resume --joblog process.log \
  jn run pipeline.json --input-file {} --output-file {.}.json \
  ::: *.csv
```

---

## 6. File System Events with `inotifywait`

**Tool**: inotifywait - Linux inotify-based file watching

**Use case**: Instant processing when file appears (faster than polling)

```bash
# Install
apt-get install inotify-tools

# Watch for new files
inotifywait -m -e create --format '%f' ./inbox/ | while read filename; do
  jn run process.json --input-file "./inbox/$filename"
done

# Watch for modifications (trigger on log updates)
inotifywait -m -e modify /var/log/app.log | while read path action file; do
  tail -n 1 /var/log/app.log | jn cat - --parser json_s | \
    jq 'select(.level == "ERROR")' | \
    curl -X POST -d @- https://hooks.slack.com/services/YOUR/WEBHOOK
done

# Multiple events
inotifywait -m -e create,modify,move --format '%e %f' ./data/ | while read event file; do
  echo "Event: $event on $file"
  jn run handle-event.json --event "$event" --file "$file"
done
```

---

## 7. Process Management with `systemd`

**Tool**: systemd - Linux init system and service manager

**Use case**: Run JN pipeline as a persistent service

```ini
# /etc/systemd/system/jn-processor.service
[Unit]
Description=JN Data Processor
After=network.target

[Service]
Type=simple
User=datauser
WorkingDirectory=/opt/jn
ExecStart=/usr/local/bin/jn follow /var/log/app.log
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable jn-processor
sudo systemctl start jn-processor

# Check status
sudo systemctl status jn-processor

# View logs
sudo journalctl -u jn-processor -f
```

**Path-based activation** (trigger on file creation):
```ini
# /etc/systemd/system/jn-watcher.path
[Path]
PathChanged=/data/inbox
MakeDirectory=yes

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/jn-watcher.service
[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for f in /data/inbox/*.csv; do jn run /opt/jn/process.json --input-file "$f"; done'
```

---

## 8. Process Supervision with `supervisord`

**Tool**: supervisord - Process control system

**Use case**: Keep JN pipelines running, auto-restart on crash

```ini
# /etc/supervisor/conf.d/jn-follower.conf
[program:jn-follower]
command=/usr/local/bin/jn follow /var/log/app.log
directory=/opt/jn
user=datauser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/jn/follower.log
```

```bash
# Control
supervisorctl start jn-follower
supervisorctl stop jn-follower
supervisorctl restart jn-follower
supervisorctl status
```

---

## 9. Data Fetching with `curl` and `wget`

**Tool**: curl/wget - Transfer data from URLs

**Use case**: Fetch data, transform, save

```bash
# Fetch and transform
curl -s https://api.example.com/data | jn cat - | jq 'select(.active)' | jn put active.json

# Download, parse, filter
wget -qO- https://example.com/data.csv | jn cat - --parser csv | \
  jq 'select(.amount > 1000)' | jn put high-value.xlsx

# Multiple sources, combine
curl -s https://api.example.com/users | jn cat - > users.json
curl -s https://api.example.com/orders | jn cat - > orders.json
jn cat users.json orders.json | jq -s '.' | jn put combined.json

# Scheduled fetch with cron
# crontab: */30 * * * * curl -s https://api.example.com/metrics | jn put /data/metrics/$(date +\%s).json
```

---

## 10. Git Hooks for Data Validation

**Tool**: Git hooks - Scripts triggered by git events

**Use case**: Validate data files before commit

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Validate all JSON files
for file in $(git diff --cached --name-only --diff-filter=ACM | grep '\.json$'); do
  jn cat "$file" > /dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "Error: $file is not valid JSON"
    exit 1
  fi
done

# Transform CSV to JSON before commit
for file in $(git diff --cached --name-only --diff-filter=ACM | grep '\.csv$'); do
  jn cat "$file" | jn put "${file%.csv}.json"
  git add "${file%.csv}.json"
done
```

---

## 11. Build Automation with `make`

**Tool**: make - Build automation tool

**Use case**: Define data pipeline dependencies

```makefile
# Makefile
.PHONY: all clean

# Default target
all: output/report.xlsx output/summary.json

# Raw data → cleaned data
data/cleaned.json: data/raw.csv
	jn cat $< | jq 'select(.valid)' | jn put $@

# Cleaned data → aggregated
data/aggregated.json: data/cleaned.json
	jn cat $< | jq -s 'group_by(.category)' | jn put $@

# Aggregated → Excel report
output/report.xlsx: data/aggregated.json
	jn cat $< | jn put $@ --format excel --header

# Aggregated → summary
output/summary.json: data/aggregated.json
	jn cat $< | jq 'map({category: .[0].category, count: length})' | jn put $@

clean:
	rm -f data/cleaned.json data/aggregated.json output/*
```

```bash
# Build everything
make

# Build specific target
make output/report.xlsx

# Rebuild from scratch
make clean all
```

---

## 12. Containerization with `docker`

**Tool**: Docker - Containerization platform

**Use case**: Package JN pipeline as reproducible container

```dockerfile
# Dockerfile
FROM python:3.11-slim

RUN pip install jn jq

WORKDIR /app
COPY pipeline.json /app/
COPY data/ /app/data/

CMD ["jn", "run", "pipeline.json"]
```

```bash
# Build
docker build -t my-pipeline .

# Run
docker run -v $(pwd)/data:/app/data my-pipeline

# Run with arguments
docker run my-pipeline jn run pipeline.json --input-file /app/data/input.csv
```

**Docker Compose** for multi-stage pipeline:
```yaml
# docker-compose.yml
version: '3'
services:
  fetch:
    image: my-pipeline
    command: jn cat https://api.example.com/data | jn put /data/raw.json
    volumes:
      - ./data:/data

  transform:
    image: my-pipeline
    command: jn run transform.json --input-file /data/raw.json --output-file /data/clean.json
    volumes:
      - ./data:/data
    depends_on:
      - fetch

  export:
    image: my-pipeline
    command: jn cat /data/clean.json | jn put /data/report.xlsx
    volumes:
      - ./data:/data
    depends_on:
      - transform
```

---

## 13. Message Queues with `kafka`

**Tool**: Kafka - Distributed event streaming

**Use case**: Consume from Kafka, transform, publish to another topic

```bash
# Consume, transform, produce
kafka-console-consumer --topic raw-events --bootstrap-server localhost:9092 | \
  jn cat - | \
  jq 'select(.valid) | {id, timestamp, value}' | \
  kafka-console-producer --topic processed-events --bootstrap-server localhost:9092

# With kafka-cat (better tool)
kafkacat -C -b localhost:9092 -t raw-events | \
  jn cat - | \
  jq 'select(.amount > 1000)' | \
  kafkacat -P -b localhost:9092 -t high-value-events
```

---

## 14. Redis for Caching and Pub/Sub

**Tool**: Redis - In-memory data store

**Use case**: Cache transformed data, publish events

```bash
# Fetch, transform, cache
jn cat https://api.example.com/users | \
  jq -s '.' | \
  redis-cli -x SET users:cache

# Read from cache, transform
redis-cli GET users:cache | jn cat - | jq 'map(select(.active))'

# Publish to Redis channel
jn cat events.json | while read line; do
  echo "$line" | redis-cli PUBLISH events "$line"
done

# Subscribe and process
redis-cli SUBSCRIBE events | \
  grep -v "subscribe" | \
  grep -v "message" | \
  jn cat - | \
  jq 'select(.priority == "high")'
```

---

## 15. AWS S3 Integration

**Tool**: aws-cli - AWS command line tool

**Use case**: Fetch from S3, transform, upload results

```bash
# Download, transform, upload
aws s3 cp s3://my-bucket/data.csv - | \
  jn cat - | \
  jq 'select(.valid)' | \
  jn put - --format json | \
  aws s3 cp - s3://my-bucket/processed/data.json

# Process all CSV files in S3 bucket
aws s3 ls s3://my-bucket/raw/ | awk '{print $4}' | while read file; do
  aws s3 cp "s3://my-bucket/raw/$file" - | \
    jn cat - | \
    jn put - --format excel | \
    aws s3 cp - "s3://my-bucket/processed/${file%.csv}.xlsx"
done

# Sync folder to S3 after processing
jn run daily-report.json --output-file /tmp/report.xlsx
aws s3 sync /tmp/report.xlsx s3://reports-bucket/$(date +%Y-%m-%d)/
```

---

## 16. Database Integration with `psql`

**Tool**: psql - PostgreSQL command line

**Use case**: Query database, transform, load to different format

```bash
# Export query results to Excel
psql -h localhost -U user -d mydb -c "SELECT * FROM sales WHERE amount > 1000" -t -A -F',' | \
  jn cat - --parser csv | \
  jn put sales-report.xlsx --header

# Transform and load back to DB
jn cat data.json | \
  jq -r '. | [.id, .name, .value] | @csv' | \
  psql -h localhost -U user -d mydb -c "COPY my_table FROM STDIN CSV"

# Daily export to multiple formats
psql -c "SELECT * FROM daily_metrics" -t -A -F',' | \
  jn cat - --parser csv | \
  tee >(jn put metrics.json) \
      >(jn put metrics.xlsx) \
      >(jn put metrics.md --format markdown)
```

---

## 17. Airflow for Complex Workflows

**Tool**: Apache Airflow - Workflow orchestration

**Use case**: Multi-stage ETL with dependencies, retries, monitoring

```python
# dags/data_pipeline.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

dag = DAG('data_pipeline', start_date=datetime(2025, 1, 1), schedule='@daily')

fetch = BashOperator(
    task_id='fetch',
    bash_command='jn cat https://api.example.com/data?date={{ ds }} | jn put /data/raw/{{ ds }}.json',
    dag=dag
)

transform = BashOperator(
    task_id='transform',
    bash_command='jn run transform.json --input-file /data/raw/{{ ds }}.json --output-file /data/clean/{{ ds }}.json',
    dag=dag
)

export = BashOperator(
    task_id='export',
    bash_command='jn cat /data/clean/{{ ds }}.json | jn put /data/reports/{{ ds }}.xlsx',
    dag=dag
)

fetch >> transform >> export
```

---

## 18. GitHub Actions for CI/CD

**Tool**: GitHub Actions - Automated workflows

**Use case**: Validate and transform data on every commit

```yaml
# .github/workflows/data-pipeline.yml
name: Data Pipeline

on:
  push:
    paths:
      - 'data/**.csv'

jobs:
  process:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install JN
        run: pip install jn

      - name: Transform data
        run: |
          jn cat data/input.csv | jn put data/output.json
          jn cat data/input.csv | jn put data/report.xlsx

      - name: Commit results
        run: |
          git config user.name "GitHub Actions"
          git add data/output.json data/report.xlsx
          git commit -m "Auto-generated reports"
          git push
```

---

## 19. Slack Notifications

**Tool**: Slack webhook - Send notifications

**Use case**: Alert on data anomalies

```bash
# Monitor and alert
jn follow /var/log/sales.log | \
  jq 'select(.amount > 10000)' | \
  while read line; do
    curl -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"High value sale: $line\"}" \
      https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  done

# Daily report summary
jn cat daily-sales.csv | \
  jq -s '{total: map(.amount) | add, count: length, avg: (map(.amount) | add / length)}' | \
  jq '{text: "Daily Summary - Total: \(.total), Avg: \(.avg), Count: \(.count)"}' | \
  curl -X POST -H 'Content-type: application/json' -d @- \
    https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## 20. Prometheus Metrics

**Tool**: Prometheus - Monitoring and alerting

**Use case**: Export pipeline metrics

```bash
# Push metrics from pipeline
jn cat metrics.json | \
  jq -r '.[] | "pipeline_records_processed \(.count)\npipeline_duration_seconds \(.duration)"' | \
  curl -X POST --data-binary @- http://localhost:9091/metrics/job/jn_pipeline

# Monitor file sizes
jn cat ls ./data/ | \
  jq -r '.[] | "data_file_size_bytes{filename=\"\(.filename)\"} \(.size)"' | \
  curl -X POST --data-binary @- http://localhost:9091/metrics/job/file_monitor
```

---

## 21. Elasticsearch for Search

**Tool**: Elasticsearch - Search and analytics engine

**Use case**: Index transformed data for searching

```bash
# Bulk index documents
jn cat products.csv | \
  jq -c '. | {"index": {"_index": "products", "_id": .id}}, .' | \
  curl -X POST "localhost:9200/_bulk" -H 'Content-Type: application/json' --data-binary @-

# Query, transform, re-index
curl "localhost:9200/products/_search" | \
  jn cat - | \
  jq '.hits.hits[]._source | select(.active)' | \
  jq -c '. | {"index": {"_index": "active_products", "_id": .id}}, .' | \
  curl -X POST "localhost:9200/_bulk" -H 'Content-Type: application/json' --data-binary @-
```

---

## 22. Dead Letter Queue with Directories

**Tool**: Bash + filesystem

**Use case**: Move failed files to error queue

```bash
# Process with error handling
for file in ./inbox/*.csv; do
  if jn run process.json --input-file "$file" --output-file "./output/$(basename $file .csv).json"; then
    # Success - move to processed
    mv "$file" ./processed/
  else
    # Failure - move to dead letter queue
    mv "$file" ./failed/
    echo "$(date): Failed to process $file" >> ./failed/errors.log
  fi
done

# Retry dead letter queue files
for file in ./failed/*.csv; do
  if jn run process.json --input-file "$file" --output-file "./output/$(basename $file .csv).json"; then
    echo "$(date): Retry successful for $file" >> ./failed/retries.log
    mv "$file" ./processed/
  fi
done
```

---

## 23. Rate Limiting with `sleep`

**Tool**: Bash sleep

**Use case**: Avoid overwhelming APIs

```bash
# Process files with rate limit (1 per second)
jn cat ls ./inbox/ | jq -r '.filename' | while read file; do
  jn cat "https://api.example.com/upload" --method POST --data "@./inbox/$file"
  sleep 1
done

# Batch processing with delays
for batch in ./data/batch*.csv; do
  jn run process.json --input-file "$batch"
  sleep 5  # Wait 5 seconds between batches
done
```

---

## 24. Log Aggregation with `syslog`

**Tool**: syslog/rsyslog - System logging

**Use case**: Centralized logging for pipelines

```bash
# Log pipeline execution
jn run pipeline.json --input-file data.csv 2>&1 | logger -t jn-pipeline

# Parse logs and analyze
journalctl -t jn-pipeline -o json | \
  jn cat - | \
  jq 'select(.MESSAGE | contains("ERROR"))' | \
  jn put error-summary.json
```

---

## 25. Testing with `bats`

**Tool**: Bats - Bash Automated Testing System

**Use case**: Test pipeline outputs

```bash
# test/pipeline.bats
#!/usr/bin/env bats

@test "pipeline produces valid JSON" {
  run jn run pipeline.json --input-file test/fixtures/input.csv --output-file /tmp/output.json
  [ "$status" -eq 0 ]
  run jq -e '.' /tmp/output.json
  [ "$status" -eq 0 ]
}

@test "pipeline filters correctly" {
  run jn cat test/fixtures/input.csv
  run bash -c "jn cat test/fixtures/input.csv | jq 'select(.amount > 100)' | jq -s length"
  [ "$output" -eq 5 ]
}

@test "pipeline handles missing file" {
  run jn run pipeline.json --input-file nonexistent.csv
  [ "$status" -ne 0 ]
}
```

```bash
# Run tests
bats test/pipeline.bats
```

---

## Summary: The Unix Philosophy

| Need | Tool | JN's Role |
|------|------|-----------|
| File watching | watchmedo, inotifywait | Transform data when triggered |
| Scheduling | cron, systemd timers | Run pipelines on schedule |
| Branching | tee | One input, multiple outputs |
| Parallelization | xargs, parallel | Process many files concurrently |
| Process management | systemd, supervisord | Keep pipelines running |
| Retries | bash loops | Transform data, retry externally |
| Dead letter queue | directories + bash | Transform, move on success/fail |
| Orchestration | Airflow, Prefect | Execute parameterized pipelines |
| Monitoring | Prometheus, Elasticsearch | Generate metrics from data |
| Notifications | Slack, email | Transform data, send alerts |
| Caching | Redis, files | Cache transformed results |
| Queuing | Kafka, Redis | Transform messages in stream |

**JN's superpower**: Simple, composable data transformation that integrates seamlessly with the Unix ecosystem.

Don't build what already exists. Use JN with the best tool for each job.
