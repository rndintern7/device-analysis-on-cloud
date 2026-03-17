import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- CUSTOM CSS FOR FONT SIZES & LOGO ALIGNMENT ---
st.markdown("""
    <style>
    /* Metric Label (Heading) Styling - Increased to 28px */
    [data-testid="stMetricLabel"] p {
        font-size: 28px !important;
        font-weight: bold !important;
        color: #FFFFFF !important;
        line-height: 1.2 !important;
    }
    /* Metric Value (Number) Styling - Decreased to 16px to prevent "..." */
    [data-testid="stMetricValue"] div {
        font-size: 16px !important;
        color: #00CCFF !important;
        white-space: nowrap !important;
    }
    /* Remove default padding to allow more space for numbers */
    [data-testid="stMetric"] {
        width: fit-content !important;
        padding-right: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- TOP HEADER SECTION ---
header_col1, header_col2 = st.columns([4, 1])

with header_col1:
    st.title("Mtrol Full-Cycle Raw Parameter Analysis")

with header_col2:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.write("*(Logo)*")

# --- DATA CONSTANTS ---
MT3_VALS = {
    "flow": {"max": 303.54, "min": 0.00, "ppm": 2449.99, "unit": "Kg/Hr"},
    "opening": {"max": 22.01, "min": 0.00, "ppm": 2449.99, "unit": "%"},
    "p1": {"max": 10.60, "min": 0.00, "ppm": 21455.76, "unit": "bar"},
    "p2": {"max": 10.06, "min": 0.00, "ppm": 20355.54, "unit": "bar"}
}

MT4_VALS = {
    "flow": {"max": 275.11, "min": 0.00, "ppm": 2170.41, "unit": "Kg/Hr"},
    "opening": {"max": 19.50, "min": 0.00, "ppm": 2170.41, "unit": "%"},
    "p1": {"max": 5.37, "min": 5.31, "ppm": 129.91, "unit": "bar"},
    "p2": {"max": 10.74, "min": 10.59, "ppm": 310.21, "unit": "bar"}
}

# --- DATA LOADING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    targets = ["flow", "opening", "p1", "p2", "temp", "chamber"]
    for col in df.columns:
        if col != time_col and any(t in col.lower() for t in targets):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    return df, time_col

# --- MAIN LOGIC ---
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    device_mode = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    
    data_lookup = MT4_VALS if device_mode == "Mtrol 4" else MT3_VALS
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    available_params = [c for c in df.columns if any(t in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if available_params and temp_col:
        selected_param = st.sidebar.selectbox("🎯 Select Parameter", available_params)
        clean_key = next((k for k in ["flow", "opening", "p1", "p2"] if k in selected_param.lower()), "p1")
        unit = data_lookup[clean_key]["unit"]

        # --- METRICS SECTION ---
        st.write("---")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        m1.metric(f"Max {selected_param}", f"{float(data_lookup[clean_key]['max']):.2f} {unit}")
        m2.metric(f"Min {selected_param}", f"{float(data_lookup[clean_key]['min']):.2f} {unit}")
        m3.metric("Max Chamber Temp", f"{df[temp_col].max():.2f}°C")
        m4.metric("Min Chamber Temp", f"{df[temp_col].min():.2f}°C")
        m5.metric("Specified PPM", f"{float(data_lookup[clean_key]['ppm']):.2f}")
        st.write("---")

        # --- PLOT ---
        valid_df = df[[time_col, selected_param, temp_col]].dropna().copy()
        start_time, end_time = valid_df[time_col].min(), valid_df[time_col].max()
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[selected_param], name="Raw Data"), secondary_y=False)
        fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], name="Temp", line=dict(dash='dot')), secondary_y=True)

        fig.update_layout(
            template="plotly_dark", height=600,
            xaxis=dict(type='date', range=[start_time, end_time]),
            yaxis2=dict(range=[-20, 70], dtick=10)
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Upload CSV to begin.")
