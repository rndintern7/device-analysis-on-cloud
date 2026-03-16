import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- SIDEBAR LOGO ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("Mtrol Analytics")

# --- CONSTANTS ---
TEMP_DELTA_FIXED = 89.85  

def get_mtrol_standards(device_name, parameter_name):
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(parameter_name)).lower()
    if "4" in device_name:
        if "flow" in clean_name: return 0.0, 500.0
        if "opening" in clean_name: return 0.0, 100.0
        if "p1" in clean_name or "p2" in clean_name: return 0.0, 17.0
    else:
        if "flow" in clean_name: return 0.0, 200.0
        if "opening" in clean_name: return 0.0, 100.0
        if "p1" in clean_name or "p2" in clean_name: return 0.0, 17.0
    return None, None

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
st.sidebar.header("Analysis Settings")
smooth_data = st.sidebar.toggle("Enable Signal Smoothing", value=True)
window_size = st.sidebar.slider("Smoothing Window", 5, 100, 20) if smooth_data else 1

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    device_mode = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_mode}")

    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    available_params = [c for c in df.columns if any(t in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if available_params and temp_col:
        selected_param = st.sidebar.selectbox("🎯 Select Parameter to Analyze", available_params)
        std_min, std_max = get_mtrol_standards(device_mode, selected_param)
        ref_range = std_max - std_min

        if ref_range:
            valid_df = df[[time_col, selected_param, temp_col]].dropna().copy()
            
            # --- CALCULATIONS ---
            raw_series = valid_df[selected_param]
            clean_series = raw_series.rolling(window=window_size, center=True).mean() if smooth_data else raw_series
            
            current_max = clean_series.expanding().max()
            current_min = clean_series.expanding().min()
            drift_delta = current_max - current_min
            
            valid_df['PPM_Stability'] = (drift_delta * 1000000) / (TEMP_DELTA_FIXED * ref_range)
            valid_df['PPM_Stability'] = valid_df['PPM_Stability'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- THE FULL CYCLE GRAPH ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(go.Scattergl(
                x=valid_df[time_col], y=valid_df['PPM_Stability'],
                name=f"{selected_param} Stability (PPM)",
                line=dict(color="#00CCFF", width=2.5)
            ), secondary_y=False)

            fig.add_trace(go.Scattergl(
                x=valid_df[time_col], y=valid_df[temp_col],
                name="Chamber Temp (°C)",
                line=dict(color="#FFD700", width=1.5, dash='dot')
            ), secondary_y=True)

            # --- UPDATED AXIS RANGES (Both set to 100) ---
            fig.update_layout(
                title=f"<b>Full-Cycle Stability: {selected_param}</b>",
                template="plotly_dark", height=600,
                xaxis=dict(title="Time", rangeslider=dict(visible=True, thickness=0.05)),
                # Locked PPM Axis
                yaxis=dict(title="Calculated PPM (Stability)", range=[0, 100]), 
                # Locked Temperature Axis
                yaxis2=dict(title="Chamber Temp (°C)", side='right', range=[0, 100]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- METRICS & MATH ---
            st.subheader(f"📊 {selected_param} Statistics")
            col1, col2, col3 = st.columns(3)
            col1.metric("Final PPM", f"{valid_df['PPM_Stability'].iloc[-1]:.2f}")
            col2.metric("Max Drift", f"{drift_delta.max():.4f}")
            col3.info(f"Y-Axes locked to 100 for standardization.")

        else:
            st.warning("Reference range missing.")
    else:
        st.error("Data columns missing.")
else:
    st.info("Upload a CSV file to begin.")
