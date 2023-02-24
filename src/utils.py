import streamlit as st
from src.session import run_auth
from src.data import DataCollector


def get_data(token):
    dc = DataCollector(token)
    dc.collect_more_items()
    return dc


def is_data_ready():
    # Set page config
    st.set_page_config(page_title="Task Analytics", layout="wide", page_icon="📊")

    # Check if user is authenticated and load data
    if 'data_is_ready' not in st.session_state:
        refresh_data()

    # If user is authenticated, return True
    return 'data_is_ready' in st.session_state


def refresh_data():
    token = run_auth()
    if token:
        with st.spinner("Getting your data :)"):
            colector = get_data(token)
            st.session_state["colector"] = colector
            st.session_state["tasks"] = colector.items
            st.session_state["user"] = colector.user
            st.session_state["collecting"] = colector.collecting
            st.session_state["data_is_ready"] = True
            st.info("Your data is loaded, you can start using this app now.")


def load_more_data():
    if 'colector' in st.session_state:
        colector = st.session_state["colector"]
        with st.spinner("Getting more data :)"):
            colector.collect_more_items()
            st.session_state["colector"] = colector
            st.session_state["tasks"] = colector.items
            st.session_state["user"] = colector.user
            st.session_state["collecting"] = colector.collecting
            st.session_state["data_is_ready"] = True
            st.info("Your data is loaded, you can start using this app now.")
