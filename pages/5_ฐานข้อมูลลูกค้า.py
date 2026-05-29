import streamlit as st

from customer360 import render_customer360
from nav_utils import render_sidebar_nav


st.set_page_config(page_title="ฐานข้อมูลลูกค้า", layout="wide")
render_sidebar_nav()
render_customer360()
