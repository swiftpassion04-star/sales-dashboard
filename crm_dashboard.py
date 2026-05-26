import streamlit as st

from customer360 import render_customer360


st.set_page_config(page_title="Customer 360", layout="wide")
render_customer360()
