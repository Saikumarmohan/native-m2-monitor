# Unofficial Native M2 Smart Water Purifier Monitor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-REST%20Sensor-blue.svg)](https://www.home-assistant.io/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Personal%20Research%20POC-orange.svg)](https://opensource.org/)

An unofficial Python client and **Home Assistant integration** developed strictly for **personal home automation, protocol research, and device interoperability** with the Native M2 Smart RO Water Purifier.

> [!CAUTION]
> ### Important Legal Disclaimer & Trademark Notice
> * **No Affiliation or Endorsement:** This repository is an independent personal project. It is **not** affiliated with, sponsored by, authorized by, or endorsed by Urban Company (UrbanClap Technologies India Pvt. Ltd.) or IoTfy Solutions Pvt. Ltd.
> * **Nominative Trademark Use:** "Urban Company", "UrbanClap", "Native", "Native M2", and related marks are trademarks of their respective owners. Their mention here is strictly for descriptive and nominative identification purposes to establish device compatibility under fair use.
> * **Private / Undocumented APIs:** The endpoints described in this repository are private, internal service endpoints. They are unsupported, unversioned, and subject to change, breaking modifications, or access restrictions at any time without notice.
> * **Personal Use & Scope:** This code is shared as an educational research artifact and personal interoperability tool. It is provided "as is" with no guarantees of fitness, ongoing availability, or support. Use responsibly at your own discretion.

