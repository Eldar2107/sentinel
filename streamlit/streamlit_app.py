# streamlit_app.py – Streamlit dashboard for Sentinel
import streamlit as st
import requests
import pandas as pd
import time

API_URL = "http://backend:8000/api"

st.set_page_config(page_title="Sentinel Monitor", layout="wide")
st.title("Sentinel — Open Banking Monitor")
st.caption("Real‑time status from backend services")

# Sidebar for refresh interval
default_interval = 10
refresh_seconds = st.sidebar.slider("Refresh interval (seconds)", 5, 30, default_interval)

placeholder = st.empty()

while True:
    with placeholder.container():
        # Top metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            dashboard = None
            try:
                dashboard = requests.get(f"{API_URL}/dashboard", timeout=5).json()
            except Exception as e:
                st.error(f"Dashboard fetch error: {e}")
            if dashboard:
                st.metric("Overall Score", dashboard.get("overall_score", "‑"))
        with col2:
            uptime = None
            try:
                uptime = requests.get(f"{API_URL}/uptime", timeout=5).json()
            except Exception as e:
                st.error(f"Uptime fetch error: {e}")
            if uptime:
                st.metric("Avg Uptime", f"{uptime.get('average_pct', '‑')}%")
        with col3:
            latency = None
            try:
                latency = requests.get(f"{API_URL}/latency", timeout=5).json()
            except Exception as e:
                st.error(f"Latency fetch error: {e}")
            if latency:
                st.metric("Avg Latency (ms)", f"{latency.get('average_ms', 0):.0f}")

        st.subheader("Bank Scores")
        scores = None
        try:
            scores = requests.get(f"{API_URL}/scores", timeout=5).json()
        except Exception as e:
            st.error(f"Scores fetch error: {e}")
        if scores:
            df_scores = pd.DataFrame(scores).set_index("bank_id")
            st.dataframe(df_scores)

        st.subheader("Recent Test Results (last 10)")
        results = None
        try:
            results = requests.get(f"{API_URL}/results?limit=10", timeout=5).json()
        except Exception as e:
            st.error(f"Results fetch error: {e}")
        if results:
            df_res = pd.DataFrame(results)
            st.dataframe(df_res)
    time.sleep(refresh_seconds)
