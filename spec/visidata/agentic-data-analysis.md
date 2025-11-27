# Agentic Data Analysis: Why VisiData Beats Text-to-SQL

**Date:** 2025-11-25
**Author:** Claude
**Status:** Published

---

## Abstract

Text-to-SQL promised to democratize data analysis: ask a question in English, get SQL, get answers. In practice, it fails. The AI doesn't know your schema. The generated SQL is wrong. You can't see intermediate results. Debugging is a nightmare.

There's a better way: **agentic data analysis** using streaming pipelines, interactive exploration, and human-in-the-loop verification. This approach combines JN (an agent-native ETL framework) with VisiData (a terminal spreadsheet) to create a workflow where AI agents and humans collaborate on data exploration—each doing what they do best.

---

## The Text-to-SQL Illusion

### The Promise

```
User: "Show me customers who spent more than $1000 last month"
AI: SELECT * FROM customers c
    JOIN orders o ON c.id = o.customer_id
    WHERE o.total > 1000
    AND o.created_at >= '2024-10-01'
```

Looks great in demos. Falls apart in production.

### The Reality

**Problem 1: Schema Blindness**

The AI doesn't know your schema. Is it `customers` or `users`? Is the amount in `total`, `amount`, or `price`? Is the date `created_at`, `order_date`, or `timestamp`?

Text-to-SQL systems try to solve this with schema injection: dump the entire schema into the prompt. This works for toy databases with 5 tables. Enterprise databases have hundreds of tables, thousands of columns, and naming conventions that require institutional knowledge.

**Problem 2: The Black Box**

When the query returns wrong results, what do you do? You can't see intermediate steps. You can't verify assumptions. You're debugging SQL you didn't write, against a schema you may not fully understand, with no visibility into the AI's reasoning.

**Problem 3: All-or-Nothing Execution**

SQL is batch processing. The query runs, you get results. If something's wrong, you start over. There's no incremental exploration, no "let me check this intermediate result before continuing."

**Problem 4: The Impedance Mismatch**

Natural language is ambiguous. SQL is precise. Translating between them requires resolving ambiguities that often require domain knowledge the AI doesn't have.

"Customers who spent more than $1000" — is that per order? Total lifetime? Last month? Calendar month or rolling 30 days?

---

## The Agentic Alternative

What if instead of generating SQL, the AI helped you *explore* data interactively?

### The Workflow

```bash
# Step 1: Agent extracts data
jn cat http://myapi/orders | jn head -n 1000 | jn vd

# Step 2: Human explores in VisiData
# - Shift+F to see amount distribution
# - Filter to amounts > 1000
# - Join with customer data

# Step 3: Agent refines based on findings
jn cat http://myapi/orders | jn filter '.amount > 1000' | jn merge customers.json --on customer_id | jn vd

# Step 4: Human verifies and exports
# - Check results make sense
# - Export to CSV for report
```

### Why This Works

**1. Visibility at Every Step**

Every intermediate result is visible. When you run `jn head -n 10`, you see exactly what the data looks like. Field names, data types, null values—all visible before you write any transformation.

**2. Human-in-the-Loop Verification**

VisiData lets you *see* the data before committing to a transformation. `Shift+F` on the "amount" column shows the distribution instantly. You discover that 90% of orders are under $100. The "big spenders" query that seemed reasonable is actually returning 0.1% of records.

**3. Incremental Refinement**

Each step in the pipeline is independent. If the filter is wrong, change it and re-run. If you need to join another table, add it to the pipeline. No need to regenerate a monolithic SQL query.

**4. Agent Strengths + Human Strengths**

AI agents are great at:
- Discovering data sources
- Writing filter expressions
- Suggesting transformations
- Generating pipeline code

Humans are great at:
- Recognizing when data "looks wrong"
- Understanding business context
- Making judgment calls about edge cases
- Exploratory pattern recognition

The agentic approach lets each do what they do best.

---

## JN: The Agent-Native ETL Framework

JN provides the infrastructure for agentic data analysis:

### Universal Addressing

```bash
# Any data source with one syntax
jn cat data.csv
jn cat https://api.example.com/data~json
jn cat "gmail://inbox"
jn cat "mcp://server/resource"
```

Agents don't need to know how to connect to different data sources. They just need the address.

### Streaming by Default

```bash
# First results appear immediately
jn cat huge_dataset.csv | jn vd
```

No waiting for the entire dataset to load. See data immediately, explore incrementally.

### Composable Operations

```bash
# Filter (jq expressions)
jn cat orders.json | jn filter '.amount > 1000'

# Join (like SQL JOIN - adds matching records from right)
jn cat orders.json | jn join customers.json --on customer_id

# Merge (combines fields from another source into existing records)
jn cat orders.json | jn merge customer_details.json --on customer_id

# Chain everything
jn cat orders.json \
  | jn filter '.status == "completed"' \
  | jn join customers.json --on customer_id \
  | jn filter '.customer.region == "EMEA"' \
  | jn vd
```

Each operation is a simple, understandable step. Agents can generate these pipelines incrementally, and humans can verify each step.

### Profile-Based Authentication

```bash
# Agent discovers available APIs
jn profile list

# Agent uses profile without knowing credentials
jn cat http://salesforce/accounts
```

