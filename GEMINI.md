# Finance Dashboard Project Instructions

This project is a personal finance tracking and analysis platform built with Python, DuckDB, and Streamlit.

## Architecture & Data Flow

The project follows a Medallion Architecture (Bronze -> Silver -> Gold) using local files and DuckDB:

- **Bronze:** 
    - Raw CSV files stored in `data/manual/transactions/`.
    - Loaded into the `Transaction_raw` table in `data/finance.db`.
- **Silver:** 
    - Transformed data in the `Transaction_silver` table in `data/finance.db`. 
    - Standardized human-readable CSVs exported to `data/silver/`.
    - Key Transformation: `amount` = `income` - `withdrawal`.
- **Gold:** Aggregated monthly summaries and reporting tables for dashboard consumption.

### Component Map
- `app/`: Streamlit dashboard code for visualization and data management.
- `pipelines/`: Python scripts for data loading and transformations.
    - `ingest_transactions.py`: The main ETL script for processing raw transaction files.
- `schemas/`: Definitions for data structures and validation rules.
- `data/`: Local storage for the different medallion layers and the DuckDB database (`finance.db`).
- `config/`: Application and pipeline configurations.

## Development Standards

- **Language:** Python 3.x (libraries: `duckdb`, `pandas`, `pathlib`)
- **Database:** DuckDB for analytical processing and storage.
- **Frontend:** Streamlit for the user interface.
- **ETL Strategy:**
    - Use DuckDB's native `COPY` and `read_csv_auto` for high-performance data movement.
    - Maintain idempotency using a `file_manifest` table and `data/manifest_file.csv`.

## Key Workflows

### Data Ingestion
1. Place raw bank/credit card CSV files in subfolders of `data/manual/transactions/`.
2. Run the ingestion pipeline:
   ```bash
   python pipelines/ingest_transactions.py
   ```
3. The script will:
    - Check the manifest to avoid duplicate loads.
    - Load raw data into `Transaction_raw`.
    - Transform and load standardized data into `Transaction_silver`.
    - Export standardized CSVs to `data/silver/`.
    - Update the manifest.

### Dashboard Updates
- Streamlit app provides interfaces for:
    - Categorized cash flow analysis.
    - Net worth tracking and savings projections.
    - Manual entry of account balances and financial assumptions.
