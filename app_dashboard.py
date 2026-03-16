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

# --- UPDATED CONSTANTS ---
TEMP_DELTA_FIXED = 89.85  # Calculated as 69.675 - (-20.175)

def get_mtrol_standards(parameter_name):
    """Returns (min, max) based on your latest input ranges."""
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(parameter_name)).lower()
    
    if "opening" in clean_name:
        return 0.0, 100.0
    elif "p1" in clean_name:
        return 0.0, 17.0
    elif "p2" in clean_name:
        return 0.0, 17.0
    # Add Flow Rate logic here later if needed
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
st.caption(f"PPM Formula using Fixed Temp Δ: {TEMP_DELTA_FIXED}°C")

st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    params = [c for c in df.columns if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if params and temp_col:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", params)
        std_min, std_max = get_mtrol_standards(plot_col)

        if std_min is not None and std_max is not None:
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            
            # --- UPDATED PPM CALCULATION ---
            # Input Range (Delta Input) calculated cumulatively
            in_range = valid_df[plot_col].expanding().max() - valid_df[plot_col].expanding().min()
            std_range = std_max - std_min
            
            # Use the FIXED Temp Delta provided by user
            valid_df['PPM'] = (in_range * 1000000) / (TEMP_DELTA_FIXED * std_range)
            valid_df['PPM'] = valid_df['PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- PLOTTING ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df['PPM'], name="Stability (PPM)", line=dict(color="#00CCFF", width=2.5)), secondary_y=False)
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], name="Chamber Temp (°C)", line=dict(color="#00FF99", width=1.5, dash='dot')), secondary_y=True)

            fig.update_layout(template="plotly_dark", height=600, 
                            title=f"<b>{plot_col} Stability Analysis</b>",
                            xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
                            yaxis=dict(title="Calculated PPM"), yaxis2=dict(title="Temp (°C)", side='right'))
            
            st.plotly_chart(fig, use_container_width=True)

            # Results Summary
            col1, col2, col3 = st.columns(3)
            col1.metric("Final Cycle PPM", f"{valid_df['PPM'].iloc[-1]:.2f}")
            col2.metric("Total Drift (Units)", f"{in_range.iloc[-1]:.4f}")
            col3.info(f"Fixed Temp Range: {TEMP_DELTA_FIXED}°C")
        else:
            st.warning(f"Standard range for {plot_col} not defined. Cannot calculate PPM.")
    else:
        st.error("Missing required columns: Chamber Temperature or Mtrol Parameters.")
else:
    st.info("Please upload a CSV file to begin.")
