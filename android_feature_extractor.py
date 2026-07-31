# android_feature_extractor.py

import pandas as pd
from datetime import datetime
from utils import haversine  # Include your haversine function here

def parse_logs(gps_df, ipdr_df, cdr_df):
    # Example IP → geo mapping
    IP_GEO_DB = {
    "185.220.101.1": (48.8566, 2.3522),    # TOR exit in France
    "142.250.64.78": (37.7749, -122.4194), # Google (USA)
    "104.21.23.18": (40.7128, -74.0060),   # Discord (NY)
    "198.51.100.1": (33.6844, 73.0479),    # Fake malware (Pakistan)
}
    ipdr_df["lat"] = ipdr_df["ip"].map(lambda x: IP_GEO_DB.get(x, (None, None))[0])
    ipdr_df["lon"] = ipdr_df["ip"].map(lambda x: IP_GEO_DB.get(x, (None, None))[1])
    # Example CDR cell tower → location mapping
    CELL_TOWER_DB = {
    "DL001": (28.6139, 77.2090),  # Delhi
    "MH007": (19.0760, 72.8777),  # Mumbai
}
    cdr_df["lat"] = cdr_df["cell_id"].map(lambda x: CELL_TOWER_DB.get(x, (None, None))[0])
    cdr_df["lon"] = cdr_df["cell_id"].map(lambda x: CELL_TOWER_DB.get(x, (None, None))[1])


    gps_df['type'] = 'gps'
    ipdr_df['type'] = 'ipdr'
    cdr_df['type'] = 'cdr'
    all_df = pd.concat([gps_df, ipdr_df, cdr_df])
    all_df['timestamp'] = pd.to_datetime(all_df['timestamp'])
    return all_df.sort_values('timestamp').reset_index(drop=True)

def extract_features(timeline_df):
    features = []
    last = None

    for _, row in timeline_df.iterrows():
        feature = {
            "type_gps": 1 if row["type"].lower() == "gps" else 0,
            "type_ipdr": 1 if row["type"].lower() == "ipdr" else 0,
            "type_cdr": 1 if row["type"].lower() == "cdr" else 0,
            "hour": row["timestamp"].hour,
        }

        if last is not None:
            time_diff = (row["timestamp"] - last["timestamp"]).total_seconds()
            dist = haversine(row["lat"], row["lon"], last["lat"], last["lon"])
            speed = dist / (time_diff / 3600) if time_diff > 0 else 0
        else:
            time_diff = 0
            dist = 0
            speed = 0

        feature["delta_sec"] = time_diff
        feature["dist_km"] = dist
        feature["speed_kmph"] = speed

        features.append(feature)
        last = row

    return pd.DataFrame(features)




