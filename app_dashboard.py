import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- SIDEBAR LOGO (Fixed for v1.55+ Width Rules) ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("Mtrol Analytics")

# --- SMART STANDARD LOOKUP ---
def get_mtrol_standards(device_name, parameter_name):
    """Matches uploaded column names to the reference standards CSV."""
    file_map = {
        "Mtrol 3": "Standard Values 11-13 March - For Mtrol 3 Input.csv",
        "Mtrol 4": "Standard Values 11-13 March - For Mtrol 4 Input.csv"
    }
    filename = file_map.get(device_name)
    
    if filename and os.path.exists(filename):
        try:
            std_df = pd.read_csv(filename)
            # Normalize names: 'P1 (bar)' -> 'p1'
            def clean(text): return re.sub(r'[^a-zA-Z0-9]', '', str(text)).lower()
            
            search_key = clean(parameter_name)
            for _, row in std_df.iterrows():
                std_param = clean(row['Parameters'])
                if std_param in search_key or search_key in std_param:
                    return float(row['Minimum Value']), float(row['Maximum Value'])
        except Exception:
            pass
    return None, None

# --- DATA CLEANING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    # Find Time Column
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    # Numeric cleanup: handles cases where numbers have symbols like '%' or units
    targets = ["flow", "opening", "p1", "p2", "temp", "chamber"]
    for col in df.columns:
        if col != time_col and any(t in col.lower() for t in targets):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    return df, time_col

# --- MAIN UI ---
st.title("Mtrol Full-Cycle Stability Dashboard")
st.caption("Standardized PPM Calculation Engine | High-Precision Analytics")

st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

# System Health Check
st.sidebar.markdown("---")
st.sidebar.subheader("Reference Files Status")
m3_exists = os.path.exists("Standard Values 11-13 March - For Mtrol 3 Input.csv")
m4_exists = os.path.exists("Standard Values 11-13 March - For Mtrol 4 Input.csv")
st.sidebar.write(f"{'✅' if m3_exists else '❌'} Mtrol 3 Standards")
st.sidebar.write(f"{'✅' if m4_exists else '❌'} Mtrol 4 Standards")

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    
    # Device Mode Detection
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode Detected: {device_name}")

    # Column identification
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    params = [c for c in df.columns if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if params and temp_col:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", params)
        std_min, std_max = get_mtrol_standards(device_name, plot_col)

        if std_min is not None and std_max is not None:
            # Stability Logic: PPM = (ΔInput * 1M) / (ΔTemp * ΔStd_Range)
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            
            # Using expanding window to capture cumulative drift
            in_range = valid_df[plot_col].expanding().max() - valid_df[plot_col].expanding().min()
            temp_range = valid_df[temp_col].expanding().max() - valid_df[temp_col].expanding().min()
            std_range = std_max - std_min
            
            # Prevent division by zero errors
            valid_df['PPM'] = (in_range * 1000000) / (temp_range * std_range)
            valid_df['PPM'] = valid_df['PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- PLOTTING (Fixed width settings) ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            fig.add_trace(go.Scattergl(
                x=valid_df[time_col], y=valid_df['PPM'], 
                name="Stability Index (PPM)", 
                line=dict(color="#00CCFF", width=2.5)
            ), secondary_y=False)

            fig.add_trace(go.Scattergl(
                x=valid_df[time_col], y=valid_df[temp_col], 
                name="Chamber Temp (°C)", 
                line=dict(color="#00FF99", width=1.5, dash='dot')
            ), secondary_y=True)

            fig.update_layout(
                template="plotly_dark", height=600,
                xaxis=dict(title="Time (Cycle Duration)", rangeslider=dict(visible=True, thickness=0.05)),
                yaxis=dict(title="Calculated PPM Stability"),
                yaxis2=dict(title="Temperature (°C)", side='right'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # --- METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Final Cycle PPM", f"{valid_df['PPM'].iloc[-1]:.2f}")
            col2.metric(f"Peak {plot_col}", f"{valid_df[plot_col].max():.4f}")
            col3.info(f"Ref Range: {std_min} - {std_max}")
            
        else:
            st.error(f"❌ Reference standards for '{plot_col}' not found.")
    else:
        st.error("❌ Required columns missing from dataset.")
else:
    st.info("👋 Welcome! Please upload a Mtrol dataset (CSV) to begin.")
