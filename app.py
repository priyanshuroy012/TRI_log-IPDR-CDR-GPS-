# app.py
import streamlit as st
import os
import json
import pandas as pd
from utils import normalize_columns, check_required, extract_gps_from_android_image,compute_file_hash
from train_model import train_anomaly_model, format_output_table,detect_spoofing_and_sim_swap
from streamlit_folium import st_folium
from map_utils import create_hybrid_movement_map_with_labels
import altair as alt

st.set_page_config(page_title="Android Forensics")

st.markdown("""
    <style>
        .block-container {padding: 2rem;}
        label, .stCheckbox > div {font-size: 16px;}
        h1, h2, h3, h4, h5, h6 {color: #003366;}
        .stRadio > div, .stSelectbox > div, .stSlider > div {font-size: 16px;}
    </style>
""", unsafe_allow_html=True)

st.title("\U0001F50D Android Forensics: GPS + IPDR + CDR Analyzer")

# Sidebar: Uploads and settings
st.sidebar.header("\U0001F4C2 Upload Forensic Logs")
use_logical_image = st.sidebar.checkbox("\U0001F4C1 Extract GPS from logical image folder", value=True)
gps_only = st.sidebar.checkbox("\U0001F4CD Analyze GPS only (skip IPDR/CDR)", value=True)
profile = st.sidebar.selectbox("\U0001F3AF Detection Profile", ["Conservative", "Balanced", "Aggressive"], index=1)

if profile == "Conservative":
    gps_threshold_default, max_gap_default, speed_threshold_default = 200, 1800, 800
elif profile == "Balanced":
    gps_threshold_default, max_gap_default, speed_threshold_default = 100, 900, 500
else:
    gps_threshold_default, max_gap_default, speed_threshold_default = 50, 600, 300

with st.sidebar.expander("\u2699\ufe0f Detection Parameters", expanded=False):
    gps_threshold_km = st.slider("\U0001F4CD GPS Distance Threshold (km)", 10, 500, value=gps_threshold_default, step=10)
    max_gap_secs = st.slider("\u23F1\ufe0f Max Time Gap Between Logs (seconds)", 60, 3600, value=max_gap_default, step=60)
    speed_threshold = st.slider("\U0001F697 High-Speed Movement Threshold (km/h)", 100, 1000, value=speed_threshold_default, step=50)

# Load Data
if use_logical_image:
    folder_path = st.sidebar.text_input("Enter folder path (e.g. extracted_logical_image/)", value="my_folder")
    gps_df = extract_gps_from_android_image(folder_path) if os.path.exists(folder_path) else pd.DataFrame()
    if gps_df.empty:
        st.sidebar.error("\u274C Folder not found or empty!")
    else:
        st.sidebar.success(f"\u2705 Loaded {len(gps_df)} GPS points from folder")
else:
    gps_file = st.sidebar.file_uploader("Upload GPS CSV", type="csv")
    gps_df = pd.read_csv(gps_file) if gps_file else pd.DataFrame()

ipdr_file = st.sidebar.file_uploader("Upload IPDR CSV (optional)", type="csv")
cdr_file = st.sidebar.file_uploader("Upload CDR CSV (optional)", type="csv")

file_hashes = []
if not use_logical_image :
    if gps_file:
        file_hashes.append(("GPS", gps_file.name, compute_file_hash(gps_file), gps_file.getbuffer().nbytes))
if ipdr_file:
    file_hashes.append(("IPDR", ipdr_file.name, compute_file_hash(ipdr_file), ipdr_file.getbuffer().nbytes))
if cdr_file:
    file_hashes.append(("CDR", cdr_file.name, compute_file_hash(cdr_file), cdr_file.getbuffer().nbytes))


