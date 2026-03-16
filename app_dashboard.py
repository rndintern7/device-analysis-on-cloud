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
TEMP_DELTA_FIXED = 89.85  # 69.675 - (-20.175)

def get_mtrol_standards(parameter_name):
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(parameter_name)).lower()
    if "opening" in clean_name:
        return 0.0, 100.0
    elif "p1" in clean_name:
        return 0.0, 17.0
    elif "p2" in clean_name:
        return 0.0, 17.0
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
st.caption(f"Standardized PPM Engine | Fixed Temp Δ: {TEMP_DELTA_FIXED}°C")

uploaded_file = st.sidebar.file_uploader("Upload Mtrol Dataset (CSV)", type=["csv"])

if uploaded_file is not None:
    df, time_col = load_and_clean_data(uploaded_file)
    temp_col = next((c for c in df.columns if "chamber" in c.lower() and "temp" in c.lower()), None)
    params = [c for c in df.columns if any(t.lower() in c.lower() for t in ["flow", "opening", "p1", "p2"])]

    if params and temp_col:
        plot_col = st.sidebar.selectbox("Select Parameter", params)
        std_min, std_max = get_mtrol_standards(plot_col)

        if std_min is not None and std_max is not None:
            # --- CALCULATIONS ---
            valid_df = df[[time_col, plot_col, temp_col]].dropna().copy()
            in_range = valid_df[plot_col].expanding().max() - valid_df[plot_col].expanding().min()
            std_range = std_max - std_min
            
            valid_df['PPM_Stability'] = (in_range * 1000000) / (TEMP_DELTA_FIXED * std_range)
            valid_df['PPM_Stability'] = valid_df['PPM_Stability'].replace([float('inf'), -float('inf')], 0).fillna(0)

            # --- METRICS SECTION ---
            st.subheader(f"📊 {plot_col} PPM Statistics")
            m1, m2, m3, m4 = st.columns(4)
            
            peak_ppm = valid_df['PPM_Stability'].max()
            avg_ppm = valid_df['PPM_Stability'].mean()
            min_ppm = valid_df[valid_df['PPM_Stability'] > 0]['PPM_Stability'].min() if not valid_df[valid_df['PPM_Stability'] > 0].empty else 0
            final_ppm = valid_df['PPM_Stability'].iloc[-1]

            m1.metric("Final PPM (Cycle End)", f"{final_ppm:.2f}")
            m2.metric("Peak PPM (Worst Case)", f"{peak_ppm:.2f}")
            m3.metric("Average PPM", f"{avg_ppm:.2f}")
            m4.metric("Minimum PPM", f"{min_ppm:.2f}")

            # --- PLOTTING ---
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df['PPM_Stability'], name="PPM", line=dict(color="#00CCFF", width=2)), secondary_y=False)
            fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], name="Temp (°C)", line=dict(color="#00FF99", width=1, dash='dot')), secondary_y=True)
            
            fig.update_layout(template="plotly_dark", height=500, xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
                            yaxis=dict(title="PPM"), yaxis2=dict(title="Temp (°C)", side='right'))
            st.plotly_chart(fig, use_container_width=True)

            # --- DATA TABLE SECTION ---
            st.divider()
            st.subheader("📋 PPM Calculation Detail Table")
            
            # Format the table for the user
            report_df = valid_df.copy()
            report_df['PPM_Stability'] = report_df['PPM_Stability'].map('{:,.2f}'.format)
            report_df[plot_col] = report_df[plot_col].map('{:.4f}'.format)
            report_df[temp_col] = report_df[temp_col].map('{:.2f}'.format)
            
            # Add progress percentage for easy tracking
            total_rows = len(report_df)
            report_df.insert(0, "Cycle Progress", [f"{(i/total_rows)*100:.1f}%" for i in range(1, total_rows + 1)])

            st.dataframe(report_df, use_container_width=True, hide_index=True)
            
            # Download Option
            csv = report_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download PPM Analysis as CSV", data=csv, file_name=f"Mtrol_PPM_{plot_col}.csv", mime='text/csv')

        else:
            st.warning(f"No standards defined for {plot_col}.")
    else:
        st.error("Required columns (Temp/Params) not detected.")
else:
    st.info("Please upload a dataset to generate the PPM report.")
