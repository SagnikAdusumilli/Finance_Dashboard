import streamlit as st
import duckdb
import pandas as pd
import altair as alt
import os
from pathlib import Path

# Set page config
st.set_page_config(page_title="Finance Dashboard", layout="wide")

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "finance.db"

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
            SELECT account_id, account_name, balance
            FROM account_balances
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM account_balances)
        """)
        
        # Get total and date
        total_data = conn.execute("SELECT SUM(balance), (SELECT MAX(snapshot_date) FROM account_balances) FROM latest_balances").fetchone()
        
        # Get individual accounts
        df_accounts = conn.execute("SELECT account_name, balance FROM latest_balances ORDER BY balance DESC").df()

        conn.close()
        
        if total_data and total_data[0] is not None:
            return total_data[0], total_data[1], df_accounts
        return 0, None, pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading networth data: {e}")
        return 0, None, pd.DataFrame()

def main():
    # Sidebar Navigation Placeholders
    st.sidebar.title("Navigation")
    st.sidebar.radio("Go to", ["Networth", "Retirement", "Cash flow"])

    st.title("Financial Summary")
    
    # Custom CSS for larger font in cards
    st.markdown("""
        <style>
        .card-text {
            font-size: 22px !important;
        }
        .card-header {
            font-size: 30px !important;
            font-weight: bold;
            margin-bottom: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Top Row: Networth and Projections
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="card-header">Total Networth</div>', unsafe_allow_html=True)
        total_networth, latest_date, df_accounts = load_networth_data()
        
        if latest_date:
            st.markdown(f'<div class="card-text"><b>networth: ${total_networth:,.2f} as of {latest_date}</b></div>', unsafe_allow_html=True)
            for _, row in df_accounts.iterrows():
                st.markdown(f'<div class="card-text">- {row["account_name"]}: ${row["balance"]:,.2f}</div>', unsafe_allow_html=True)
        else:
            st.info("No networth data available. Run ingestion pipeline.")
            st.code("python src/pipelines/ingest_account_data.py")

    with col_right:
        st.markdown('<div class="card-header">Projections</div>', unsafe_allow_html=True)
        st.markdown("""
            <div class="card-text">
                - <b>Retirement target:</b> $0.00 (Placeholder)<br>
                - <b>Age to retirement:</b> 0 (Placeholder)<br>
                - <b>Total contribution:</b> $0.00 (Placeholder)<br>
                - <b>Monthly contribution:</b> $0.00 (Placeholder)
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Cash Flow Analysis Section
    st.header("Cash Flow Analysis")
    
    df_cashflow = load_cashflow_data()

    if not df_cashflow.empty:
        # Prepare data for the bar chart
        chart_df = df_cashflow[['month_label', 'month_start', 'cash_in', 'cash_out']].copy()
        chart_df = chart_df.rename(columns={'cash_in': 'Cash In', 'cash_out': 'Cash Out'})
        
        # Sort chronologically (oldest to newest)
        chart_df = chart_df.sort_values('month_start')
        
        # Melting the dataframe for Altair
        melted_df = chart_df.melt(id_vars=['month_label', 'month_start'], value_vars=['Cash In', 'Cash Out'], var_name='Type', value_name='Amount')
        
        # Create Altair chart with perfectly flush bars
        chart = alt.Chart(melted_df).mark_bar(width={'band': 1.0}, strokeWidth=0, stroke=None).encode(
            x=alt.X('month_label:N', title=None, sort=alt.EncodingSortField(field='month_start', order='ascending')),
            y=alt.Y('Amount:Q', title='Amount ($)'),
            color=alt.Color('Type:N', scale=alt.Scale(domain=['Cash In', 'Cash Out'], range=['#2ecc71', '#e74c3c'])),
            xOffset=alt.XOffset('Type:N', scale=alt.Scale(padding=0)) 
        ).properties(
            height=400
        ).configure_view(
            stroke=None
        )

        st.altair_chart(chart, width='stretch')

        # Summary Metrics (Rolling 3-Month Average)
        latest = df_cashflow.iloc[0]
        
        st.subheader("Summary Metrics (Rolling 3-Month Average)")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Avg Cash In", 
                value=f"${latest['rolling_3m_cash_in']:,.2f}"
            )
        
        with col2:
            st.metric(
                label="Avg Cash Out", 
                value=f"${latest['rolling_3m_cash_out']:,.2f}"
            )
            
        with col3:
            st.metric(
                label="Avg Net Cash Flow", 
                value=f"${latest['rolling_3m_net_cash_flow']:,.2f}",
                delta=f"{latest['rolling_3m_net_cash_flow']:,.2f}",
                delta_color="normal"
            )
            
    else:
        st.warning("No data found in Transaction_silver. Please run the ingestion pipeline first.")
        st.code("python src/pipelines/ingest_transactions.py")

if __name__ == "__main__":
    main()