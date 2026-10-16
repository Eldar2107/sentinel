# streamlit/app.py
import streamlit as st
import requests
import pandas as pd
import time

API_URL = "http://backend:8000/api"

st.set_page_config(page_title="Sentinel Monitor", layout="wide")

st.title("Sentinel — Open Banking Monitor")
st.caption("Real‑time status from backend services")

def fetch(endpoint: str):
    """GET JSON from backend, return dict or None."""
    try:
        r = requests.get(f"{API_URL}/{endpoint}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to load {endpoint}: {e}")
        return None

# Sidebar: refresh interval
refresh_seconds = st.sidebar.slider("Refresh interval (seconds)", min_value=5, max_value=30, value=10, step=1)

placeholder = st.empty()

while True:
    with placeholder.container():
        # Top metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            dashboard = fetch("dashboard")
            if dashboard:
                st.metric("Overall Score", dashboard.get("overall_score", "‑"))
        with col2:
            uptime = fetch("uptime")
            if uptime:
                st.metric("Avg Uptime", f"{uptime.get('average_pct', '‑')}%")
        with col3:
            latency = fetch("latency")
            if latency:
                st.metric("Avg Latency (ms)", f"{latency.get('average_ms', 0):.0f}")

        st.subheader("Bank Scores")
        scores = fetch("scores")
        if scores:
            df_scores = pd.DataFrame(scores)
            if not df_scores.empty:
                df_scores = df_scores.set_index("bank_id")
                st.dataframe(df_scores)

        st.subheader("Recent Test Results (last 10)")
        results = fetch("results?limit=10")
        if results:
            df_res = pd.DataFrame(results)
            if not df_res.empty:
                st.dataframe(df_res)

    time.sleep(refresh_seconds)
