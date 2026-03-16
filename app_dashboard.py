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
    st.sidebar.image("logo.png", width=None) 
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
            # Helper to strip units/spaces: 'P1 (bar)' -> 'p1'
            def clean(text): return re.sub(r'[^a-zA-Z0-9]', '', str(text)).lower()
            
            search_key = clean(parameter_name)
            for _, row in std_df.iterrows():
                std_param = clean(row['Parameters'])
                # Check if one is contained in the other
                if std_param in search_key or search_key in std_param:
                    return float(row['Minimum Value']), float(row['Maximum Value'])
        except Exception:
            pass
    return None, None

# --- DATA CLEANING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    # Identify Time Column
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col).dropna(subset=[time_col])
    
    # Numeric cleanup (removes %, units, etc.)
    targets = ["flow", "opening", "p1", "p2", "temp", "chamber"]
    for col in df.columns:
        if col != time_col and any(t in col.lower() for t in targets):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    return df, time_col

# --- MAIN UI ---
st.title("Mtrol Full-Cycle Stability Dashboard")
st.caption("Automated PPM Stability Analysis | High-Precision Metrics")

st.sidebar.header("📂 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

# Health Check Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Reference Files Status")
m3_path = "Standard Values 11-13 March - For Mtrol 3 Input.csv"
m4_path = "Standard Values 11-13 March - For Mtrol 4 Input.csv"
st.sidebar.write(f"{'✅' if os.path.exists(m3_path) else '❌'} Mtrol 3 Standards")
st.sidebar.write(f"{'✅' if os.path.exists(m4_path) else '❌'} Mtrol 4 Standards")

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    
    # Auto-detect device type from filename
    device_name = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_name}")

    # Identify Temperature and Parameter columns
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    params = [c for c in df.columns if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if params and temp_col:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", params)
        std_min, std_max = get_mtrol_standards(device_name, plot_col)

        if std_min is not None and std_max is not None:
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            
            # Cumulative Range (Expanding Window) to filter jitter
            in_range = valid_df[plot_col].expanding().max() - valid_df[plot_col].expanding().min()
            temp_range = valid_df[temp_col].expanding().max() - valid_df[temp_col].expanding().min()
            std_total_range = std_max - std_min
            
            # PPM Stability Formula
            # Formula: (Input_Delta * 1,000,000) / (Temp_Delta * Std_Range)
            valid_df['PPM'] = (in_range * 1000000) / (temp_range * std_total_range)
            valid_df['PPM'] = valid_df['PPM'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- PLOTTING ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Primary: PPM Stability
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df['PPM'], 
                                     name="Stability (PPM)", line=dict(color="#00CCFF", width=2.5)), 
                          secondary_y=False)
            
            # Secondary: Temp
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], 
                                     name="Chamber Temp (°C)", line=dict(color="#00FF99", width=1, dash='dot')), 
                          secondary_y=True)

            fig.update_layout(template="plotly_dark", height=600, 
                            title=f"<b>Cycle Drift: {plot_col} vs Temp</b>",
                            xaxis=dict(title="Cycle Duration", rangeslider=dict(visible=True, thickness=0.05)),
                            yaxis=dict(title="Calculated PPM Stability"), 
                            yaxis2=dict(title="Temperature (°C)", side='right'))
            
            st.plotly_chart(fig, use_container_width=True)

            # Final Summary Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Final Cycle PPM", f"{valid_df['PPM'].iloc[-1]:.2f}")
            c2.metric("Temp Shift Δ", f"{valid_df[temp_col].max() - valid_df[temp_col].min():.2f}°C")
            c3.info(f"Ref Range: {std_min} to {std_max}")
        else:
            st.warning(f"Reference range for {plot_col} not found in standards file.")
    else:
        st.error("Dataset missing required 'Chamber Temp' or Mtrol parameters.")
