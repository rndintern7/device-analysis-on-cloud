import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- CONSTANTS ---
TEMP_DELTA_FIXED = 89.85  

# Data provided by user for metrics display
MT3_DATA = {
    "flow": {"max": 303.5447, "min": 0.0, "ppm": 2449.9944}, # Adjusted to match user list logic
    "opening": {"max": 22.0132, "min": 0.0, "ppm": 2449.9944},
    "p1": {"max": 10.6029, "min": 0.0, "ppm": 21455.7595},
    "p2": {"max": 10.0592, "min": 0.0, "ppm": 20355.5420},
    "flow_range": 200.0
}

MT4_DATA = {
    "flow": {"max": 275.1067, "min": 0.0, "ppm": 2170.4062},
    "opening": {"max": 19.5011, "min": 0.0, "ppm": 2170.4062},
    "p1": {"max": 5.3704, "min": 5.3062, "ppm": 129.9134},
    "p2": {"max": 10.7396, "min": 10.5863, "ppm": 310.2139},
    "flow_range": 500.0
}

def get_ref_range(device_mode, clean_name):
    if "flow" in clean_name: return 500.0 if "4" in device_mode else 200.0
    if "opening" in clean_name: return 100.0
    if "p1" in clean_name or "p2" in clean_name: return 17.0
    return 1.0

# --- DATA CLEANING ---
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

# --- MAIN UI ---
st.title("Mtrol Full-Cycle Stability Dashboard")

uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    device_mode = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_mode}")
    
    data_dict = MT4_DATA if device_mode == "Mtrol 4" else MT3_DATA
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    available_params = [c for c in df.columns if any(t in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if available_params and temp_col:
        selected_param = st.sidebar.selectbox("🎯 Select Parameter", available_params)
        clean_key = next((k for k in ["flow", "opening", "p1", "p2"] if k in selected_param.lower()), "p1")
        
        # --- TOP METRICS (As per your exact values) ---
        st.subheader(f"📊 {device_mode} Global Metrics for {selected_param}")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        m1.metric(f"Max {selected_param}", f"{data_dict[clean_key]['max']}")
        m2.metric(f"Min {selected_param}", f"{data_dict[clean_key]['min']}")
        m3.metric("Max Chamber Temp", f"{df[temp_col].max():.2f}°C")
        m4.metric("Min Chamber Temp", f"{df[temp_col].min():.2f}°C")
        m5.metric("Specified PPM", f"{data_dict[clean_key]['ppm']}")

        # --- DYNAMIC PLOT CALCULATION ---
        ref_range = get_ref_range(device_mode, clean_key)
        valid_df = df[[time_col, selected_param, temp_col]].dropna().copy()
        
        # Expanding drift for plot synchronization
        current_max = valid_df[selected_param].expanding().max()
        current_min = valid_df[selected_param].expanding().min()
        drift_delta = current_max - current_min
        valid_df['PPM_Stability'] = (drift_delta * 1000000) / (TEMP_DELTA_FIXED * ref_range)

        # --- THE PLOT ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df['PPM_Stability'], 
                                   name="PPM Stability", line=dict(color="#00CCFF", width=2)), secondary_y=False)
        fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], 
                                   name="Chamber Temp", line=dict(color="#FFD700", width=1.5, dash='dot')), secondary_y=True)

        fig.update_layout(template="plotly_dark", height=600,
                          xaxis=dict(title="Time", rangeslider=dict(visible=True)),
                          yaxis=dict(title="PPM", range=[0, max(100, data_dict[clean_key]['ppm'])]), 
                          yaxis2=dict(title="Temp (°C)", side='right', range=[0, 100]))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Check CSV columns for 'Chamber Temp' and Mtrol parameters.")
else:
    st.info("Upload Mtrol CSV to start.")
