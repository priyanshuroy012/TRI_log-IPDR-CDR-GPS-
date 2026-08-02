# IPDR Integration Module – DIFA (Digital Investigator for Android)

# Deployed Link https://axbtp2prklgtf8kdrmb9j4.streamlit.app/
 
The **IPDR (Internet Protocol Detail Record) Integration Module** is part of the **DIFA** forensic suite.  
It allows investigators to **ingest, process, and correlate IPDR data** with GPS and CDR records to identify suspicious network activity, location mismatches, and behavioral anomalies.

---

## 📌 Overview
IPDR records contain detailed metadata about internet usage sessions from telecom operators.  
When combined with **GPS** and **CDR** data, the module can:
- Map user activity across **time, network, and location** dimensions.
- Detect possible **SIM swaps, IP spoofing, and abnormal travel patterns**.
- Correlate internet activity with **physical presence** for investigative leads.
<img width="514" height="155" alt="image" src="https://github.com/user-attachments/assets/5b1e0c7f-5463-43cc-b95d-6daeced38b0b" />
<img width="509" height="221" alt="image" src="https://github.com/user-attachments/assets/5b2d3ae9-8886-4684-a0e3-5217b4886b2a" />


---

## 🚀 Features
- **Multi-source Integration**  
  Load and merge IPDR data with GPS and CDR datasets.
  
- **Anomaly Detection**  
  Uses Isolation Forest and Autoencoder ML models to detect:
  - Impossible travel distances between logins.
  - Multiple IP addresses from different regions in short intervals.
  - Mismatches between GPS location and IP geolocation.
  - <img width="478" height="278" alt="image" src="https://github.com/user-attachments/assets/262fc3f4-86c0-4731-bb55-672c8e879ac1" />


- **Visualization**  
  Interactive timeline & map for:
  - Session start/end times.
  - IP location plotting.
  - Behavioral profile clusters.
  - <img width="469" height="247" alt="image" src="https://github.com/user-attachments/assets/8cc08960-d0f7-4b16-9299-611d5af16f87" />


- **Forensic Output**  
  - Highlighted suspicious events.
  - Exportable CSV & unified PDF report integration.
 
  - <img width="496" height="242" alt="image" src="https://github.com/user-attachments/assets/ed588512-7a2b-47ac-9577-7aac56b651a0" />


---

## 📂 Input Format
**CSV Columns  (Required):
```text
timestamp, ip_address, port, session_duration, device_id, imsi, imei


🛠 How It Works
Data Loading – Upload IPDR CSV or extract from device image via DIFA's evidence handler.

Integration – Merge with GPS & CDR datasets.

Anomaly Analysis – Apply ML and rule-based checks.

Visualization – Render interactive map and timeline.

Reporting – Send anomalies to the unified DIFA report.

🧠 Algorithms Used
Isolation Forest (Sklearn) – Detect statistical outliers in geolocation and IP changes.

Autoencoder (Keras/TensorFlow) – Detect deviations from normal behavior patterns.

GeoIP Lookup – Map IP addresses to physical locations.

Haversine Distance – Calculate distance between GPS points to flag impossible travel.

📊 Outputs
Interactive session map with cluster-based color coding.

Anomaly table with:

Timestamp

IP address & geolocation

Risk classification (Low / Medium / High)

Export to CSV, JSON, or unified PDF.

📜 Example Use Case
An investigator uploads an IPDR log and GPS data from a suspect's device. The system detects that on the same day:

GPS shows location in Delhi

IP geolocation points to Singapore

Travel gap is < 5 minutes
The system flags this as a probable VPN/proxy use or account compromise.

📦 Installation & Usage
This module is part of DIFA and not intended for standalone deployment.

Inside DIFA:

streamlit run app.py
# Select IPDR Integration from module drawer


yaml
