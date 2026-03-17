import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- DATA CONSTANTS (Your Exact Provided Values) ---
MT3_VALS = {
    "flow": {"max": 303.5447, "min": 0.0, "ppm": 2449.9944, "unit": "Kg/Hr"},
    "opening": {"max": 22.0132, "min": 0.0, "ppm": 2449.9944, "unit": "%"},
    "p1": {"max": 10.6029, "min": 0.0, "ppm": 21455.7595, "unit": "bar"},
    "p2": {"max": 10.0592, "min": 0.0, "ppm": 20355.5420, "unit": "bar"}
}

MT4_VALS = {
    "flow": {"max": 275.1067, "min": 0.0, "ppm": 2170.4062, "unit": "Kg/Hr"},
    "opening": {"max": 19.5011, "min": 0.0, "ppm": 2170.4062, "unit": "%"},
    "p1": {"max": 5.3704, "min": 5.3062, "ppm": 129.9134, "unit": "bar"},
    "p2": {"max": 10.7396, "min": 10.5863, "ppm": 310.2139, "unit": "bar"}
}

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
st.title("Mtrol Full-Cycle Raw Parameter Analysis")

uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    device_mode = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_mode}")
    
    data_lookup = MT4_VALS if device_mode == "Mtrol 4" else MT3_VALS
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    available_params = [c for c in df.columns if any(t in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if available_params and temp_col:
        selected_param = st.sidebar.selectbox("🎯 Select Parameter to Plot", available_params)
        
        # Identify which parameter type we are looking at for the metrics display
        clean_key = next((k for k in ["flow", "opening", "p1", "p2"] if k in selected_param.lower()), "p1")
        unit = data_lookup[clean_key]["unit"]

        # --- TOP METRICS (USING YOUR DATA) ---
        st.subheader(f"📊 {device_mode} Global Specs for {selected_param}")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        m1.metric(f"Max {selected_param}", f"{data_lookup[clean_key]['max']} {unit}")
        m2.metric(f"Min {selected_param}", f"{data_lookup[clean_key]['min']} {unit}")
        m3.metric("Max Chamber Temp", f"{df[temp_col].max():.2f}°C")
        m4.metric("Min Chamber Temp", f"{df[temp_col].min():.2f}°C")
        m5.metric("Calculated PPM", f"{data_lookup[clean_key]['ppm']}")

        # --- RAW PARAMETER PLOT ---
        valid_df = df[[time_col, selected_param, temp_col]].dropna().copy()
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Primary Plot: The Raw Data (Not PPM)
        fig.add_trace(go.Scattergl(
            x=valid_df[time_col], 
            y=valid_df[selected_param],
            name=f"Raw {selected_param} ({unit})",
            line=dict(color="#00CCFF", width=2)
        ), secondary_y=False)

        # Secondary Plot: Chamber Temp
        fig.add_trace(go.Scattergl(
            x=valid_df[time_col], 
            y=valid_df[temp_col],
            name="Chamber Temp (°C)",
            line=dict(color="#FFD700", width=1.5, dash='dot')
        ), secondary_y=True)

        fig.update_layout(
            title=f"<b>Synchronized Raw Data: {selected_param} vs Temperature</b>",
            template="plotly_dark", height=600,
            xaxis=dict(title="Time Progress", rangeslider=dict(visible=True)),
            yaxis=dict(title=f"{selected_param} ({unit})"), 
            yaxis2=dict(title="Temp (°C)", side='right', range=[0, 100]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Missing columns. Ensure 'Chamber Temp' and Mtrol parameters exist.")
else:
    st.info("Please upload a Mtrol CSV file.")