# Proceed if data is ready
if not gps_df.empty and (gps_only or (ipdr_file and cdr_file)):
    gps_df = normalize_columns(gps_df, type="gps")
    ipdr_df = normalize_columns(pd.read_csv(ipdr_file), type="ipdr") if ipdr_file else pd.DataFrame()
    cdr_df = normalize_columns(pd.read_csv(cdr_file), type="cdr") if cdr_file else pd.DataFrame()

    check_required(gps_df, ["timestamp", "lat", "lon"], "GPS")
    check_required(ipdr_df, ["timestamp", "ip", "domain", "lat", "lon"], "IPDR")
    check_required(cdr_df, ["timestamp", "contact", "call_type", "lat", "lon"], "CDR")

    model, scaler, timeline_df, features_df, alerts = train_anomaly_model(gps_df, ipdr_df, cdr_df)
    st.toast("\u2705 Model trained and timeline generated!", icon="\U0001F680")

    # Filters
    anomaly_only = st.sidebar.checkbox("\U0001F6A8 Show anomalies only")
    long_jump_only = st.sidebar.checkbox("\U0001F4CD Long GPS jumps only")
    event_types = timeline_df['type'].dropna().unique().tolist()
    selected_types = st.sidebar.multiselect("\U0001F4CA Event Types", event_types, default=event_types)

    suspicious_domains = ["telegram", "onion", "vpn", "tor"]
    with st.sidebar.expander("\u2699\ufe0f Advanced Filters", expanded=False):
        suspicious_only = st.checkbox("\U0001F575\ufe0f Suspicious domains")
        start_time = st.time_input("\U0001F551 Start Time", value=pd.to_datetime("00:00").time())
        end_time = st.time_input("\U0001F551 End Time", value=pd.to_datetime("23:59").time())

    filtered_df = timeline_df.copy()
    if anomaly_only: filtered_df = filtered_df[filtered_df['anomaly'] == 1]
    if selected_types: filtered_df = filtered_df[filtered_df['type'].isin(selected_types)]
    if suspicious_only and 'domain' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['domain'].str.contains('|'.join(suspicious_domains), na=False, case=False)]
    if 'speed_kmph' in filtered_df.columns:
        filtered_df = filtered_df[pd.to_numeric(filtered_df['speed_kmph'], errors='coerce') > speed_threshold]
    if long_jump_only and 'notes' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['notes'].str.contains('jump', na=False)]
    filtered_df['hour'] = pd.to_datetime(filtered_df['timestamp']).dt.time
    filtered_df = filtered_df[(filtered_df['hour'] >= start_time) & (filtered_df['hour'] <= end_time)]

    # Investigation Summary
    st.markdown("---")
    st.markdown("## \U0001F9E0 Investigation Summary")
    summary = {
        "Total Events": len(filtered_df),
        "Anomalies Detected": filtered_df['anomaly'].sum(),
        "GPS Jumps": filtered_df['notes'].str.contains("jump", na=False).sum(),
        "SIM Swap Events": filtered_df['notes'].str.contains("swap", na=False).sum(),
        "Spoofing Detected": filtered_df['notes'].str.contains("spoof", na=False).sum(),
        "Correlation Score > 3": (filtered_df['correlation_score'] > 3).sum() if 'correlation_score' in filtered_df.columns else 0
    }
    st.table(pd.DataFrame(summary.items(), columns=["Metric", "Value"]))

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["\U0001F4CB Timeline", "\U0001F4CA Chart", "\U0001F4CD Map"])
    with tab1:
        st.dataframe(format_output_table(filtered_df).style.set_properties(**{"white-space": "pre-line"}))
    with tab2:
        counts = filtered_df[filtered_df['anomaly'] == 1]['type'].value_counts().reset_index()
        counts.columns = ['Event Type', 'Count']
        st.altair_chart(alt.Chart(counts).mark_bar().encode(x='Event Type', y='Count', color='Event Type'), use_container_width=True)
    with tab3:
        st.markdown("### \U0001F5FA\ufe0f Movement Map")
        st_folium(create_hybrid_movement_map_with_labels(filtered_df), width=800, height=550)

    with st.expander("\U0001F6A8 View Alert Messages", expanded=False):
        if alerts:
            for alert in alerts: st.warning(f"{alert[0]} ➜ {alert[1]}")
        else:
            st.info("\u2705 No alerts raised based on current filters.")

    st.markdown("---")
    st.header("\U0001F4C4 Forensic Report")
    st.subheader("\U0001F512 Uploaded File Hashes")
    if file_hashes:
        st.table(pd.DataFrame(file_hashes, columns=["Type", "Filename", "SHA256", "Size (bytes)"]))

    st.subheader("\u2699\ufe0f Parameters Used")
    st.json({
        "Profile": profile,
        "GPS Threshold (km)": gps_threshold_km,
        "Max Time Gap (s)": max_gap_secs,
        "Speed Threshold (km/h)": speed_threshold,
        "Anomaly Only": anomaly_only,
        "Jump Only": long_jump_only,
        "Suspicious Domains": suspicious_only,
        "Event Types": selected_types,
        "Time Window": f"{start_time} - {end_time}"
    })

    st.subheader("\U0001F4AC Notable Events")
    top_alerts = timeline_df[timeline_df['notes'].notna()].sort_values("timestamp").head(10)
    for _, row in top_alerts.iterrows():
        st.markdown(f"- **{row['timestamp']}** — {row['notes']}")

    report = {
        "file_hashes": [
            {"type": t, "filename": fn, "sha256": sha, "size": sz} for t, fn, sha, sz in file_hashes
        ],
        "parameters": {
            "profile": profile,
            "gps_threshold_km": gps_threshold_km,
            "max_gap_secs": max_gap_secs,
            "speed_threshold_kmph": speed_threshold,
            "anomaly_only": anomaly_only,
            "long_jump_only": long_jump_only,
            "suspicious_only": suspicious_only,
            "event_types": selected_types,
            "time_window": f"{start_time} - {end_time}"
        },
        "findings": summary,
        "alerts": top_alerts[["timestamp", "notes"]].to_dict(orient="records")
    }
    st.download_button(
    "⬇️ Download Report as JSON",
    json.dumps(report, indent=2, default=str),
    file_name="forensic_report.json"
)


else:
    st.warning("\u26A0\uFE0F Please upload at least the GPS data. IPDR and CDR required unless GPS-only mode is selected.")




