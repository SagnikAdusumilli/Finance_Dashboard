import streamlit as st
from utils.data_loaders import load_user_data,load_networth_data

def render_projections_card():
    st.markdown('<div class="card-header">Projections</div>', unsafe_allow_html=True)
    user_data = load_user_data()
    _, _, df_accounts = load_networth_data()

    if user_data and len(df_accounts) > 0:
      st.markdown(f'<div class="card-text">- Liquidity Target: ${user_data['liquidity_target']:,}</div>',unsafe_allow_html=True)
      st.markdown(f'<div class="card-text">- Target Age: {user_data['age_target']}</div>',unsafe_allow_html=True)
      #TODO actual projected target age
      #TODO total monthy projection
      # TODO total yearly projections

    # st.markdown("""
    #     <div class="card-text">
    #         - <b>Retirement target:</b> $0.00 (Placeholder)<br>
    #         - <b>Age to retirement:</b> 0 (Placeholder)<br>
    #         - <b>Total contribution:</b> $0.00 (Placeholder)<br>
    #         - <b>Monthly contribution:</b> $0.00 (Placeholder)
    #     </div>
    # """, unsafe_allow_html=True)
