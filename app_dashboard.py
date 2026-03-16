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
TEMP_DELTA_FIXED = 89.85  # Range: -20.175 to 69.675

def get_mtrol_standards(device_name, parameter_name):
    """Returns (min, max) based on Mtrol 3/4 specific specs."""
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(parameter_name)).lower()
    
    # Mtrol 4 Standards
    if "4" in device_name:
        if "flow" in clean_name: return 0.0, 500.0
        if "opening" in clean_name: return 0.0, 100.0
        if "p1" in clean_name or "p2" in clean_name: return 0.0, 17.0
    # Mtrol 3 Standards
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
            # Clean numeric data (removes units/symbols)
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    return df, time_col

# --- MAIN UI ---
st.title("Mtrol Full-Cycle Stability Dashboard")
# Fixed Line 55: Added 'r' before string to handle LaTeX \Delta properly
st.markdown(r"**Standardized Formula:** $PPM = \frac{(\Delta Input) \times 1,000,000}{89.85 \times (Ref Range)}$")

uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    
    # Auto-detect device mode
    device_mode = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode: {device_mode}")

    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    params = [c for c in df.columns if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if params and temp_col:
        plot_col = st.sidebar.selectbox("Select Parameter to Analyze", params)
        std_min, std_max = get_mtrol_standards(device_mode, plot_col)

        if std_min is not None and std_max is not None:
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            
            # --- CALCULATIONS ---
            # Drift = Running Max - Running Min of your uploaded data
            current_max = valid_df[plot_col].expanding().max()
            current_min = valid_df[plot_col].expanding().min()
            drift_delta = current_max - current_min
            
            ref_range = std_max - std_min
            
            # PPM Calculation
            valid_df['PPM_Stability'] = (drift_delta * 1000000) / (TEMP_DELTA_FIXED * ref_range)
            valid_df['PPM_Stability'] = valid_df['PPM_Stability'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- SUMMARY METRICS ---
            st.subheader("📊 Stability Statistics")
            final_drift = drift_delta.iloc[-1]
            final_ppm = valid_df['PPM_Stability'].iloc[-1]
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Final PPM Score", f"{final_ppm:.2f}")
            m2.metric("Total Drift (Units)", f"{final_drift:.4f}")
            m3.metric("Peak Value Found", f"{current_max.iloc[-1]:.3f}")
            m4.metric("Min Value Found", f"{current_min.iloc[-1]:.3f}")

            # --- PLOTTING ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df['PPM_Stability'], name="Stability (PPM)", line=dict(color="#00CCFF", width=2.5)), secondary_y=False)
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], name="Chamber Temp", line=dict(color="#FFD700", width=1, dash='dot')), secondary_y=True)
            
            fig.update_layout(template="plotly_dark", height=500, xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
                            yaxis=dict(title="Calculated PPM"), yaxis2=dict(title="Temp (°C)", side='right'))
            st.plotly_chart(fig, use_container_width=True)

            # --- MATH BREAKDOWN BOX ---
            with st.expander("🔍 Click to see the Calculation Breakdown"):
                st.write(f"**Step 1:** Drift = ({current_max.iloc[-1]} - {current_min.iloc[-1]}) = **{final_drift:.4f}**")
                st.write(f"**Step 2:** Ref Scale ({plot_col}) = **{ref_range}**")
                st.write(f"**Step 3:** Fixed Temp Delta = **89.85**")
                st.latex(rf"PPM = \frac{{{final_drift:.4f} \times 1,000,000}}{{89.85 \times {ref_range}}} = {final_ppm:.2f}")

            # --- DATA TABLE ---
            st.subheader("📋 Detailed PPM Log")
            st.dataframe(valid_df.tail(100), use_container_width=True)
            
        else:
            st.warning(f"Standard range for {plot_col} not defined.")
    else:
        st.error("CSV must contain 'Chamber Temp' and Mtrol parameters.")
else:
    st.info("👋 Ready to analyze. Please upload a Mtrol CSV file.")