> [!NOTE]
> **Compatibility Scope:**  
> Tested on a single personal **Native M2** unit as of November 2026. Other models have not been verified.

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [How It Works (For Humans & AI Agents)](#how-it-works-for-humans--ai-agents)
- [Reverse-Engineering & Hardware Findings](#reverse-engineering--hardware-findings)
  - [Hardware Specs](#1-hardware-specifications)
  - [Network & Protocol Analysis](#2-network--protocol-analysis)
  - [Why Direct Local Connection Fails (Dead Ends Analyzed)](#3-why-direct-local-connection-fails-dead-ends-analyzed)
- [Quick Start Guide](#quick-start-guide)
  - [1. 30-Second Token Capture (Desktop Browser)](#step-1-capture-your-credentials-desktop-browser-method)
  - [2. Configuration](#step-2-configure-credentials)
  - [3. Run the CLI Monitor](#step-3-run-the-cli-monitor)
- [Home Assistant Integration](#home-assistant-integration)
  - [Sensor Configuration (`configuration.yaml`)](#home-assistant-configurationyaml)
  - [Lovelace Dashboard Card Example](#sample-lovelace-dashboard-card)
- [API Reference](#api-reference)
- [Troubleshooting & Token Renewal](#troubleshooting--token-renewal)
- [Legal Disclaimer & License](#legal-disclaimer--license)

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Hardware ["Native M2 Purifier (Inside Your Home)"]
        Sensors["TDS Probe + Flow Meter"] --> ESP8266["Espressif ESP8266<br>(IoTfy SDK v10)"]
    end

    subgraph ManufacturerCloud ["Manufacturer Cloud Infrastructure"]
        TimeServer["iace.iotfy.com<br>(HTTP Port 80 Clock Sync)"]
        AWSIoT["AWS IoT Core (Mumbai)<br>a3814bo3dsv6qh-ats.iot.ap-south-1.amazonaws.com:8883<br>(Mutual TLS / mTLS)"]
        UCBackend["Urban Company Backend<br>api.urbanclap.com/api/v2/..."]
    end

    subgraph UserInterface ["Your Monitoring Clients"]
        CLI["Python CLI<br>(get_status.py)"]
        HA["Home Assistant<br>(REST Sensors)"]
    end

    ESP8266 -- "1. HTTP getTimeMs" --> TimeServer
    ESP8266 -- "2. MQTTS (mTLS Encrypted)" --> AWSIoT
    AWSIoT <--> UCBackend
    UserInterface -- "3. HTTPS REST (Bearer Auth)" --> UCBackend
```

---

## How It Works (For Humans & AI Agents)

Instead of intercepting encrypted hardware packets or opening the appliance casing, this integration interfaces directly with Urban Company's micro-frontend API endpoint:

1. **Authentication:** Uses a standard long-lived **Bearer session token** obtained from logging into your Urban Company account.
2. **Details Endpoint:** Queries `POST /api/v2/growth/appliances/getDetailsScreen` to get the digital twin state (live output TDS, online state, filter life, warranty).
3. **Consumption Endpoint:** Queries `POST /api/v2/supply/appliances/getWaterConsumptionData` to get daily water dispensing volume history.
4. **Execution:** Runs via a lightweight standard Python script (`native_m2.py`) or as native Home Assistant REST sensors with zero external daemon dependencies.

---

## Reverse-Engineering & Hardware Findings

*(Documented to save other developers and AI assistants from repeating packet-sniffing experiments)*

During network packet analysis (capturing through an isolated 2.4 GHz Access Point with `tcpdump` and Wireshark), we determined the complete internal hardware and protocol stack:

### 1. Hardware Specifications
* **Microcontroller:** **Espressif ESP8266** running the **IoTfy Embedded C++ SDK (v10)**.
* **User-Agent:** `ESP8266HTTPClient`.
* **MAC Address OUI:** `34:AB:95:xx:xx:xx` (Espressif Systems).
* **Wi-Fi Radio:** Strictly **2.4 GHz** (802.11b/g/n, channels 1–11). The hardware does not contain a 5 GHz antenna.

### 2. Network & Protocol Analysis
When the purifier boots up:
1. **Clock Sync:** Sends an unencrypted HTTP GET request to `http://iace.iotfy.com/t/getTimeMs` on port 80 (hosted on Google App Engine) with headers `ESP-MAC-ADDR` and `X-IOTFY-LIB-VERSION: 10` to sync system epoch time.
2. **Cloud Broker Handshake:** Opens a TCP connection on port **8883 (MQTTS)** to `a3814bo3dsv6qh-ats.iot.ap-south-1.amazonaws.com` (AWS IoT Core in Mumbai).
3. **Mutual TLS (mTLS):** The ESP8266 and AWS IoT perform mutual authentication. The device presents an internal client certificate:
   - **Issuer:** `Amazon Web Services (AWS IoT Certificate)`
   - **Validity:** Valid through year 2049.
4. **Encrypted Telemetry:** All sensor telemetry (TDS, flow pulses, keepalives) is transmitted inside encrypted TLS Application Data packets.

### 3. Why Direct Local Connection Fails (Dead Ends Analyzed)

| Approach Attempted | What Happens | Why It Fails |
|---|---|---|
| **Direct IP Query (`http://192.168.x.x`)** | Connection refused / timed out | **No open listening ports.** The ESP8266 does not run an HTTP or local web server to save RAM. All connections are outbound. |
| **Rogue Hotspot / DNS Spoofing** | Purifier disconnects and retries | **Strict mTLS.** The ESP8266 hardcodes Amazon's Root CA and sends a client certificate. Local brokers (Mosquitto) fail the TLS handshake. |
| **Android App Proxying (`mitmproxy`)** | `Client TLS handshake failed` | **Android 7+ Security.** Android blocks user-installed CA certificates inside apps unless the app is modified or phone is rooted. |
| **Desktop Web API (Working)** | **HTTP 200 OK** | **Bypasses all hurdles.** Provides clean JSON telemetry with zero hardware tampering or voided warranties. |

---

## Quick Start Guide

### Step 1: Capture Your Credentials (Desktop Browser Method)

> [!TIP]
> **No proxy, mobile phone setup, or root certificates required.**

1. On your computer, open **[https://www.urbancompany.com](https://www.urbancompany.com/)** in any browser (Brave, Chrome, Edge, Firefox).
2. Press **`F12`** (or right-click > **Inspect**) and go to the **Network** tab.
3. In the filter box, select **`Fetch/XHR`**.
4. Log into Urban Company using your mobile phone number and SMS OTP.
5. In the Network tab list, click on any recent request (e.g., `getDiscoveryScreenData` or `getDetailsScreen`).
6. In the **Headers** tab, scroll to **Request Headers**:
   - Copy **`authorization`** (e.g., `Bearer 9RjErhLBBLHoaZq...`).
   - Copy **`x-device-id`** (e.g., `v-1794569622`).
7. To find your **`applianceId`**:
   - In DevTools, press `Ctrl+F` and search for `applianceId`.
   - Or click on your purifier in the browser and inspect the payload sent to `/getDetailsScreen`.

---

### Step 2: Configure Credentials

1. Clone or download this repository:
   ```bash
   git clone https://github.com/Saikumarmohan/native-m2-monitor.git
   cd native-m2-monitor
   ```
2. Copy the template:
   ```bash
   cp config.example.json config.json
   ```
3. Edit `config.json` with your captured credentials:
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

---

### Step 3: Run the CLI Monitor

Execute the monitor script:
```bash
python get_status.py
```

Output:
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

### `configuration.yaml`

Add the following to your Home Assistant `configuration.yaml`. Replace `YOUR_BEARER_TOKEN` and `YOUR_APPLIANCE_ID` with your values:

```yaml
rest:
  - resource: https://www.urbanclap.com/api/v2/growth/appliances/getDetailsScreen
    method: POST
    scan_interval: 300 # Poll every 5 minutes (300 seconds)
    headers:
      Authorization: "Bearer YOUR_BEARER_TOKEN"
      x-device-id: "v-1794569622"
      x-device-os: "desktop_web"
      Content-Type: "application/json"
      x-brand-key: "urbanCompany"
      x-version-code: "4.273.58"
      User-Agent: "HomeAssistant/NativeM2"
    payload: '{"city_key":null,"applianceId":"YOUR_APPLIANCE_ID"}'
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

### Sample Lovelace Dashboard Card

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.purifier_tds
    min: 0
    max: 300
    name: Purifier TDS
    severity:
      green: 0
      yellow: 100
      red: 150
  - type: entities
    entities:
      - entity: sensor.purifier_status
        name: Online Status
      - entity: sensor.purifier_filter_status
        name: Filter Status
      - entity: sensor.purifier_warranty_status
        name: Warranty
```

---

## API Reference

### 1. Appliance Details & Live TDS
* **URL:** `POST https://www.urbanclap.com/api/v2/growth/appliances/getDetailsScreen`
* **Payload:** `{"city_key": null, "applianceId": "<id>"}`
* **Key Response Paths:**
  - `success.data.dataStore.bigMetricHeader.metricData.metricKeyText.textValue` -> Live TDS (e.g. `"79"`)
  - `success.data.dataStore.bigMetricHeader.metricData.supScriptText.textValue` -> Unit (`"ppm"`)
  - `success.data.dataStore.bigMetricHeader.metricData.badge.text` -> Health badge (`"Healthy"`)
  - `success.data.dataStore.header.badgeStack.tags[0].text` -> Connection state (`"ONLINE"`)
  - `success.data.dataStore.filterDetailsCard.items[1].data.adsTextStack.items[0].data.text` -> Filter note

### 2. Water Consumption History
* **URL:** `POST https://www.urbanclap.com/api/v2/supply/appliances/getWaterConsumptionData`
* **Payload:** `{"city_key": null, "applianceId": "<id>", "timeStampOfLastDayInWeek": <timestamp_ms>}`
* **Key Response Paths:**
  - `success.data.historicWaterConsumptionData[0].average` -> Average daily litres
  - `success.data.historicWaterConsumptionData[0].dailyData` -> Array of `{"dateText": "Nov 13", "value": 3}`

---

## Troubleshooting & Token Renewal

### How Long Does the Token Last?
Urban Company session tokens (`Bearer ...`) are long-lived (typically valid for **several months to a year**), provided you do not manually click "Log Out" in that browser session.

### What Happens When It Expires?
If the token expires, the client and Home Assistant will receive an `HTTP 401 Unauthorized` or `403 Forbidden`. The Python script will output:
```text
[AUTH ERROR] Authorization token has expired or is invalid. 
Please re-capture your Bearer token and update config.json.
```
To renew: open `urbancompany.com`, press `F12`, log in via OTP, and copy the new `Bearer` string into `config.json` or your Home Assistant `configuration.yaml`.

---

## Legal Disclaimer & Responsible Use

### 1. Trademark Non-Affiliation
This repository is an independent research project and is **not affiliated with, authorized, maintained, or endorsed by Urban Company (UrbanClap Technologies India Pvt. Ltd.)**, IoTfy Solutions Pvt. Ltd., or any of their affiliates. The names "Urban Company", "UrbanClap", "Native", and "IoTfy" are used exclusively for nominative identification and interoperability descriptions under fair use principles.

### 2. Terms of Service & API Considerations
* The endpoints utilized in this project are undocumented, private APIs. They are subject to change, rate-limiting, or revocation by the service operator at any time without prior notice.
* This tool is intended solely for personal, private automation and educational protocol research on appliances you legally own.
* **Responsible Polling:** Always maintain a conservative polling interval (e.g., 5 to 10 minutes or longer). Do not perform high-frequency polling, scraping, or automated stress-testing against third-party backends.

### 3. Limitation of Liability
The software is provided "AS IS", without warranty of any kind, express or implied. Under no circumstances shall the authors or copyright holders be liable for any claim, damages, service interruption, account restriction, or hardware malfunction arising from the use of this software.

---

## License

Distributed under the [MIT License](LICENSE).
