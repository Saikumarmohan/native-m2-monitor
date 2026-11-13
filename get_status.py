#!/usr/bin/env python3
"""
Native M2 CLI Status Monitor
"""
import sys
from native_m2 import NativeM2Client

def main():
    try:
        client = NativeM2Client()
        details = client.get_details()
        consumption = client.get_water_consumption()
    except FileNotFoundError as e:
        print(f"\n[CONFIG ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"\n[AUTH ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Failed to fetch data: {e}\n", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 52)
    print(f"  {details['device_name']} SMART WATER PURIFIER MONITOR")
    print("=" * 52)
    print(f"  Status          : {details['status']}")
    print(f"  Live Output TDS : {details['tds']} {details['tds_unit']} ({details['tds_health']})")
    print(f"  Filter Status   : {details['filter_heading']}")
    if details['filter_life_left']:
        print(f"  Filter Life     : {details['filter_life_left']}")
    print(f"  Warranty        : {details['warranty_status']}")
    print("-" * 52)
    print(f"  Water Usage ({consumption['date_range']}):")
    print(f"  Average Daily   : {consumption['daily_average_litres']} Litres / day")
    print("  Daily Breakdown :")
    for day in consumption['consumption']:
        bar = "#" * int(day['litres'])
        print(f"    {day['date']:<8} : {day['litres']:>2} L  {bar}")
    print("=" * 52 + "\n")

if __name__ == "__main__":
    main()
