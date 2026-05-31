import streamlit as st
import altair as alt
from utils.data_loaders import load_cashflow_data

def render_cashflow_section():
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

        st.altair_chart(chart, use_container_width=True)

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