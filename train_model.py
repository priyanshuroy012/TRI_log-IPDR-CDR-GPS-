import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from android_feature_extractor import parse_logs, extract_features
from utils import haversine

# 1️⃣ GPS-only training
def train_gps_only_model(gps_df):
    gps_df["timestamp"] = pd.to_datetime(gps_df["timestamp"])
    gps_df["type"] = "gps"

    timeline_df = gps_df.sort_values("timestamp").reset_index(drop=True)
    features_df = extract_features(timeline_df)

    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(features_df)

    preds = model.predict(features_df)
    timeline_df["anomaly"] = (preds == -1).astype(int)
    timeline_df["notes"] = timeline_df["anomaly"].apply(lambda x: "⚠️ Unrealistic movement" if x == 1 else "")

    return model, None, timeline_df, features_df, []  # Return empty alerts


# 2️⃣ Full-model with GPS + IPDR + CDR
def train_full_model(gps_df, ipdr_df, cdr_df,gps_threshold_km=100, max_gap_secs=900, speed_threshold=500):
    gps_df["timestamp"] = pd.to_datetime(gps_df["timestamp"])
    ipdr_df["timestamp"] = pd.to_datetime(ipdr_df["timestamp"])
    cdr_df["timestamp"] = pd.to_datetime(cdr_df["timestamp"])

    timeline_df = parse_logs(gps_df, ipdr_df, cdr_df)
    features_df = extract_features(timeline_df)

    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(features_df)

    preds = model.predict(features_df)
    timeline_df["anomaly"] = (preds == -1).astype(int)
    timeline_df["notes"] = timeline_df["anomaly"].apply(lambda x: "⚠️ Anomaly detected" if x == 1 else "")

    # 🚨 Apply rule-based detection
    from train_model import detect_spoofing_and_sim_swap
      # 🚨 Pass rule tuning params here
    timeline_df, rule_alerts = detect_spoofing_and_sim_swap(
        timeline_df,
        gps_threshold_km=gps_threshold_km,
        max_gap_secs=max_gap_secs,
    )

    return model, None, timeline_df, features_df, rule_alerts


# 3️⃣ Smart dispatcher
def train_anomaly_model(gps_df, ipdr_df=None, cdr_df=None,gps_threshold_km=100, max_gap_secs=900, speed_threshold=500):
    if (
        ipdr_df is None or ipdr_df.empty or
        cdr_df is None or cdr_df.empty
    ):
        return train_gps_only_model(gps_df)
    else:
        return train_full_model(
            gps_df, ipdr_df, cdr_df,
            gps_threshold_km=gps_threshold_km,
            max_gap_secs=max_gap_secs,
            speed_threshold=speed_threshold
        )


# 🧾 Table formatter
def format_output_table(timeline_df):
    from utils import haversine
    import re

    last = None
    timeline_df["Time"] = pd.to_datetime(timeline_df["timestamp"]).dt.strftime("%H:%M")
    timeline_df["duration"] = "—"
    timeline_df["speed_kmph"] = "—"

    if "anomaly" not in timeline_df.columns:
        timeline_df["anomaly"] = 0

    timeline_df["notes"] = timeline_df.get("notes", "").fillna("").astype(str)
    timeline_df["lat"] = pd.to_numeric(timeline_df.get("lat", None), errors='coerce')
    timeline_df["lon"] = pd.to_numeric(timeline_df.get("lon", None), errors='coerce')
    timeline_df["type"] = timeline_df.get("type", "unknown").astype(str).str.upper()
    timeline_df["domain"] = timeline_df.get("domain", pd.Series(["—"] * len(timeline_df))).fillna("—")
    timeline_df["correlation_score"] = (
        timeline_df["anomaly"].fillna(0)
        + timeline_df["notes"].str.contains("spoof", na=False).astype(int)
        + timeline_df["notes"].str.contains("jump", na=False).astype(int)
        + timeline_df["domain"].str.contains("vpn|tor|telegram", case=False, na=False).astype(int)
        if "domain" in timeline_df.columns else 0
    )

    for i, row in timeline_df.iterrows():
        notes = row.get("notes", "").strip()

        # Duration + Speed logic
        if last is not None and pd.notna(row["lat"]) and pd.notna(last["lat"]):
            duration = (row["timestamp"] - last["timestamp"]).total_seconds()
            dist = haversine(row["lat"], row["lon"], last["lat"], last["lon"])
            speed = (dist / (duration / 3600)) if duration > 0 else 0

            timeline_df.at[i, "duration"] = f"{int(duration)}s"
            timeline_df.at[i, "speed_kmph"] = f"{speed:.2f}"

            if speed > 500:
                extra_note = "⚠️ Unrealistic speed"
                if extra_note not in notes:
                    notes += " | " + extra_note
                timeline_df.at[i, 'anomaly'] = 1

        if notes.strip() == "":
            notes = "Normal"

        # Clean & format
        note_list = [re.sub(r'^\d+\.\s*', '', n.strip()) for n in notes.split("|") if n.strip()]
        formatted_notes = "\n".join([f"{j+1}. {n}" for j, n in enumerate(note_list)])
        timeline_df.at[i, "notes"] = formatted_notes

        last = row

    return timeline_df


