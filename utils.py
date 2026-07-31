
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
import streamlit as st
import os
import sqlite3
import json
import xml.etree.ElementTree as ET
import pandas as pd
import folium
import pandas as pd
from folium.plugins import TimestampedGeoJson
import streamlit as st
from datetime import timedelta



def parse_timestamp(ts):
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.strptime(ts, "%Y/%m/%d %H:%M:%S")


def haversine(lat1, lon1, lat2, lon2):
    # Earth radius in km
    R = 6371.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # in kilometers


def time_diff_seconds(t1, t2):
    return abs((t1 - t2).total_seconds())

# normalizer.py

import pandas as pd

def normalize_columns(df, type="generic"):
    """
    Generic column normalization dispatcher for GPS, CDR, IPDR.
    """
    if type == "ipdr":
        return normalize_ipdr(df)
    elif type == "cdr":
        return normalize_cdr(df)
    elif type == "gps":
        return normalize_gps(df)
    else:
        return df


def normalize_ipdr(df):
    column_map = {
        "source_ip": "ip",
        "src_ip": "ip",
        "destination_ip": "ip",
        "domain_name": "domain",
        "hostname": "domain",
        "host": "domain",
        "datetime": "timestamp",
        "time": "timestamp",
        "lat": "lat",
        "latitude": "lat",
        "lon": "lon",
        "longitude": "lon"
    }
    df = _rename_and_patch(df, column_map, required=["timestamp", "ip", "domain", "lat", "lon"])
    return df


def normalize_cdr(df):
    column_map = {
        "callee": "contact",
        "called_party": "contact",
        "caller": "contact",
        "call_type": "call_type",
        "datetime": "timestamp",
        "time": "timestamp",
        "lat": "lat",
        "latitude": "lat",
        "lon": "lon",
        "longitude": "lon"
    }
    df = _rename_and_patch(df, column_map, required=["timestamp", "contact", "call_type", "lat", "lon"])
    return df


def normalize_gps(df):
    column_map = {
        "datetime": "timestamp",
        "time": "timestamp",
        "lat": "lat",
        "latitude": "lat",
        "lon": "lon",
        "longitude": "lon"
    }
    df = _rename_and_patch(df, column_map, required=["timestamp", "lat", "lon"])
    return df


def _rename_and_patch(df, column_map, required):
    # Rename known variants to standard names
    df = df.rename(columns={col: column_map.get(col.lower(), col) for col in df.columns})

    # Ensure all required columns exist
    for col in required:
        if col not in df.columns:
            df[col] = None

    # Parse timestamp column
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df


def check_required(df, cols, label):
    missing = [col for col in cols if col not in df.columns or df[col].isnull().all()]
    if missing:
        st.warning(f"⚠️ Missing in {label}: {', '.join(missing)}")


