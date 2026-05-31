import streamlit as st
import sys
import os

# Add the current directory to sys.path to allow imports from utils and components
sys.path.append(os.path.dirname(__file__))

from components.networth_card import render_networth_card
from components.projections_card import render_projections_card
from components.cashflow_section import render_cashflow_section

# Set page config
st.set_page_config(page_title="Finance Dashboard", layout="wide")

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
        render_networth_card()

    with col_right:
        render_projections_card()

    st.markdown("---")

    # Cash Flow Analysis Section
    render_cashflow_section()

if __name__ == "__main__":
    main()