import streamlit as st
import os
import pandas as pd
import altair as alt
import json
from utils import (normalize_columns, check_required, extract_gps_from_android_image,convert_for_json,display_forensic_report,compute_file_hash)
from train_model_dual import (train_anomaly_model, format_output_table, detect_spoofing_and_sim_swap)
from streamlit_folium import st_folium
from map_utils import create_hybrid_movement_map_with_labels,display_timeline_with_playback

st.set_page_config(page_title="Android Forensics")

st.markdown("""
    <style>
        .block-container {padding: 2rem;}
        label, .stCheckbox > div {font-size: 16px;}
        h1, h2, h3, h4, h5, h6 {color: #003366;}
        .stRadio > div, .stSelectbox > div, .stSlider > div {font-size: 16px;}
    </style>
""", unsafe_allow_html=True)

st.title("🔍 Android Forensics: GPS + IPDR + CDR Analyzer")

st.sidebar.header("📂 Upload Forensic Logs")
st.sidebar.markdown("---")

use_logical_image = st.sidebar.checkbox("📁 Extract GPS from logical image folder", value=True)
gps_only = st.sidebar.checkbox("📍 Analyze GPS only (skip IPDR/CDR)", value=True)

profile = st.sidebar.selectbox("🎯 Detection Profile", ["Conservative", "Balanced", "Aggressive"], index=1)

profile_params = {
    "Conservative": (200, 1800, 800),
    "Balanced": (100, 900, 500),
    "Aggressive": (50, 600, 300)
}
gps_threshold_default, max_gap_default, speed_threshold_default = profile_params[profile]

with st.sidebar.expander("⚙️ Detection Parameters", expanded=False):
    gps_threshold_km = st.slider("📍 GPS Distance Threshold (km)", 10, 500, value=gps_threshold_default, step=10)
    max_gap_secs = st.slider("⏱️ Max Time Gap Between Logs (seconds)", 60, 3600, value=max_gap_default, step=60)
    speed_threshold_tuning = st.slider("🚗 High-Speed Movement Threshold (km/h)", 100, 1000, value=speed_threshold_default, step=50)

model_choice = st.sidebar.selectbox("🧠 Anomaly Detection Model", ["Isolation Forest", "Autoencoder"])
model_type = "autoencoder" if model_choice == "Autoencoder" else "isolation_forest"

if model_type == "autoencoder":
    with st.sidebar.expander("⚙️ Autoencoder Tuning", expanded=False):
        encoding_dim = st.slider("Encoding Dim", 2, 16, value=8)
        epochs = st.slider("Training Epochs", 10, 100, value=50, step=10)
        threshold_q = st.slider("Anomaly Threshold (percentile)", 80, 99, value=95)
else:
    encoding_dim, epochs, threshold_q = None, None, None

if use_logical_image:
    folder_path = st.sidebar.text_input("Enter folder path (e.g. extracted_logical_image/)", value="my_folder")
    if os.path.exists(folder_path):
        gps_df = extract_gps_from_android_image(folder_path)
        st.sidebar.success(f"✅ Loaded {len(gps_df)} GPS points from folder")
    else:
        st.sidebar.error("❌ Folder not found!")
        gps_df = pd.DataFrame()
else:
    gps_file = st.sidebar.file_uploader("Upload GPS CSV", type="csv")
    gps_df = pd.read_csv(gps_file) if gps_file else pd.DataFrame()

ipdr_file = st.sidebar.file_uploader("Upload IPDR CSV (optional)", type="csv")
cdr_file = st.sidebar.file_uploader("Upload CDR CSV (optional)", type="csv")

