# timeline_builder.py

import json
from utils import parse_timestamp

def build_timeline(gps_data, ipdr_data, cdr_data):
    timeline = []

    for entry in gps_data:
        timeline.append({
            "timestamp": parse_timestamp(entry["timestamp"]),
            "type": "gps",
            "lat": entry["lat"],
            "lon": entry["lon"],
            "source": entry.get("source", "location.db")
        })

    for entry in ipdr_data:
        timeline.append({
            "timestamp": parse_timestamp(entry["timestamp"]),
            "type": "ipdr",
            "source_ip": entry.get("source_ip"),
            "destination": entry.get("destination"),
            "upload": entry.get("upload"),
            "download": entry.get("download"),
            "app": entry.get("app", "unknown"),
            "location": entry.get("location")
        })

    for entry in cdr_data:
        timeline.append({
            "timestamp": parse_timestamp(entry["timestamp"]),
            "type": "cdr",
            "call_type": entry.get("call_type"),
            "number": entry.get("number"),
            "duration": entry.get("duration"),
            "location": entry.get("location")
        })

    # Sort the timeline chronologically
    timeline.sort(key=lambda x: x["timestamp"])

    return timeline


if __name__ == "__main__":
    # Example usage
    with open("sample_gps.json") as f:
        gps = json.load(f)
    with open("sample_ipdr.json") as f:
        ipdr = json.load(f)
    with open("sample_cdr.json") as f:
        cdr = json.load(f)

    timeline = build_timeline(gps, ipdr, cdr)
    
    with open("timeline_output.json", "w") as f:
        json.dump(timeline, f, indent=4, default=str)
