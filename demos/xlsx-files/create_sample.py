#!/usr/bin/env python3
"""
Create sample budget.xlsx file for demo
"""

try:
    from openpyxl import Workbook
except ImportError:
    print("ERROR: openpyxl not installed")
    print("Install with: pip install openpyxl")
    exit(1)

# Sample budget data
budget_data = [
    ["Month", "Category", "Description", "Amount"],
    ["January", "Engineering", "Software Licenses", "1200"],
    ["January", "Marketing", "Ad Campaign", "3500"],
    ["January", "Operations", "Office Rent", "4000"],
    ["January", "HR", "Recruiting", "800"],
    ["February", "Engineering", "Cloud Services", "2200"],
    ["February", "Marketing", "Content Creation", "1500"],
    ["February", "Operations", "Utilities", "450"],
    ["February", "Sales", "CRM Software", "600"],
    ["March", "Engineering", "Development Tools", "950"],
    ["March", "Marketing", "Social Media Ads", "2800"],
    ["March", "Operations", "Office Supplies", "320"],
    ["March", "HR", "Training Programs", "1200"],
    ["April", "Engineering", "API Services", "1800"],
    ["April", "Marketing", "Email Marketing", "900"],
    ["April", "Operations", "Equipment", "2500"],
    ["April", "Sales", "Travel Expenses", "1400"],
    ["May", "Engineering", "Infrastructure", "3200"],
    ["May", "Marketing", "SEO Services", "1800"],
    ["May", "Operations", "Maintenance", "650"],
    ["May", "HR", "Benefits", "2200"],
]

# Create workbook
wb = Workbook()
ws = wb.active
ws.title = "Budget 2024"

# Write data
for row in budget_data:
    ws.append(row)

# Save file
filename = "budget.xlsx"
wb.save(filename)

print(f"✓ Created {filename}")
print(f"  Records: {len(budget_data) - 1}")
print(f"  Categories: Engineering, Marketing, Operations, HR, Sales")
print(f"  Months: January - May")
