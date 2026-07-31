# correlation_engine.py

from datetime import timedelta

def correlate_events(timeline, max_time_diff_sec=120):
    correlated = []

    for i, event in enumerate(timeline):
        entry = event.copy()
        entry["correlated"] = []

        for j in range(i+1, len(timeline)):
            other = timeline[j]
            time_diff = abs((other["timestamp"] - event["timestamp"]).total_seconds())

            if time_diff > max_time_diff_sec:
                break  # events too far apart

            # Example correlation logic
            if event["type"] == "gps" and other["type"] == "ipdr":
                entry["correlated"].append({
                    "type": "ipdr",
                    "upload": other.get("upload"),
                    "download": other.get("download"),
                    "app": other.get("app")
                })

            if event["type"] == "cdr" and other["type"] == "gps":
                entry["correlated"].append({
                    "type": "gps",
                    "lat": other.get("lat"),
                    "lon": other.get("lon")
                })

        correlated.append(entry)

    return correlated


if __name__ == "__main__":
    import json
    from utils import parse_timestamp

    with open("timeline_output.json") as f:
        raw_timeline = json.load(f)

    # Ensure datetime format
    for event in raw_timeline:
        event["timestamp"] = parse_timestamp(event["timestamp"])

    correlated = correlate_events(raw_timeline)

    with open("correlated_timeline.json", "w") as f:
        json.dump(correlated, f, indent=4, default=str)
