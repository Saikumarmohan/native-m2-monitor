# Urban Company Native M2 / M1 Smart Water Purifier Monitor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-REST%20Sensor-blue.svg)](https://www.home-assistant.io/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)

An unofficial Python client and **Home Assistant integration** for the **Urban Company Native M2 / M1 / M3 Smart RO Water Purifiers**.

Tracks **real-time output TDS (ppm)**, online/offline status, filter life remaining, warranty status, and daily water consumption without hardware modifications.

---

## The Backstory

Many owners of the Urban Company Native water purifiers have wanted to integrate real-time TDS and water metrics into Home Assistant or personal dashboards. However, the manufacturer does not expose any local dashboard, local API, or open MQTT broker.

This repository provides a clean, working solution and documents the underlying hardware and network findings so others (and AI coding assistants) don't have to waste time exploring dead ends.

---

## Hardware & Network Reverse-Engineering Findings

*(Why connecting directly to the purifier's local IP or setting up a rogue hotspot does not work)*

During hardware and network packet analysis, we verified the complete internal architecture of the Native M2 purifier:

### 1. The Microcontroller
* **Chip:** **Espressif ESP8266** running **IoTfy Embedded C++ SDK (v10)** (`User-Agent: ESP8266HTTPClient`).
* **MAC Prefix:** `34:AB:95:xx:xx:xx`.
* **Zero Local Ports:** The ESP8266 has **no open listening ports** (no local web server on port 80, 8080, or 443). Querying its local IP directly (`192.168.x.x`) times out or drops packets.

### 2. The Cloud Protocol & Security
* **Time Sync:** Upon boot, it performs an unencrypted HTTP call to `iace.iotfy.com/t/getTimeMs` on port 80 (hosted on Google App Engine) to sync internal epoch time.
* **Telemetry Connection:** It connects outbound to **AWS IoT Core** (Mumbai region) at `*.iot.ap-south-1.amazonaws.com:8883`.
* **Mutual TLS (mTLS):** The connection strictly enforces **mTLS**. The ESP8266 has an official **X.509 client certificate and private key burned into flash memory** (valid through 2049) signed by Amazon Web Services.
* **Why "Fake Cloud" / DNS Spoofing Fails:** If you redirect the domain to a local Mosquitto MQTT broker on a Raspberry Pi or router, the ESP8266 strictly verifies Amazon's Root CA. It rejects custom/self-signed certificates during the TLS handshake and immediately aborts the connection.

### 3. The Android App SSL Restriction
If you attempt to proxy the official mobile app using tools like `mitmproxy`, Android 7+ enforces **Network Security Config**, which ignores user-installed CA certificates by default (`Client TLS handshake failed: certificate unknown`).

### Conclusion
**The cloud API endpoint used by the mobile webview is the cleanest, non-destructive path.** It requires no physical soldering, doesn't void your 2-year warranty, and gives full real-time telemetry.

---

## Features

- [x] **Live Output TDS** (in `ppm`) + health status badge (`Healthy` / `Moderate` / `High`).
- [x] **Online Status** (`ONLINE` / `OFFLINE`).
- [x] **Filter Life Tracking** (days remaining + replacement alerts).
- [x] **Daily Water Consumption** (litres dispensed per day + 7-day average).
- [x] **Home Assistant Ready** (pre-built REST sensor definitions).
- [x] **Lightweight CLI** (prints formatted stats in 0.5 seconds).

---

## Quick Start (Python CLI)

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/native-m2-monitor.git
cd native-m2-monitor
```

### 2. Configure credentials
Copy the example configuration:
```bash
cp config.example.json config.json
```
Edit `config.json` with your captured `appliance_id` and `authorization` token (see below for how to get these):
```json
{
  "appliance_id": "67245f04f6203600xxxxxxxx",
  "authorization": "Bearer 1t3Df8X8J6thVnp2bMEiBJ/xxxx...",
  "device_id": "v-1794569747",
  "brand_key": "urbanCompany",
  "version_code": "4.273.58",
  "device_os": "web"
}
```

### 3. Run the status monitor
```bash
python get_status.py
```

Sample output:
```text
====================================================
  Native M2 SMART WATER PURIFIER MONITOR
====================================================
  Status          : ONLINE
  Live Output TDS : 79 ppm (Healthy)
  Filter Status   : 1 filter needs attention
  Filter Life     : Life left: 0 days
  Warranty        : Expired
----------------------------------------------------
  Water Usage (Nov 9 - 15):
  Average Daily   : 5 Litres / day
  Daily Breakdown :
    Nov 9    :  7 L  #######
    Nov 10   :  5 L  #####
    Nov 11   :  4 L  ####
    Nov 12   :  5 L  #####
    Nov 13   :  2 L  ##
    Nov 14   :  0 L  
    Nov 15   :  0 L  
====================================================
```

---

## How to Capture Your Auth Token (30-Second Guide)

Because Urban Company uses a webview/micro-frontend for appliance details, you can extract your token easily:

1. **Start an HTTP proxy** (such as [mitmproxy](https://mitmproxy.org/), Charles, or Reqable) on your computer.
2. Set your phone's Wi-Fi proxy to your computer's IP on port `8080` and install the proxy CA certificate via `http://mitm.it`.
3. Open your mobile browser (or the Urban Company app) and navigate to your **Native Purifier** details page.
4. Filter captured requests for `urbanclap.com/api/v2/growth/appliances/getDetailsScreen`.
5. Copy two values into `config.json`:
   - `applianceId`: Found in the POST JSON body.
   - `Authorization`: Found in the HTTP request headers (`Bearer ...`).
6. Turn off the proxy on your phone. The token is long-lived and will remain valid for months.

---

## Home Assistant Integration

Add the sensors to your Home Assistant `configuration.yaml`:

```yaml
rest:
  - resource: https://www.urbanclap.com/api/v2/growth/appliances/getDetailsScreen
    method: POST
    scan_interval: 300 # Poll every 5 minutes
    headers:
      Authorization: "Bearer YOUR_BEARER_TOKEN_HERE"
      x-device-id: "v-1794569747"
      x-device-os: "web"
      Content-Type: "application/json"
      x-brand-key: "urbanCompany"
      x-version-code: "4.273.58"
      User-Agent: "HomeAssistant/NativeM2"
    payload: '{"city_key":null,"applianceId":"YOUR_APPLIANCE_ID_HERE"}'
    sensor:
      - name: "Purifier TDS"
        unique_id: native_m2_tds
        value_template: "{{ value_json.success.data.dataStore.bigMetricHeader.metricData.metricKeyText.textValue | int }}"
        unit_of_measurement: "ppm"
        state_class: measurement
        icon: mdi:water-check

      - name: "Purifier Status"
        unique_id: native_m2_status
        value_template: "{{ value_json.success.data.dataStore.header.badgeStack.tags[0].text }}"
        icon: mdi:power

      - name: "Purifier Filter Status"
        unique_id: native_m2_filter_status
        value_template: "{{ value_json.success.data.dataStore.filterDetailsCard.items[1].data.adsTextStack.items[0].data.text }}"
        icon: mdi:filter-cog

      - name: "Purifier Warranty Status"
        unique_id: native_m2_warranty_status
        value_template: "{{ value_json.success.data.dataStore.warrantyCard.items[0].data.adsTextStack.items[0].data.tags[0].text }}"
        icon: mdi:shield-alert
```

Restart Home Assistant. You now have `sensor.purifier_tds`, `sensor.purifier_status`, and filter life entities ready to display on your dashboard!

---

## Disclaimer

This is an independent, community-driven open-source project created strictly for personal home automation and interoperability. It is not affiliated with, endorsed by, or sponsored by Urban Company (UrbanClap Technologies Pvt. Ltd.). All product names, trademarks, and registered trademarks belong to their respective holders.

---

## License

[MIT License](LICENSE)
