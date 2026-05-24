# Finance_Dashboard
This a Data engineering and analytics project I'm building to track and analysize my personal finance. 
It is going to track: 
- monthy cashflow
- monthly income
- monthly transactions
- Project future networth and savings

## MVP 1 Scope

### Data Sources
- Manually downloaded bank and credit card transaction files
- Monthly investment/account balance snapshots
- User-entered assumptions such as retirement target, savings target, and liquid cash goal

### Data Layers
- Bronze: raw uploaded files stored locally without modification
- Silver: validated and standardized transaction/account data
- Gold: monthly finance summaries for dashboard reporting

### Processing
Python scripts load raw files, validate schema, write standardized records into DuckDB, and generate aggregated tables for analysis.

### Dashboard
Streamlit provides:
- Monthly categorized cash flow
- Monthly income and spending
- Net worth tracking
- Savings projections
- Retirement target projections
- Data upload and validation feedback
- Editable assumptions for retirement age, target amount, monthly contribution, and liquid cash goal
