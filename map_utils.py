# map_utils.py



import folium
from folium.plugins import MarkerCluster
from folium import PolyLine
from utils import haversine  # assumes you have haversine(lat1, lon1, lat2, lon2)
import pandas as pd
import folium
from folium.plugins import AntPath
from utils import haversine
from streamlit_folium import st_folium


def create_hybrid_movement_map_with_labels(timeline_df):
    if timeline_df.empty:
        return folium.Map(location=[20.5937, 78.9629], zoom_start=5)

    m = folium.Map(location=[timeline_df['lat'].mean(), timeline_df['lon'].mean()], zoom_start=6)
    last_point = None

    for i, row in timeline_df.iterrows():
        lat, lon = row['lat'], row['lon']
        if pd.isna(lat) or pd.isna(lon):
            continue

        notes = row.get("notes", "").lower()
        color = "blue"
        icon = "info-sign"

        if "unrealistic" in notes or "jump" in notes:
            color = "yellow"
        elif "spoof" in notes:
            color = "orange"
        elif "vpn" in notes or "tor" in notes or "suspicious domain" in notes:
            color = "purple"
        if row.get("anomaly", 0) == 1 and notes.count("⚠️") >= 2:
            color = "red"

        folium.Marker(
            [lat, lon],
            popup=f"{row['timestamp']}<br>{row.get('notes', '')}",
            icon=folium.Icon(color=color, icon=icon)
        ).add_to(m)

        if last_point is not None:
            folium.PolyLine(
                [last_point, [lat, lon]],
                color=color,
                weight=3,
                opacity=0.6
            ).add_to(m)

        last_point = [lat, lon]

    return m

import folium
import pandas as pd
from folium.plugins import TimestampedGeoJson
import streamlit as st
from datetime import timedelta


def display_timeline_with_playback(timeline_df):
    if timeline_df.empty:
        st.warning("No data to visualize.")
        return

    timeline_df["timestamp"] = pd.to_datetime(timeline_df["timestamp"], errors='coerce')
    timeline_df = timeline_df.dropna(subset=["lat", "lon"])

    from datetime import timedelta
    # 1️⃣ Time Slider
    min_time = timeline_df["timestamp"].min().to_pydatetime()
    max_time = timeline_df["timestamp"].max().to_pydatetime()
    selected_range = st.slider(
    "🕐 Select Time Range",
    min_value=min_time,
    max_value=max_time,
    value=(min_time, max_time),
    step=timedelta(hours=1),
    format="YYYY-MM-DD HH:mm"
)


    # 2️⃣ Filter by time
    filtered_df = timeline_df[
        (timeline_df["timestamp"] >= selected_range[0]) &
        (timeline_df["timestamp"] <= selected_range[1])
    ].copy()

    if filtered_df.empty:
        st.info("No events in selected range.")
        return

    # 3️⃣ Prepare GeoJSON Features for TimestampedGeoJson
    features = []
    for _, row in filtered_df.iterrows():
        notes = row.get("notes", "")
        anomaly = int(row.get("anomaly", 0))
        color = "red" if anomaly else "blue"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["lon"], row["lat"]]
            },
            "properties": {
                "time": row["timestamp"].isoformat(),
                "popup": f"{row['timestamp']}<br>{notes}",
                "icon": "circle",
                "iconstyle": {
                    "fillColor": color,
                    "fillOpacity": 0.8,
                    "stroke": "true",
                    "radius": 6
                }
            }
        }
        features.append(feature)

    # 4️⃣ Create Map + TimestampedGeoJson
    m = folium.Map(location=[filtered_df["lat"].mean(), filtered_df["lon"].mean()], zoom_start=6)
    TimestampedGeoJson(
        {
            "type": "FeatureCollection",
            "features": features
        },
        period="PT1M",
        add_last_point=True,
        auto_play=True,
        loop=False,
        max_speed=1,
        loop_button=True,
        date_options="YYYY-MM-DD HH:mm:ss",
        time_slider_drag_update=True
    ).add_to(m)

    st.markdown("### 🎥 Animated Playback")
    st_folium(m, width=800, height=550)
