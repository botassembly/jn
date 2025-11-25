#!/usr/bin/env python3
"""Setup test data for the adapter-merge demo."""

import json
import subprocess
from pathlib import Path

DEMO_DIR = Path(__file__).parent


def setup_duckdb():
    """Create DuckDB database with treatment data."""
    db_path = DEMO_DIR / "genie.duckdb"

    # Create database with sample clinical data
    subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "duckdb",
            "python",
            "-c",
            f"""
import duckdb
conn = duckdb.connect('{db_path}')

# Create treatments table (clinical trial data)
conn.execute('''
    CREATE OR REPLACE TABLE treatments (
        patient_id VARCHAR,
        regimen VARCHAR,
        os_months INTEGER,
        response VARCHAR
    )
''')

# Insert sample data (simulated clinical data)
conn.execute('''
    INSERT INTO treatments VALUES
    ('P001', 'FOLFOX', 24, 'CR'),
    ('P002', 'FOLFIRI', 18, 'PR'),
    ('P003', 'FOLFOX', 36, 'CR'),
    ('P004', 'FOLFIRI', 12, 'SD'),
    ('P005', 'FOLFOX', 15, 'PR'),
    ('P006', 'FOLFIRI', 30, 'CR'),
    ('P007', 'FOLFOX', 9, 'PD'),
    ('P008', 'FOLFIRI', 22, 'PR'),
    ('P009', 'FOLFOX', 28, 'CR'),
    ('P010', 'FOLFIRI', 16, 'SD')
''')

conn.close()
print(f'Created DuckDB database: {db_path}')
""",
        ],
        check=True,
    )


def setup_duckdb_profile():
    """Create DuckDB profile with optional parameter pattern."""
    profile_dir = DEMO_DIR / "profiles" / "duckdb" / "genie"
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Create meta file with relative path (relative to _meta.json location)
    # From profiles/duckdb/genie/ back to demos/adapter-merge/ is ../../../
    meta = {
        "driver": "duckdb",
        "path": "../../../genie.duckdb",
        "description": "GENIE clinical data demo",
    }
    (profile_dir / "_meta.json").write_text(json.dumps(meta, indent=2))

    # Create SQL query with optional parameter pattern
    (profile_dir / "treatment.sql").write_text(
        """-- Treatment query with optional filters
-- Parameters: regimen, min_survival

SELECT
    patient_id,
    regimen,
    os_months,
    response
FROM treatments
WHERE
    ($regimen IS NULL OR regimen = $regimen)
    AND
    ($min_survival IS NULL OR os_months >= $min_survival)
ORDER BY os_months DESC;
"""
    )

    print(f"Created DuckDB profile: {profile_dir}")


def setup_sales_csv():
    """Create sample sales CSV file."""
    csv_path = DEMO_DIR / "sales.csv"
    csv_path.write_text(
        """date,region,product,amount
2024-01-15,East,Widget,500
2024-01-16,West,Gadget,750
2024-01-17,East,Widget,1200
2024-01-18,West,Widget,300
2024-01-19,East,Gadget,900
2024-01-20,West,Gadget,1500
2024-01-21,East,Widget,450
2024-01-22,West,Widget,2000
"""
    )
    print(f"Created sales CSV: {csv_path}")


def setup_jq_profiles():
    """Create JQ profiles for native argument binding."""
    profile_dir = DEMO_DIR / "profiles" / "jq" / "sales"
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Filter by region
    (profile_dir / "by_region.jq").write_text(
        """# Filter sales by region
# Parameters: region
select(.region == $region)
"""
    )

    # Filter by threshold
    (profile_dir / "above_threshold.jq").write_text(
        """# Filter sales above threshold
# Parameters: threshold
select((.amount | tonumber) > ($threshold | tonumber))
"""
    )

    print(f"Created JQ profiles: {profile_dir}")


if __name__ == "__main__":
    print("Setting up adapter-merge demo data...")
    print()
    setup_duckdb()
    setup_duckdb_profile()
    setup_sales_csv()
    setup_jq_profiles()
    print()
    print("Setup complete! Run ./run_examples.sh to see the demo.")