def extract_gps_from_android_image(image_dir):
    gps_entries = []

    # SQLite DBs
    for root, _, files in os.walk(image_dir):
        for file in files:
            if file.lower() in ["location.db", "networklocation.db"]:
                try:
                    conn = sqlite3.connect(os.path.join(root, file))
                    cursor = conn.cursor()
                    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                    for table in tables:
                        try:
                            rows = cursor.execute(f"SELECT * FROM {table}").fetchall()
                            cols = [desc[0] for desc in cursor.description]
                            if {'latitude', 'longitude', 'timestamp'}.issubset(set(cols)):
                                for row in rows:
                                    r = dict(zip(cols, row))
                                    gps_entries.append({
                                        "timestamp": pd.to_datetime(r["timestamp"], unit="s", errors='coerce'),
                                        "lat": r["latitude"],
                                        "lon": r["longitude"],
                                        "source": file
                                    })
                        except:
                            continue
                    conn.close()
                except:
                    continue

    # Google JSON
    for root, _, files in os.walk(image_dir):
        for file in files:
            if file.endswith(".json") and "location" in file.lower():
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for loc in data.get("locations", []):
                            gps_entries.append({
                                "timestamp": pd.to_datetime(int(loc.get("timestampMs", 0)) // 1000, unit='s'),
                                "lat": loc.get("latitudeE7", 0) / 1e7,
                                "lon": loc.get("longitudeE7", 0) / 1e7,
                                "source": file
                            })
                except:
                    continue

    # GPX/XML
    for root, _, files in os.walk(image_dir):
        for file in files:
            if file.endswith(".gpx") or file.endswith(".xml"):
                try:
                    tree = ET.parse(os.path.join(root, file))
                    root_xml = tree.getroot()
                    ns = {'default': 'http://www.topografix.com/GPX/1/1'}
                    for trkpt in root_xml.findall(".//default:trkpt", ns):
                        lat = float(trkpt.attrib["lat"])
                        lon = float(trkpt.attrib["lon"])
                        time_tag = trkpt.find("default:time", ns)
                        timestamp = pd.to_datetime(time_tag.text) if time_tag is not None else None
                        gps_entries.append({
                            "timestamp": timestamp,
                            "lat": lat,
                            "lon": lon,
                            "source": file
                        })
                except:
                    continue

    if gps_entries:
        df = pd.DataFrame(gps_entries)
        df = df.dropna(subset=["timestamp", "lat", "lon"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    return pd.DataFrame()

import hashlib

def compute_file_hash(uploaded_file):
    hasher = hashlib.sha256()
    # Check if file-like or raw file object
    if hasattr(uploaded_file, "chunks"):
        for chunk in uploaded_file.chunks():
            hasher.update(chunk)
    else:
        hasher.update(uploaded_file.read())
    uploaded_file.seek(0)  # Reset file pointer after reading
    return hasher.hexdigest()


import datetime

def convert_for_json(obj):
    if isinstance(obj, (pd.Timestamp, datetime.datetime, datetime.date, datetime.time)):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(i) for i in obj]
    else:
        return obj


import streamlit as st
import json

def display_forensic_report(report: dict):
    st.markdown("### 📑 Forensic Report Summary")

    # Section: Metadata
    with st.expander("🧠 Model Info & Parameters", expanded=False):
        st.json({
            "Model Used": report.get("model_used", "unknown"),
            "Parameters": report.get("parameters", {})
        })

    # Section: Summary Table
    summary = report.get("summary", [])
    if not summary:
        st.info("No events in report.")
        return

    summary_df = pd.DataFrame(summary)
    summary_df["timestamp"] = pd.to_datetime(summary_df["timestamp"], errors='coerce')
    summary_df = summary_df.sort_values("timestamp")

    st.dataframe(summary_df[["timestamp", "type", "anomaly", "notes"]], use_container_width=True)

    # Optional JSON view
    with st.expander("🧾 Full Report (Raw JSON)", expanded=False):
        st.code(json.dumps(report, indent=2), language="json")

    # Download button
    st.download_button(
        "⬇️ Download Report",
        data=json.dumps(report, indent=2),
        file_name="forensic_report.json",
        mime="application/json"
    )
from fpdf import FPDF
import matplotlib.pyplot as plt
import pandas as pd
import os
import tempfile
import datetime


import unicodedata

def clean_text(text):
    return unicodedata.normalize('NFKD', text).encode('latin1', 'ignore').decode('latin1')


from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def generate_forensic_pdf_report(report_data, output_path="forensic_report.pdf"):
    """
    Generates a PDF report from structured report data.
    report_data: dict with keys - summary, alerts, parameters, file_hashes
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    y = height - 40

    def draw_title(title):
        nonlocal y
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, title)
        y -= 25

    def draw_section(title, items):
        nonlocal y
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, title)
        y -= 20
        c.setFont("Helvetica", 11)
        for key, value in items.items():
            line = f"{key}: {value}"
            if y < 60:
                c.showPage()
                y = height - 40
            c.drawString(60, y, line)
            y -= 15
        y -= 10

    def draw_list(title, list_data, limit=10):
        nonlocal y
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, title)
        y -= 20
        c.setFont("Helvetica", 11)
        for i, item in enumerate(list_data[:limit]):
            line = f"{i+1}. {item.get('timestamp', '')} - {item.get('notes', '')}"
            if y < 60:
                c.showPage()
                y = height - 40
            c.drawString(60, y, line[:100])  # Truncate long notes
            y -= 15
        y -= 10

    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, y, "🔍 Android Forensics Report")
    y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(40, y, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 30

    # Summary
    draw_section("🧾 Investigation Summary", report_data.get("findings", {}))

    # Parameters
    draw_section("⚙️ Parameters Used", report_data.get("parameters", {}))

    # Alerts
    draw_list("📢 Alerts Raised", report_data.get("alerts", []))

    # File Hashes
    hashes = {
        f"{fh['type']} ({fh['filename']})": f"{fh['sha256']} | {fh['size']} bytes"
        for fh in report_data.get("file_hashes", [])
    }
    draw_section("🔐 File Hashes", hashes)

    c.save()
    return output_path
