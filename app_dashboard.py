import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# 1. Page Config
st.set_page_config(page_title="Mtrol Precision Analytics", layout="wide")

# --- DATA CONSTANTS ---
MT3_VALS = {
    "flow": {"max": 303.54, "min": 0.00, "ppm": None, "unit": "Kg/Hr"},
    "opening": {"max": 22.01, "min": 0.00, "ppm": 2449.99, "unit": "%"},
    "p1": {"max": 10.60, "min": 0.00, "ppm": 21455.76, "unit": "bar"},
    "p2": {"max": 10.06, "min": 0.00, "ppm": 20355.54, "unit": "bar"}
}

MT4_VALS = {
    "flow": {"max": 275.11, "min": 0.00, "ppm": None, "unit": "Kg/Hr"},
    "opening": {"max": 19.50, "min": 0.00, "ppm": 2170.41, "unit": "%"},
    "p1": {"max": 5.37, "min": 5.31, "ppm": 129.91, "unit": "bar"},
    "p2": {"max": 10.74, "min": 10.59, "ppm": 310.21, "unit": "bar"}
}

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

        # --- DYNAMIC Y-AXIS RANGE ---
        param_lower = selected_param.lower()
        if "flow" in param_lower:
            left_range, left_dtick = [0, 320], 40
        elif "p1" in param_lower or "p2" in param_lower:
            left_range, left_dtick = [0, 20], 2
        else:
            left_range, left_dtick = [-20, 70], 10

        # --- GRAPH ---
        valid_df = df[[time_col, selected_param, temp_col]].dropna().copy()
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[selected_param], name=f"{selected_param}", line=dict(color="#00CCFF")), secondary_y=False)
        fig.add_trace(go.Scattergl(x=valid_df[time_col], y=valid_df[temp_col], name="Chamber Temp", line=dict(color="#FFD700", dash='dot')), secondary_y=True)

        fig.update_layout(
            template="plotly_dark", height=600,
            hovermode="x unified",
            dragmode="zoom", # Enables the "Box Zoom" cursor
            xaxis=dict(title="Time Progress", rangeslider=dict(visible=True)),
            # CRITICAL: fixedrange=False allows vertical zooming
            yaxis=dict(
                title=f"<b>{selected_param} ({unit})</b>", 
                color="#00CCFF", 
                range=left_range, 
                dtick=left_dtick,
                fixedrange=False 
            ),
            yaxis2=dict(
                title="<b>Chamber Temperature (°C)</b>", 
                color="#FFD700", 
                range=[-20, 70], 
                fixedrange=False 
            ),
        )

        # Enabling the Zoom tool specifically in the toolbar
        st.plotly_chart(fig, use_container_width=True, config={
            'scrollZoom': True,           # Zoom with mouse wheel
            'displayModeBar': True,       # Shows the zoom/pan/reset toolbar
            'modeBarButtonsToRemove': [], # Keep all tools
            'displaylogo': False
        })

        st.subheader("📁 Raw Dataset Explorer")
        st.dataframe(df, use_container_width=True)
else:
    st.info("Upload CSV to begin.")
