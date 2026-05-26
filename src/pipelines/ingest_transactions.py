import duckdb
import pandas as pd
import os
from pathlib import Path
from datetime import datetime

# Configuration
DB_PATH = 'data/finance.db'
TRANSACTIONS_ROOT = 'data/manual/transactions'
SILVER_ROOT = 'data/silver'
MANIFEST_PATH = 'data/manifest_file.csv'

def setup_database(conn):
    """Initializes the database schema if not already present."""
    # Transaction_raw schema based on docs/Solution_Design/Data_model/data_model.txt
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Transaction_raw (
            date DATE,
            Name VARCHAR,
            withdrawl DOUBLE,
            income DOUBLE,
            Category VARCHAR,
            Account_Name VARCHAR,
            transaction_type VARCHAR,
            file_source VARCHAR,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Transaction_silver schema with single amount column
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Transaction_silver (
            date DATE,
            Name VARCHAR,
            amount DOUBLE,
            Category VARCHAR,
            Account_Name VARCHAR,
            transaction_type VARCHAR,
            file_source VARCHAR,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # file_manifest schema based on docs/Solution_Design/Data_model/data_model.txt
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_manifest (
            file_name VARCHAR PRIMARY KEY,
            row_count INTEGER,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

def get_loaded_files():
    """Reads the manifest file and returns a set of already loaded filenames."""
    if not os.path.exists(MANIFEST_PATH):
        return set()
    
    try:
        # We still use pandas for reading to easily get a set of filenames
        df_manifest = pd.read_csv(MANIFEST_PATH)
        return set(df_manifest['file_name'].tolist())
    except Exception:
        return set()

def update_manifest_file(conn):
    """Syncs the file_manifest table to the manifest_file.csv using DuckDB COPY."""
    conn.execute(f"COPY file_manifest TO '{MANIFEST_PATH}' (HEADER, DELIMITER ',')")

def ingest_transactions():
    # Ensure necessary directories exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(SILVER_ROOT, exist_ok=True)
    
    conn = duckdb.connect(DB_PATH)
    setup_database(conn)
    
    loaded_files = get_loaded_files()
    
    # Recursively find all CSV files in the transactions folder
    all_files = list(Path(TRANSACTIONS_ROOT).rglob('*.csv'))
    
    new_files_count = 0
    for file_path in all_files:
        file_name = str(file_path)
        
        if file_name in loaded_files:
            print(f"Skipping {file_name} (already loaded).")
            continue
            
        print(f"Processing {file_name}...")
        
        try:
            # Create a temporary view of the CSV to validate and count
            conn.execute(f"CREATE OR REPLACE TEMP VIEW temp_load AS SELECT * FROM read_csv_auto('{file_name}')")
            
            # Map columns to handle case-insensitivity and typos
            cols = conn.execute("DESCRIBE temp_load").fetchall()
            col_names = [c[0] for c in cols]
            
            date_col = next((c for c in col_names if c.lower() == 'date'), 'Date')
            withdraw_col = next((c for c in col_names if c.lower() == 'withdrawl'), 'withdrawl')
            account_col = next((c for c in col_names if c.lower() == 'account_name'), 'Account_Name')
            income_col = next((c for c in col_names if c.lower() == 'income'), 'income')
            category_col = next((c for c in col_names if c.lower() == 'category'), 'Category')
            name_col = next((c for c in col_names if c.lower() == 'name'), 'Name')
            type_col = next((c for c in col_names if c.lower() == 'transaction_type'), 'transaction_type')

            row_count = conn.execute("SELECT COUNT(*) FROM temp_load").fetchone()[0]
            
            # 1. Insert into the Transaction_raw table (DuckDB)
            conn.execute(f"""
                INSERT INTO Transaction_raw (date, Name, withdrawl, income, Category, Account_Name, transaction_type, file_source)
                SELECT 
                    "{date_col}", 
                    "{name_col}", 
                    "{withdraw_col}", 
                    "{income_col}", 
                    "{category_col}", 
                    "{account_col}", 
                    "{type_col}", 
                    '{file_name}'
                FROM temp_load
            """)

            # 2. Transform and Insert into Transaction_silver table
            conn.execute(f"""
                INSERT INTO Transaction_silver (date, Name, amount, Category, Account_Name, transaction_type, file_source)
                SELECT 
                    "{date_col}", 
                    "{name_col}", 
                    CASE 
                        WHEN LOWER("{type_col}") IN ('income', 'withdraw') 
                        THEN (COALESCE("{income_col}", 0) - COALESCE("{withdraw_col}", 0))
                        ELSE 0 
                    END as amount, 
                    "{category_col}", 
                    "{account_col}", 
                    "{type_col}", 
                    '{file_name}'
                FROM temp_load
            """)
            
            # 3. Write human-readable CSV to the silver layer
            # Now exporting directly from the Transaction_silver table
            base_filename = Path(file_name).stem
            csv_path = os.path.join(SILVER_ROOT, f"{base_filename}_standardized.csv")
            conn.execute(f"""
                COPY (
                    SELECT date, Name, amount, Category, Account_Name, transaction_type
                    FROM Transaction_silver
                    WHERE file_source = '{file_name}'
                ) TO '{csv_path}' (HEADER, DELIMITER ',')
            """)            
            
            # 4. Update the manifest in the database
            conn.execute("INSERT OR REPLACE INTO file_manifest (file_name, row_count) VALUES (?, ?)", (file_name, row_count))
            
            print(f"Successfully loaded {file_name} ({row_count} rows).")
            print(f"  -> Human-readable CSV (Silver): {csv_path}")
            new_files_count += 1
            
        except Exception as e:
            print(f"Error processing {file_name}: {e}")
            continue

    if new_files_count > 0:
        print(f"\nIngestion complete. Total new files loaded: {new_files_count}")
        update_manifest_file(conn)
    else:
        print("\nNo new files found for ingestion.")
        # Ensure manifest file exists for tracking
        if not os.path.exists(MANIFEST_PATH):
            update_manifest_file(conn)

    conn.close()

if __name__ == "__main__":
    ingest_transactions()