Agents work with logical names ("salesforce/accounts"), not raw credentials or connection strings.

---

## VisiData: The Interactive Component

VisiData is the human interface to agentic data analysis:

### Instant Statistics

```
Shift+I  →  See nulls, uniques, min/max/mean for every column
Shift+F  →  Frequency table for any column
```

In seconds, you understand the shape of your data. No writing queries to check data quality.

### Visual Filtering

```
|BRAF     →  Select all rows matching "BRAF"
"         →  Open selected rows as new sheet
```

Filter by pointing, not by writing WHERE clauses. See results immediately.

### Aggregation Without GROUP BY

```
1. Navigate to "region" column, press !
2. Navigate to "amount" column, press + and type "sum"
3. Press Shift+F
```

You just did `SELECT region, SUM(amount) FROM orders GROUP BY region` without writing SQL.

### Joins Without JOIN Syntax

```
1. Open orders in VisiData
2. Open customers in VisiData
3. Press & and select join type
```

Visual joins. See the result. Verify it makes sense. No debugging cryptic SQL errors.

---

## The Paradigm Shift

### Text-to-SQL: Batch Thinking

```
Question → SQL → Results → (Wrong?) → New Question → SQL → Results → ...
```

The feedback loop is slow. Each iteration requires a new natural language query, a new SQL generation, a new execution. Debugging happens in your head.

### Agentic Analysis: Stream Thinking

```
Extract → See → Filter → See → Join → See → Aggregate → See → Export
        ↑       ↑         ↑       ↑          ↑
      Verify  Verify    Verify  Verify     Verify
```

The feedback loop is instant. Each step is visible. You verify as you go. The AI agent can watch you explore and suggest next steps.

---

## Real-World Example: Analyzing Gene Data

### The Text-to-SQL Approach

```
User: "Find protein-coding genes on chromosome 7 related to cancer"

AI generates:
SELECT * FROM genes
WHERE type = 'protein-coding'
AND chromosome = '7'
AND description LIKE '%cancer%'

Problems:
- Is the column "type" or "gene_type" or "type_of_gene"?
- Is chromosome stored as string "7" or integer 7?
- Does "related to cancer" mean description contains "cancer"?
```

You run it. It fails. Or worse, it returns results that look plausible but are wrong.

### The Agentic Approach

```bash
# Step 1: Load and explore
jn head -n 1000 "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz" | jn vd

# In VisiData:
# - Shift+I to see all columns
# - Discover: column is "type_of_gene", chromosome is string
# - Shift+F on type_of_gene to see: "protein-coding" (most common)
# - Shift+F on chromosome to see distribution

# Step 2: Filter with verified column names
jn cat "https://..." | jn filter '.type_of_gene == "protein-coding" and .chromosome == "7"' | jn vd

# In VisiData:
# - See 1,234 genes on chromosome 7
# - Search descriptions for cancer: g/ then "cancer"
# - Find 23 matches
# - Select them, export

# Step 3: Agent learns from your exploration
# Next time: "The user prefers to verify column names first"
```

Total time: 3 minutes. Zero SQL debugging. High confidence in results.

---

## When to Use What

### Use Text-to-SQL When:
- Schema is simple and well-documented
- Query patterns are repetitive and well-tested
- You have strong SQL expertise to verify results
- The database has query optimization that matters

### Use Agentic Analysis When:
- Exploring unfamiliar data
- Schema is complex or poorly documented
- You need to verify data quality before analysis
- The analysis is exploratory, not routine
- You're working with APIs, files, or mixed data sources
- Collaboration between AI and human is valuable

---

## The Future: AI-Assisted Exploration

The next evolution is not AI generating queries for humans to run. It is AI *watching* humans explore and learning:

```
Human: [Opens VisiData, presses Shift+F on "status" column]
AI: "I notice the status column has 5 unique values. Want me to filter to active records?"

Human: [Joins two sheets, sees duplicate rows]
AI: "The join created 15% more rows than expected. This suggests a one-to-many relationship. Want me to aggregate or deduplicate?"

```

This is **collaborative intelligence**: AI provides context and suggestions, humans make decisions, and both learn from the interaction.

---

## Conclusion

Text-to-SQL is a solution to the wrong problem. It tries to remove humans from data analysis. Agentic data analysis embraces human judgment while automating the tedious parts.

The tools exist today:
- **JN** for streaming data pipelines (filter, join, merge)
- **VisiData** for interactive exploration
- **AI agents** for discovery and suggestion

The workflow is simple:
1. Agent extracts data
2. Human explores in VisiData
3. Agent suggests refinements
4. Human verifies and exports

No SQL. No black boxes. No debugging queries you did not write.

Just data flowing through pipes, visible at every step, with human intelligence applied where it matters most.

---

## References

- [JN: Agent-Native ETL Framework](https://github.com/botassembly/jn)
- [VisiData](https://www.visidata.org/)
- [Why Text-to-SQL Fails](https://arxiv.org/abs/2305.03111) - Academic analysis of Text-to-SQL limitations
- [The Streaming Manifesto](spec/done/arch-backpressure.md) - Why streaming beats batching