if not gps_df.empty and (gps_only or (ipdr_file and cdr_file)):
    raw_gps_df = gps_df.copy()
    raw_ipdr_df = pd.read_csv(ipdr_file) if ipdr_file else pd.DataFrame()
    raw_cdr_df = pd.read_csv(cdr_file) if cdr_file else pd.DataFrame()

    gps_df = normalize_columns(raw_gps_df, type="gps")
    ipdr_df = normalize_columns(raw_ipdr_df, type="ipdr") if not raw_ipdr_df.empty else raw_ipdr_df
    cdr_df = normalize_columns(raw_cdr_df, type="cdr") if not raw_cdr_df.empty else raw_cdr_df

    check_required(gps_df, ["timestamp", "lat", "lon"], "GPS")
    check_required(ipdr_df, ["timestamp", "ip", "domain", "lat", "lon"], "IPDR")
    check_required(cdr_df, ["timestamp", "contact", "call_type", "lat", "lon"], "CDR")
    file_hashes = []
    if not use_logical_image :
        if gps_file:
            file_hashes.append(("GPS", gps_file.name, compute_file_hash(gps_file), gps_file.getbuffer().nbytes))
    if ipdr_file:
        file_hashes.append(("IPDR", ipdr_file.name, compute_file_hash(ipdr_file), ipdr_file.getbuffer().nbytes))
    if cdr_file:
        file_hashes.append(("CDR", cdr_file.name, compute_file_hash(cdr_file), cdr_file.getbuffer().nbytes))

    model, scaler, timeline_df, features_df, alerts = train_anomaly_model(
        gps_df, ipdr_df, cdr_df,
        gps_threshold_km=gps_threshold_km,
        max_gap_secs=max_gap_secs,
        speed_threshold=speed_threshold_tuning,
        model_type=model_type
    )
    st.toast("✅ Model trained and timeline generated!", icon="🚀")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎛️ Filter Controls")

    anomaly_only = st.sidebar.checkbox("🚨 Show anomalies only")
    long_jump_only = st.sidebar.checkbox("📍 Long GPS jumps only")

    event_types = timeline_df['type'].dropna().unique().tolist()
    selected_types = st.sidebar.multiselect("📊 Event Types", event_types, default=event_types)

    with st.sidebar.expander("⚙️ Advanced Filters", expanded=False):
        suspicious_only = st.checkbox("🕵️ Suspicious domains")
        start_time = st.time_input("🕐 Start Time", value=pd.to_datetime("00:00").time())
        end_time = st.time_input("🕐 End Time", value=pd.to_datetime("23:59").time())

    filtered_df = timeline_df.copy()
    if anomaly_only:
        filtered_df = filtered_df[filtered_df['anomaly'] == 1]
    if selected_types:
        filtered_df = filtered_df[filtered_df['type'].isin(selected_types)]
    if suspicious_only and 'domain' in filtered_df.columns:
        suspicious_domains = ["telegram", "onion", "vpn", "tor"]
        filtered_df = filtered_df[filtered_df['domain'].str.contains('|'.join(suspicious_domains), na=False, case=False)]
    if 'speed_kmph' in filtered_df.columns:
        filtered_df = filtered_df[pd.to_numeric(filtered_df['speed_kmph'], errors='coerce') > speed_threshold_tuning]
    if long_jump_only and 'notes' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['notes'].str.contains('jump', na=False)]
    filtered_df['hour'] = pd.to_datetime(filtered_df['timestamp']).dt.time
    filtered_df = filtered_df[(filtered_df['hour'] >= start_time) & (filtered_df['hour'] <= end_time)]




    st.markdown("---")
    st.markdown("## 🧠 Investigation Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔢 Total Events", len(filtered_df))
    col2.metric("🚨 Anomalies Detected", filtered_df['anomaly'].sum())
    col3.metric("📍 GPS Jumps", filtered_df['notes'].str.contains("jump", na=False).sum())
    col4.metric("🕵️ SIM Spoof Cases", filtered_df['notes'].str.contains("spoof", na=False).sum())

# Investigation Summary
    st.markdown("---")
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
    with st.expander("📢 View Alert Messages", expanded=False):
        if alerts:
            for alert in alerts:
                st.warning(f"{alert[0]} ➜ {alert[1]}")
        else:
            st.info("✅ No alerts raised based on current filters.")





    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📋 Timeline", "📊 Chart", "📍 Map"])

    with tab1:
        output_df = format_output_table(filtered_df)
        st.dataframe(output_df.style.set_properties(**{"white-space": "pre-line"}))

    with tab2:
        anomaly_counts = filtered_df[filtered_df['anomaly'] == 1]['type'].value_counts().reset_index()
        anomaly_counts.columns = ['Event Type', 'Count']
        bar_chart = alt.Chart(anomaly_counts).mark_bar().encode(
            x='Event Type', y='Count', color='Event Type')
        st.altair_chart(bar_chart, use_container_width=True)

    with tab3:
        st.markdown("### 🗺️ Movement Map")
        labeled_map = create_hybrid_movement_map_with_labels(filtered_df)
        st_folium(labeled_map, width=800, height=550)
        if st.button("🎥 Animate Movement"):
            display_timeline_with_playback(filtered_df)


        with st.popover("ℹ️ Legend"):
            st.markdown("""
             - 🔵 Normal path  
             - 🔴 Unrealistic jump  
             - 🚨 Speed/distance anomaly  
             - 🟠 Spoofed activity  
             - 🟣 Suspicious domain  
             - 🛑 Multiple overlapping anomalies 
            """)


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
        "Speed Threshold (km/h)": speed_threshold_tuning ,
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
            "speed_threshold_kmph": speed_threshold_tuning ,
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
from utils import generate_forensic_pdf_report

if st.button("📝 Generate PDF Report"):
    pdf_path = generate_forensic_pdf_report({
        "model_used": model_choice,
        "parameters": report["parameters"],
        "summary": filtered_df,
        "alerts": report["alerts"]
    })
    with open(pdf_path, "rb") as f:
        st.download_button("⬇️ Download PDF Report", data=f, file_name="forensic_report.pdf", mime="application/pdf")
  
        
else:
    st.warning("⚠️ Please upload at least the GPS data. IPDR and CDR required unless GPS-only mode is selected.")


