import streamlit as st
from utils.data_loaders import load_networth_data

def render_networth_card():
    st.markdown('<div class="card-header">Total Networth</div>', unsafe_allow_html=True)
    total_networth, latest_date, df_assets = load_networth_data()
    
    if latest_date:
        st.markdown(f'<div class="card-text"><b>networth: ${total_networth:,.2f} as of {latest_date}</b></div>', unsafe_allow_html=True)
        for _, row in df_assets.iterrows():
            st.markdown(f'<div class="card-text">- {row["asset_name"]}: ${row["balance"]:,.2f}</div>', unsafe_allow_html=True)
    else:
        st.info("No networth data available. Run ingestion pipeline.")
        st.code("python src/pipelines/ingest_account_data.py")
