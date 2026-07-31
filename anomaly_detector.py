# anomaly_detector.py

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from utils import haversine

def extract_features(timeline):
    features = []

    last_location = None
    last_time = None

    for event in timeline:
        feature = {
            "type_gps": 1 if event["type"] == "gps" else 0,
            "type_ipdr": 1 if event["type"] == "ipdr" else 0,
            "type_cdr": 1 if event["type"] == "cdr" else 0,
            "upload": event.get("upload", 0),
            "download": event.get("download", 0),
            "duration": event.get("duration", 0),
            "hour": event["timestamp"].hour,
            "speed": 0  # will be filled later if GPS
        }

        if event["type"] == "gps":
            if last_location and last_time:
                dist = haversine(
                    last_location[0], last_location[1],
                    event["lat"], event["lon"]
                )
                time_diff = (event["timestamp"] - last_time).total_seconds() / 3600
                if time_diff > 0:
                    feature["speed"] = dist / time_diff  # km/h

            last_location = (event["lat"], event["lon"])
            last_time = event["timestamp"]

        features.append(feature)

    return pd.DataFrame(features)


def detect_anomalies(timeline):
    df = extract_features(timeline)

    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(df)

    df["anomaly_score"] = model.decision_function(df)
    df["is_anomaly"] = model.predict(df)  # -1 for anomaly

    # Attach results back to timeline
    for i, event in enumerate(timeline):
        event["anomaly_score"] = round(float(df.loc[i, "anomaly_score"]), 4)
        event["is_anomaly"] = int(df.loc[i, "is_anomaly"] == -1)

    return timeline


if __name__ == "__main__":
    import json
    from utils import parse_timestamp

    with open("timeline_output.json") as f:
        timeline = json.load(f)

    for event in timeline:
        event["timestamp"] = parse_timestamp(event["timestamp"])

    result = detect_anomalies(timeline)

    with open("anomaly_output.json", "w") as f:
        json.dump(result, f, indent=4, default=str)
