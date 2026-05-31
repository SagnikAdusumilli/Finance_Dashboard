import duckdb
import pandas as pd
from pathlib import Path
import streamlit as st
import json

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "finance.db"
USER_CONFIG_PATH = BASE_DIR / "data" / "manual" / "user_config.json"

def load_user_data():

    if not USER_CONFIG_PATH.exists():
        return {}
    try: 
        with open(USER_CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return {}




def load_cashflow_data():
    """Loads and aggregates cashflow data from Transaction_silver."""
    if not DB_PATH.exists():
        return pd.DataFrame()

    try:
        conn = duckdb.connect(str(DB_PATH))
        
        # Query to aggregate by month and calculate rolling averages
        query = """
        WITH monthly_totals AS (
            SELECT
                date_trunc('month', date) as month_start,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as cash_in,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as cash_out,
                SUM(amount) as net_cash_flow
            FROM Transaction_silver
            GROUP BY 1
        ),
        rolling_metrics AS (
            SELECT
                month_start,
                cash_in,
                cash_out,
                net_cash_flow,
                AVG(cash_in) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as rolling_3m_cash_in,
                AVG(cash_out) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as rolling_3m_cash_out,
                AVG(net_cash_flow) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as rolling_3m_net_cash_flow
            FROM monthly_totals
        )
        SELECT 
            strftime(month_start, '%b %Y') as month_label,
            month_start,
            cash_in,
            cash_out,
            net_cash_flow,
            rolling_3m_cash_in,
            rolling_3m_cash_out,
            rolling_3m_net_cash_flow
        FROM rolling_metrics
        ORDER BY month_start DESC
        LIMIT 6
        """
        df = conn.execute(query).df()
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def load_networth_data():
    """Loads the latest account balances and calculates total networth."""
    if not DB_PATH.exists():
        return 0, None, pd.DataFrame()

    try:
        conn = duckdb.connect(str(DB_PATH))
        
        # Check if table exists
        table_exists = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'account_balances'").fetchone()[0]
        if not table_exists:
            conn.close()
            return 0, None, pd.DataFrame()

        # Create temp view for the latest snapshot
        conn.execute("""
            CREATE OR REPLACE TEMP VIEW latest_balances AS
            SELECT asset_id, asset_name, balance
            FROM account_balances
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM account_balances)
        """)
        
        # Get total and date
        total_data = conn.execute("SELECT SUM(balance), (SELECT MAX(snapshot_date) FROM account_balances) FROM latest_balances").fetchone()
        
        # Get individual accounts
        df_accounts = conn.execute("SELECT asset_name, balance FROM latest_balances ORDER BY balance DESC").df()

        conn.close()
        
        if total_data and total_data[0] is not None:
            return total_data[0], total_data[1], df_accounts
        return 0, None, pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading networth data: {e}")
        return 0, None, pd.DataFrame()
