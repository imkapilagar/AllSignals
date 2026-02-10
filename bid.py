#!/usr/bin/env python3
"""
BID Signal - Compare previous day 3:30 PM LTP with next day 9:15 AM Open
Usage: python3 bid.py
"""

import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote


# ANSI Color Codes
class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    BLUE = '\033[34m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


INSTRUMENTS = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "BANK NIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX"
}


def load_access_token():
    """Load access token from config"""
    config_paths = ['config.json', '../YoutubeData/config.json']
    for path in config_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                config = json.load(f)
                return config.get("access_token")
    return os.getenv("UPSTOX_ACCESS_TOKEN")


def get_trading_days() -> tuple:
    """Get previous trading day and today (for BID comparison)"""
    today = datetime.now()

    # If before market open, shift both days back
    if today.hour < 9 or (today.hour == 9 and today.minute < 15):
        today = today - timedelta(days=1)

    # Skip weekends for today
    while today.weekday() >= 5:
        today = today - timedelta(days=1)

    # Previous trading day
    prev_day = today - timedelta(days=1)
    while prev_day.weekday() >= 5:
        prev_day = prev_day - timedelta(days=1)

    return prev_day.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def get_330_ltp(access_token: str, instrument_key: str, date: str) -> float:
    """Get 3:30 PM LTP for a given date"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    encoded_key = quote(instrument_key, safe='')
    url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/1minute/{date}/{date}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data and 'data' in data and 'candles' in data['data']:
            candles = data['data']['candles']
            best_candle = None
            best_time = None

            for candle in candles:
                try:
                    dt = datetime.fromisoformat(candle[0].replace('+05:30', ''))
                    hour, minute = dt.hour, dt.minute

                    if hour == 15 and minute <= 29:
                        if best_time is None or (hour, minute) > best_time:
                            best_time = (hour, minute)
                            best_candle = candle
                    elif hour < 15:
                        if best_time is None or (hour, minute) > best_time:
                            best_time = (hour, minute)
                            best_candle = candle
                except:
                    continue

            if best_candle:
                return best_candle[4]
    except:
        pass
    return None


def get_915_open(access_token: str, instrument_key: str, date: str) -> float:
    """Get 9:15 AM Open for a given date"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    encoded_key = quote(instrument_key, safe='')
    url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/1minute/{date}/{date}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data and 'data' in data and 'candles' in data['data']:
            for candle in data['data']['candles']:
                try:
                    dt = datetime.fromisoformat(candle[0].replace('+05:30', ''))
                    if dt.hour == 9 and dt.minute == 15:
                        return candle[1]  # Open price
                except:
                    continue
    except:
        pass
    return None


def get_bid_data(access_token: str, instrument_key: str, prev_day: str, today: str) -> dict:
    """Get 3:30 PM LTP from previous day and 9:15 AM Open from today"""
    return {
        "ltp_330": get_330_ltp(access_token, instrument_key, prev_day),
        "open_915": get_915_open(access_token, instrument_key, today)
    }


def main():
    C = Colors

    print()
    print(f"{C.CYAN}{C.BOLD}  BID Signal{C.RESET}")
    print()

    access_token = load_access_token()
    if not access_token:
        print(f"{C.RED}ERROR: No access token found!{C.RESET}")
        print(f"{C.YELLOW}Set UPSTOX_ACCESS_TOKEN or create config.json{C.RESET}")
        return

    prev_day, today = get_trading_days()
    print(f"{C.DIM}  {prev_day} 3:30 PM  →  {today} 9:15 AM{C.RESET}")
    print()

    for name, instrument_key in INSTRUMENTS.items():
        data = get_bid_data(access_token, instrument_key, prev_day, today)
        ltp_330 = data["ltp_330"]
        open_915 = data["open_915"]

        print(f"{C.CYAN}{C.BOLD}  {name}{C.RESET}")
        print(f"{C.DIM}  {'─' * 50}{C.RESET}")

        if ltp_330 and open_915:
            # Gap from 3:30 PM to 9:15 AM (how much market moved overnight)
            gap = round(open_915 - ltp_330, 2)
            gap_pct = round((gap / ltp_330) * 100, 2)

            if gap > 0:
                direction = "Gap Up"
                color = C.GREEN
                arrow = "▲"
            elif gap < 0:
                direction = "Gap Down"
                color = C.RED
                arrow = "▼"
            else:
                direction = "Flat"
                color = C.YELLOW
                arrow = "─"

            print(f"  {C.YELLOW}{'3:30 LTP:':<12}{C.RESET} {ltp_330:,.2f}")
            print(f"  {C.YELLOW}{'9:15 Open:':<12}{C.RESET} {open_915:,.2f}")
            gap_str = f"{gap:+,.2f} ({gap_pct:+.2f}%)"
            print(f"  {C.YELLOW}{'Gap:':<12}{C.RESET} {color}{gap_str}{C.RESET}")
            print(f"  {C.YELLOW}{'Direction:':<12}{C.RESET} {color}{arrow} {direction}{C.RESET}")
        else:
            ltp_str = f"{ltp_330:,.2f}" if ltp_330 else "N/A"
            open_str = f"{open_915:,.2f}" if open_915 else "N/A"
            print(f"  {C.YELLOW}{'3:30 LTP:':<12}{C.RESET} {ltp_str}")
            print(f"  {C.YELLOW}{'9:15 Open:':<12}{C.RESET} {open_str}")
            print(f"  {C.YELLOW}{'Gap:':<12}{C.RESET} N/A")
            print(f"  {C.YELLOW}{'Direction:':<12}{C.RESET} {C.DIM}─ No Data{C.RESET}")

        print(f"{C.DIM}  {'─' * 50}{C.RESET}")
        print()


if __name__ == "__main__":
    main()
