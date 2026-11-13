# Urban Company Native M2 Smart Water Purifier Monitor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-REST%20Sensor-blue.svg)](https://www.home-assistant.io/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Tested Device](https://img.shields.io/badge/Tested%20On-Native%20M2%20(Nov%202026)-success.svg)](https://www.urbancompany.com/)

An unofficial Python client and **Home Assistant integration** for the **Urban Company Native M2 Smart RO Water Purifier**.

Tracks **real-time output TDS (ppm)**, online/offline status, filter life remaining, warranty status, and daily water consumption without hardware modifications.

> **Compatibility Notice:**  
> **Tested and confirmed working as of November 2026 on the Urban Company Native M2**.  
> Other models (Native M1, M2 Pro, M3) likely share the same IoTfy/Urban Company API structure, but have not been independently verified. If you test on other models, please feel free to open an issue or pull request!

---

## The Backstory

Many owners of the Urban Company Native water purifiers have wanted to integrate real-time TDS and water metrics into Home Assistant or personal dashboards. However, the manufacturer does not expose any local dashboard, local API, or open MQTT broker.

This repository provides a clean, working solution and documents the underlying hardware and network findings so others (and AI coding assistants) don't have to waste time exploring dead ends.

---

## How to Get Your Credentials (30-Second Desktop Browser Method)

**You do NOT need `mitmproxy` or special certificates.** You can grab your token directly using your desktop web browser (Brave, Chrome, Edge, or Firefox):

1. On your computer, open **[https://www.urbancompany.com](https://www.urbancompany.com/)**.
2. Press **`F12`** (or right-click > *Inspect*) to open Developer Tools, and switch to the **Network** tab.
3. In the filter box at the top, select **`Fetch/XHR`**.
4. Log into Urban Company on the website using your mobile number and SMS OTP.
5. In the Network tab, click on any recent request (e.g., `getDiscoveryScreenData`, `getDetailsScreen`, or any API call).
6. Under the **Headers** tab, scroll to **Request Headers**:
   - Copy the value of **`authorization`** (e.g., `Bearer 9RjErhLBBLHoaZqHp...`).
   - Copy the value of **`x-device-id`** (e.g., `v-1794569622`).
7. To find your **`applianceId`**:
   - In the Network search (Ctrl+F inside DevTools), search for `applianceId`.
   - Or open your purifier details and look for the payload sent to `/getDetailsScreen`.
8. Paste these into `config.json` (see Quick Start below).

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
Edit `config.json` with your captured credentials:
```json
{
  "appliance_id": "67245f04f6203600xxxxxxxx",
  "authorization": "Bearer 9RjErhLBBLHoaZqHp0EApwau0tcj1XBa2arEfkCZXuQ=",
  "device_id": "v-1794569622",
  "brand_key": "urbanCompany",
  "version_code": "4.273.58",
  "device_os": "desktop_web"
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
    Nov 13   :  3 L  ###
    Nov 14   :  0 L  
    Nov 15   :  0 L  
====================================================
```

---

## Home Assistant Integration

Add the sensors to your Home Assistant `configuration.yaml`:

```yaml
rest:
  - resource: https://www.urbanclap.com/api/v2/growth/appliances/getDetailsScreen
    method: POST
    scan_interval: 300 # Poll every 5 minutes (300s)
    headers:
      Authorization: "Bearer YOUR_BEARER_TOKEN_HERE"
      x-device-id: "YOUR_DEVICE_ID"
      x-device-os: "desktop_web"
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
**The desktop web API endpoint is the cleanest, easiest path.** It requires no physical soldering, avoids proxy/certificate hassles, doesn't void your 2-year warranty, and gives full real-time telemetry.

---

## Disclaimer

This is an independent, community-driven open-source project created strictly for personal home automation and interoperability. It is not affiliated with, endorsed by, or sponsored by Urban Company (UrbanClap Technologies Pvt. Ltd.). All product names, trademarks, and registered trademarks belong to their respective holders.

---

## License

[MIT License](LICENSE)
