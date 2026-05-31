import duckdb
import os
from datetime import datetime
import sys

# Configuration
DB_PATH = 'data/finance.db'
ACCOUNTS_CSV = 'data/manual/accounts/asset_balances.csv'
CONTRIBUTIONS_CSV = 'data/manual/accounts/contributions.csv'

def setup_database(conn):
    """Initializes the database schema if not already present."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            snapshot_date DATE,
            asset_id INTEGER,
            asset_name VARCHAR,
            asset_type VARCHAR,
            include_in_projection BOOLEAN,
            balance DOUBLE,
            row_hash VARCHAR,
            PRIMARY KEY (snapshot_date, asset_id)
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_contributions (
            snap_date DATE,
            asset_id INTEGER,
            monthly_contribution_amnt DOUBLE,
            PRIMARY KEY (snap_date, asset_id)
        );
    """)

def ingest_account_data():
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = duckdb.connect(DB_PATH)
    setup_database(conn)
    
    today = datetime.now().date()
    
    try:
        # 1. Load and Validate account_balances.csv using DuckDB
        if not os.path.exists(ACCOUNTS_CSV):
            print(f"Error: {ACCOUNTS_CSV} not found.")
            sys.exit(1)

        # Strictly require asset_id and account_name
        col_names = conn.execute(f"SELECT * FROM read_csv_auto('{ACCOUNTS_CSV}', normalize_names=True) LIMIT 0").df().columns
        required_cols = ['asset_id', 'asset_name']
        missing_cols = [col for col in required_cols if col not in col_names]
        if missing_cols:
            print(f"Failure: Required column(s) {missing_cols} missing in {ACCOUNTS_CSV}")
            sys.exit(1)

        # Create a view that cleans balance strings (removes commas/dollars) on the fly
        conn.execute(f"""
            CREATE OR REPLACE TEMP VIEW raw_balances AS 
            WITH cleaned_csv AS (
                SELECT 
                    asset_id::INTEGER as aid, 
                    asset_name::VARCHAR as aname,
                    asset_type::VARCHAR as atype,
                    include_in_projection::BOOLEAN as aproj,
                    regexp_replace(balance::VARCHAR, '[,$]', '', 'g')::DOUBLE as abalance
                FROM read_csv_auto('{ACCOUNTS_CSV}', normalize_names=True)
            )
            SELECT 
                aid as asset_id,
                aname as asset_name,
                atype as asset_type,
                aproj as include_in_projection,
                abalance as balance,
                md5(
                    concat_ws('|',
                    coalesce(aname, '<NULL>'),
                    coalesce(atype, '<NULL>'),
                    coalesce(aproj::VARCHAR, '<NULL>'),
                    coalesce(round(abalance, 2)::VARCHAR, '<NULL>')
                    )
                ) AS row_hash
            FROM cleaned_csv
        """)

        # Validation: Check for duplicate asset_id in CSV
        dupes = conn.execute("SELECT asset_id FROM raw_balances GROUP BY asset_id HAVING COUNT(*) > 1").fetchall()
        if dupes:
            print(f"Failure: Duplicate asset_id values exist in {ACCOUNTS_CSV}: {[d[0] for d in dupes]}")
            sys.exit(1)

        # 2. Load and Validate contributions.csv
        if not os.path.exists(CONTRIBUTIONS_CSV):
            print(f"Error: {CONTRIBUTIONS_CSV} not found.")
            sys.exit(1)

        conn.execute(f"""
            CREATE OR REPLACE TEMP VIEW raw_contributions AS 
            SELECT 
                asset_id::INTEGER as aid_contrib, 
                regexp_replace(monthy_contriubution_amnt::VARCHAR, '[,$]', '', 'g')::DOUBLE as monthly_contribution_amnt
            FROM read_csv_auto('{CONTRIBUTIONS_CSV}', normalize_names=True)
        """)

        # Validation: Check for unknown asset_id in contributions
        unknown = conn.execute("""
            SELECT c.aid_contrib FROM raw_contributions c 
            LEFT JOIN raw_balances b ON c.aid_contrib = b.asset_id 
            WHERE b.asset_id IS NULL
        """).fetchall()
        if unknown:
            print(f"Failure: {CONTRIBUTIONS_CSV} contains unknown asset_id(s) not in {ACCOUNTS_CSV}: {[u[0] for u in unknown]}")
            sys.exit(1)

        # 3. Process Account Balances (Bulk Upsert with Change Detection)
        pre_count = conn.execute("SELECT COUNT(*) FROM account_balances").fetchone()[0]
        
        conn.execute(f"""
            INSERT INTO account_balances 
                     (snapshot_date, asset_id, asset_name, asset_type, include_in_projection, balance, row_hash)
            SELECT 
                '{today}' as snapshot_date, 
                curr.asset_id, 
                curr.asset_name,
                curr.asset_type,
                curr.include_in_projection,
                curr.balance,
                curr.row_hash
            FROM raw_balances curr
            LEFT JOIN (
                SELECT asset_id, row_hash, 
                       ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY snapshot_date DESC) as rn
                FROM account_balances
            ) prev ON curr.asset_id = prev.asset_id AND prev.rn = 1
            WHERE prev.asset_id is NULL OR prev.row_hash != curr.row_hash
            ON CONFLICT (snapshot_date, asset_id) 
            DO UPDATE SET 
                asset_name = excluded.asset_name,
                asset_type = excluded.asset_type,
                include_in_projection = excluded.include_in_projection,
                balance = excluded.balance,
                row_hash = excluded.row_hash
            WHERE account_balances.row_hash != excluded.row_hash
        """)
        
        post_count = conn.execute("SELECT COUNT(*) FROM account_balances").fetchone()[0]
        new_snapshots = post_count - pre_count
        
        # 4. Process Contributions (Bulk Upsert)
        conn.execute(f"""
            INSERT INTO account_contributions (snap_date, asset_id, monthly_contribution_amnt)
            SELECT '{today}', aid_contrib, monthly_contribution_amnt FROM raw_contributions
            ON CONFLICT (snap_date, asset_id) 
            DO UPDATE SET monthly_contribution_amnt = excluded.monthly_contribution_amnt
            WHERE round(account_contributions.monthly_contribution_amnt, 2) != round(excluded.monthly_contribution_amnt, 2)
        """)

        # Get Summary Stats
        acc_processed = conn.execute("SELECT COUNT(DISTINCT asset_id) FROM raw_balances").fetchone()[0]
        contrib_processed = conn.execute("SELECT COUNT(*) FROM raw_contributions").fetchone()[0]
        
        print("\nETL Job Summary (SQL Optimized):")
        print(f"- Accounts processed: {acc_processed}")
        print(f"- New balance snapshots added: {new_snapshots}")
        print(f"- Contributions processed: {contrib_processed}")

    except Exception as e:
        print(f"Error during ingestion: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    ingest_account_data()
