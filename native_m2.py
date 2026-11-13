"""
Native M2 Smart Water Purifier API Client
------------------------------------------
Extracts real-time TDS, online status, filter health, and daily water consumption
from Urban Company's appliance API.
"""

import json
import urllib.request
import urllib.error
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILE = Path(__file__).parent / "config.json"

class NativeM2Client:
    def __init__(self, config_path: Optional[Path] = None):
        cfg_path = config_path or CONFIG_FILE
        if not cfg_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found at '{cfg_path}'. "
                f"Please copy 'config.example.json' to 'config.json' and fill in your credentials."
            )

        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.appliance_id = self.config["appliance_id"]
        self.headers = {
            "authorization": self.config["authorization"],
            "x-device-id": self.config.get("device_id", "v-1794569747"),
            "x-device-os": self.config.get("device_os", "web"),
            "content-type": "application/json",
            "x-brand-key": self.config.get("brand_key", "urbanCompany"),
            "x-version-code": self.config.get("version_code", "4.273.58"),
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NativeM2Client/1.0"
        }

    def _post(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise PermissionError(
                    "Authorization token has expired or is invalid. "
                    "Please re-capture your Bearer token and update config.json."
                ) from e
            raise RuntimeError(f"HTTP Error {e.code}: {e.reason}") from e

    def get_details(self) -> Dict[str, Any]:
        """
        Fetches purifier real-time details: online status, TDS, filter life, warranty.
        """
        url = "https://www.urbanclap.com/api/v2/growth/appliances/getDetailsScreen"
        payload = {"city_key": None, "applianceId": self.appliance_id}
        res = self._post(url, payload)

        if res.get("isError") or not res.get("success"):
            raise RuntimeError(f"API Error: {res}")

        ds = res["success"]["data"]["dataStore"]

        # Parse Header & Online Status
        header = ds.get("header", {})
        tags = header.get("badgeStack", {}).get("tags", [])
        status = tags[0].get("text", "UNKNOWN") if tags else "UNKNOWN"
        device_name = header.get("title", {}).get("textValue", "Native M2")

        # Parse Live TDS
        big_metric = ds.get("bigMetricHeader", {}).get("metricData", {})
        tds_val = big_metric.get("metricKeyText", {}).get("textValue", "0")
        tds_unit = big_metric.get("supScriptText", {}).get("textValue", "ppm")
        tds_badge = big_metric.get("badge", {}).get("text", "")

        # Parse Filter Life
        filter_card = ds.get("filterDetailsCard", {})
        filter_heading = "OK"
        filter_days_left = None
        for item in filter_card.get("items", []):
            if item.get("type") == "heading":
                text_items = item.get("data", {}).get("adsTextStack", {}).get("items", [])
                if text_items:
                    filter_heading = text_items[0].get("data", {}).get("text", "")
            elif item.get("type") == "tileBlock":
                for tile in item.get("data", {}).get("items", []):
                    desc = tile.get("mediaContent", {}).get("props", {}).get("description", {}).get("textValue")
                    if desc:
                        filter_days_left = desc

        # Parse Warranty
        warranty_card = ds.get("warrantyCard", {})
        warranty_status = "Active"
        for item in warranty_card.get("items", []):
            if item.get("id") == "headingBlock":
                tag_list = item.get("data", {}).get("adsTextStack", {}).get("items", [{}])[0].get("data", {}).get("tags", [])
                if tag_list:
                    warranty_status = tag_list[0].get("text", "Unknown")

        return {
            "device_name": device_name,
            "status": status,
            "tds": int(tds_val) if tds_val.isdigit() else tds_val,
            "tds_unit": tds_unit,
            "tds_health": tds_badge,
            "filter_heading": filter_heading,
            "filter_life_left": filter_days_left,
            "warranty_status": warranty_status
        }

    def get_water_consumption(self, timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetches water consumption history and daily breakdown.
        """
        url = "https://www.urbanclap.com/api/v2/supply/appliances/getWaterConsumptionData"
        
        if timestamp_ms is None:
            now = datetime.datetime.now(datetime.timezone.utc)
            days_ahead = (6 - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target = (now + datetime.timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
            timestamp_ms = int(target.timestamp() * 1000)

        payload = {
            "city_key": None,
            "applianceId": self.appliance_id,
            "timeStampOfLastDayInWeek": timestamp_ms
        }
        res = self._post(url, payload)

        if res.get("isError") or not res.get("success"):
            raise RuntimeError(f"API Error: {res}")

        data = res["success"]["data"]["historicWaterConsumptionData"]
        current_week = data[0] if data else {}
        daily = []
        for day in current_week.get("dailyData", []):
            if day.get("value") is not None:
                daily.append({
                    "date": day.get("dateText"),
                    "litres": day.get("value")
                })

        return {
            "date_range": current_week.get("dateRangeText"),
            "daily_average_litres": current_week.get("average"),
            "consumption": daily
        }
