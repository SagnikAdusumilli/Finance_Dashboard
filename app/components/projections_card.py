import streamlit as st
import math
from utils.data_loaders import load_user_data,load_networth_data, load_contri_data
from datetime import date

def render_projections_card():
    st.markdown('<div class="card-header">Projections</div>', unsafe_allow_html=True)
    user_data = load_user_data()
    tgt_age = user_data['age_target']
    tgt_sum = user_data['liquidity_target']
    cr = user_data['expected_annual_return']
    dob = user_data['date_of_birth']


    _, _, df_assets = load_networth_data()
    curr_balance = get_total_liquidity(df_assets)


    month_contri, total_contri, contri_df = load_contri_data()

    #get projected stats
    proj_age = get_projected_age(curr_balance, tgt_sum, total_contri, cr, int(dob[:4]))

    if user_data and len(df_assets) > 0:
      st.markdown(f'<div class="card-text">- Liquidity Target: ${tgt_sum:,}</div>',unsafe_allow_html=True)
      st.markdown(f'<div class="card-text">- Current Liqudity: {curr_balance:,}</div>',unsafe_allow_html=True)
      st.markdown(f'<div class="card-text">- Target Age: {tgt_age}</div>',unsafe_allow_html=True)
      st.markdown(f'<div class="card-text">- Projected Age: {proj_age}</div>',unsafe_allow_html=True)
      st.markdown(f'<div class="card-text">- Current contributions: ${month_contri:,} per month, ${total_contri:,} per year</div>',unsafe_allow_html=True)

     
    # st.markdown("""
    #     <div class="card-text">
    #         - <b>Retirement target:</b> $0.00 (Placeholder)<br>
    #         - <b>Age to retirement:</b> 0 (Placeholder)<br>
    #         - <b>Total contribution:</b> $0.00 (Placeholder)<br>
    #         - <b>Monthly contribution:</b> $0.00 (Placeholder)
    #     </div>
    # """, unsafe_allow_html=True)


def get_total_liquidity(df_assets):
    return df_assets[df_assets["include_in_projection"] == True]['balance'].sum()

def get_projected_age(curr_balance, target_sum, total_contri, cr, birth_year):
   curr_year = date.today().year
   return math.floor(math.log((target_sum + total_contri/cr)/ (curr_balance + total_contri/cr)) / math.log(1 + cr)) + curr_year - birth_year

   