# 🧠 Rule-based anomaly detection
def detect_spoofing_and_sim_swap(timeline_df, gps_threshold_km=100, max_gap_secs=900):
    alerts = []
    last_gps = None

    timeline_df['timestamp'] = pd.to_datetime(timeline_df['timestamp'], errors='coerce')
    if 'anomaly' not in timeline_df.columns:
        timeline_df['anomaly'] = 0
    if 'notes' not in timeline_df.columns:
        timeline_df['notes'] = ""

    MALICIOUS_DOMAINS = {
        "malicious.com", "cnc.badsite.net", "spyapp.io", "stealer.org", "malware.fake"
    }

    for i in range(1, len(timeline_df)):
        curr = timeline_df.iloc[i]
        prev = timeline_df.iloc[i - 1]
        time_diff = (curr['timestamp'] - prev['timestamp']).total_seconds()
        notes = str(curr.get("notes", "")).strip()

        # Rule 1: CDR/IPDR jump > 100km with no GPS
        if curr['type'] in ['ipdr', 'cdr'] and prev['type'] in ['ipdr', 'cdr']:
            if pd.notna(curr["lat"]) and pd.notna(prev["lat"]):
                dist = haversine(curr["lat"], curr["lon"], prev["lat"], prev["lon"])
                gps_between = timeline_df[
                    (timeline_df['type'] == 'gps') &
                    (timeline_df['timestamp'] > prev['timestamp']) &
                    (timeline_df['timestamp'] < curr['timestamp'])
                ]
                if dist > gps_threshold_km and gps_between.empty:
                    if "SIM Spoof: CDR/IP jump without GPS" not in notes:
                        notes += " | ⚠️ SIM Spoof: CDR/IP jump without GPS"
                        alerts.append((curr['timestamp'], "SIM Spoof: IP/CDR jump >100km with no GPS"))
                    timeline_df.at[i, 'anomaly'] = 1

        # Rule 2: GPS vs IP/CDR mismatch
        if curr['type'] in ['ipdr', 'cdr'] and last_gps is not None:
            gps_time_diff = abs((curr['timestamp'] - last_gps['timestamp']).total_seconds())
            gps_dist = haversine(curr.get("lat", 0), curr.get("lon", 0), last_gps['lat'], last_gps['lon'])
            if gps_time_diff <= max_gap_secs and gps_dist > gps_threshold_km:
                if "GPS-IP conflict → SIM spoof" not in notes:
                    notes += " | ⚠️ GPS-IP conflict → SIM spoof"
                    alerts.append((curr['timestamp'], "GPS-IP/CDR mismatch ➜ Possible spoof/SIM misuse"))
                timeline_df.at[i, 'anomaly'] = 1

        # Rule 3: Tower hops (IPDRs < 5min apart and far apart)
        if curr['type'] == 'ipdr' and prev['type'] == 'ipdr':
            if time_diff < 300 and pd.notna(curr["lat"]) and pd.notna(prev["lat"]):
                dist = haversine(curr["lat"], curr["lon"], prev["lat"], prev["lon"])
                if dist > 50:
                    if "Multiple IP hops" not in notes:
                        notes += " | ⚠️ Multiple IP hops"
                        alerts.append((curr['timestamp'], "Multiple IPDR tower hops in short time"))
                    timeline_df.at[i, 'anomaly'] = 1

        # Rule 4: Malicious domains or .onion
        domain = str(curr.get("domain", "")).lower()
        if curr["type"] == "ipdr":
            if ".onion" in domain:
                if "TOR Hidden Service" not in notes:
                    notes += " | ⚠️ TOR Hidden Service"
                    alerts.append((curr['timestamp'], "TOR Hidden Service accessed"))
                timeline_df.at[i, 'anomaly'] = 1
            elif domain in MALICIOUS_DOMAINS:
                if "Malware Domain" not in notes:
                    notes += " | ⚠️ Malware Domain"
                    alerts.append((curr['timestamp'], f"Malware Domain Detected: {domain}"))
                timeline_df.at[i, 'anomaly'] = 1

        timeline_df.at[i, "notes"] = notes.strip(" |")

        if curr["type"] == "gps" and pd.notna(curr.get("lat")):
            last_gps = curr

    return timeline_df, alerts









