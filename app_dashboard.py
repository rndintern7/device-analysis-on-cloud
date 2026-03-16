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
# Per your requirement: Fixed Temperature Delta for the whole chamber cycle
TEMP_DELTA_FIXED = 89.85  

def get_mtrol_standards(device_name, parameter_name):
    """Assigns the Reference Range (Denominator) based on Mtrol 3/4 specs."""
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(parameter_name)).lower()
    
    # Mtrol 4 (Scale from your images)
    if "4" in device_name:
        if "flow" in clean_name: return 0.0, 500.0
        if "opening" in clean_name: return 0.0, 100.0
        if "p1" in clean_name or "p2" in clean_name: return 0.0, 17.0
    # Mtrol 3 (Scale from your images)
    else:
        if "flow" in clean_name: return 0.0, 200.0
        if "opening" in clean_name: return 0.0, 100.0
        if "p1" in clean_name or "p2" in clean_name: return 0.0, 17.0
    return None, None

# --- DATA LOADING ---
@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    time_col = next((c for c in df.columns if "time" in c.lower()), None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.sort_values(by=time_col)
    
    targets = ["flow", "opening", "p1", "p2", "temp", "chamber"]
    for col in df.columns:
        if col != time_col and any(t in col.lower() for t in targets):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    return df, time_col

# --- MAIN UI ---
st.title("Mtrol Full-Cycle Stability Dashboard")
st.markdown(r"**PPM Formula:** $\frac{(Max_{raw} - Min_{raw}) \times 1,000,000}{89.85 \times (Ref Range)}$")

uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    device_mode = "Mtrol 4" if "MT4" in uploaded_file.name.upper() else "Mtrol 3"
    st.sidebar.success(f"Mode Detected: {device_mode}")

    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    available_params = [c for c in df.columns if any(t in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if available_params and temp_col:
        selected_param = st.sidebar.selectbox("🎯 Select Parameter", available_params)
        std_min, std_max = get_mtrol_standards(device_mode, selected_param)
        ref_range = std_max - std_min

        if ref_range:
            # Keep all data to ensure complete cycle coverage
            valid_df = df[[time_col, selected_param, temp_col]].copy()
            valid_df = valid_df.fillna(method='ffill').fillna(method='bfill')

            # --- DYNAMIC DRIFT CALCULATION ---
            # Drift is the expanding range of the raw selected parameter
            current_max = valid_df[selected_param].expanding().max()
            current_min = valid_df[selected_param].expanding().min()
            drift_delta = current_max - current_min
            
            # --- FINAL PPM FORMULA ---
            valid_df['PPM_Stability'] = (drift_delta * 1000000) / (TEMP_DELTA_FIXED * ref_range)

            # --- GRAPHING ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Stability Line
            fig.add_trace(go.Scattergl(
                x=valid_df[time_col], y=valid_df['PPM_Stability'],
                name=f"{selected_param} PPM",
                line=dict(color="#00CCFF", width=2)
            ), secondary_y=False)

            # Chamber Temp Line
            fig.add_trace(go.Scattergl(
                x=valid_df[time_col], y=valid_df[temp_col],
                name="Chamber Temp (°C)",
                line=dict(color="#FFD700", width=1.5, dash='dot')
            ), secondary_y=True)

            fig.update_layout(
                title=f"<b>Complete Cycle Stability: {selected_param}</b>",
                template="plotly_dark", height=600,
                xaxis=dict(title="Time Progress", rangeslider=dict(visible=True)),
                yaxis=dict(title="Calculated PPM", range=[0, 100]), 
                yaxis2=dict(title="Temp (°C)", side='right', range=[0, 100]),
                legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- STATISTICS TABLE ---
            st.subheader("📋 Peak / Min / Average Summary")
            
            final_ppm = valid_df['PPM_Stability'].iloc[-1]
            peak_ppm = valid_df['PPM_Stability'].max()
            avg_ppm = valid_df['PPM_Stability'].mean()
            min_ppm = valid_df['PPM_Stability'].min()

            stats_data = {
                "Metric": ["Final Cycle PPM", "Peak PPM Encountered", "Average PPM", "Minimum PPM"],
                "Value": [f"{final_ppm:.4f}", f"{peak_ppm:.4f}", f"{avg_ppm:.4f}", f"{min_ppm:.4f}"]
            }
            st.table(pd.DataFrame(stats_data))

            with st.expander("🔍 Detailed Data Table"):
                st.dataframe(valid_df, use_container_width=True)
        else:
            st.warning("Could not find Reference Range.")
    else:
        st.error("Missing required columns (Temp/Params).")
else:
    st.info("Upload your Mtrol CSV to generate the stability report.")
