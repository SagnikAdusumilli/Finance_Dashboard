import duckdb
import os
from datetime import datetime
import sys

# Configuration
DB_PATH = 'data/finance.db'
ACCOUNTS_CSV = 'data/manual/accounts/account_balances.csv'
CONTRIBUTIONS_CSV = 'data/manual/accounts/contributions.csv'

def setup_database(conn):
    """Initializes the database schema if not already present."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            snapshot_date DATE,
            account_id INTEGER,
            balance DOUBLE,
            PRIMARY KEY (snapshot_date, account_id)
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_contributions (
            snap_date DATE,
            account_id INTEGER,
            monthly_contribution_amnt DOUBLE,
            PRIMARY KEY (snap_date, account_id)
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

        # Create a view that cleans balance strings (removes commas/dollars) on the fly
        conn.execute(f"""
            CREATE OR REPLACE TEMP VIEW raw_balances AS 
            SELECT 
                account_id::INTEGER as account_id, 
                regexp_replace(balance::VARCHAR, '[,$]', '', 'g')::DOUBLE as balance 
            FROM read_csv_auto('{ACCOUNTS_CSV}', normalize_names=True)
        """)

        # Validation: Check for duplicate account_id in CSV
        dupes = conn.execute("SELECT account_id FROM raw_balances GROUP BY account_id HAVING COUNT(*) > 1").fetchall()
        if dupes:
            print(f"Failure: Duplicate account_id values exist in {ACCOUNTS_CSV}: {[d[0] for d in dupes]}")
            sys.exit(1)

        # 2. Load and Validate contributions.csv
        if not os.path.exists(CONTRIBUTIONS_CSV):
            print(f"Error: {CONTRIBUTIONS_CSV} not found.")
            sys.exit(1)

        # DuckDB handles the typo 'monthy_contriubution_amnt' by using normalize_names=True 
        # which results in 'monthy_contriubution_amnt'. We clean it just like balances.
        conn.execute(f"""
            CREATE OR REPLACE TEMP VIEW raw_contributions AS 
            SELECT 
                account_id::INTEGER as account_id, 
                regexp_replace(monthy_contriubution_amnt::VARCHAR, '[,$]', '', 'g')::DOUBLE as monthly_contribution_amnt
            FROM read_csv_auto('{CONTRIBUTIONS_CSV}', normalize_names=True)
        """)

        # Validation: Check for unknown account_id in contributions
        unknown = conn.execute("""
            SELECT c.account_id FROM raw_contributions c 
            LEFT JOIN raw_balances b ON c.account_id = b.account_id 
            WHERE b.account_id IS NULL
        """).fetchall()
        if unknown:
            print(f"Failure: {CONTRIBUTIONS_CSV} contains unknown account_id not in {ACCOUNTS_CSV}: {[u[0] for u in unknown]}")
            sys.exit(1)

        # 3. Process Account Balances (Bulk Upsert with Change Detection)
        pre_count = conn.execute("SELECT COUNT(*) FROM account_balances").fetchone()[0]
        
        # Upsert Logic:
        # 1. Insert/Update today's record if it differs from the most recent PREVIOUS balance
        # 2. Use ON CONFLICT to handle multiple runs on the same day
        conn.execute(f"""
            INSERT INTO account_balances (snapshot_date, account_id, balance)
            SELECT 
                '{today}' as snapshot_date, 
                curr.account_id, 
                curr.balance
            FROM raw_balances curr
            LEFT JOIN (
                -- Get the most recent balance record BEFORE today for each account
                SELECT account_id, balance, 
                       ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY snapshot_date DESC) as rn
                FROM account_balances
                WHERE snapshot_date < '{today}'
            ) prev ON curr.account_id = prev.account_id AND prev.rn = 1
            WHERE prev.balance IS NULL OR round(prev.balance, 2) != round(curr.balance, 2)
            ON CONFLICT (snapshot_date, account_id) 
            DO UPDATE SET balance = excluded.balance
            WHERE round(account_balances.balance, 2) != round(excluded.balance, 2)
        """)
        
        post_count = conn.execute("SELECT COUNT(*) FROM account_balances").fetchone()[0]
        new_snapshots = post_count - pre_count
        
        # 4. Process Contributions (Bulk Upsert)
        conn.execute(f"""
            INSERT INTO account_contributions (snap_date, account_id, monthly_contribution_amnt)
            SELECT '{today}', account_id, monthly_contribution_amnt FROM raw_contributions
            ON CONFLICT (snap_date, account_id) 
            DO UPDATE SET monthly_contribution_amnt = excluded.monthly_contribution_amnt
            WHERE round(account_contributions.monthly_contribution_amnt, 2) != round(excluded.monthly_contribution_amnt, 2)
        """)

        # Get Summary Stats
        acc_processed = conn.execute("SELECT COUNT(DISTINCT account_id) FROM raw_balances").fetchone()[0]
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
