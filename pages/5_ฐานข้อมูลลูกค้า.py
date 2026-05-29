import streamlit as st

from customer360 import render_customer360


st.set_page_config(page_title="ฐานข้อมูลลูกค้า", layout="wide")
render_customer360()
