import streamlit as st

def render_projections_card():
    st.markdown('<div class="card-header">Projections</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-text">
            - <b>Retirement target:</b> $0.00 (Placeholder)<br>
            - <b>Age to retirement:</b> 0 (Placeholder)<br>
            - <b>Total contribution:</b> $0.00 (Placeholder)<br>
            - <b>Monthly contribution:</b> $0.00 (Placeholder)
        </div>
    """, unsafe_allow_html=True)