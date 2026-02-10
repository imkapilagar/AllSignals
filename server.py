#!/usr/bin/env python3
"""
Trading Signals Dashboard Server
Serves the dashboard with live data from Upstox API
Usage: python3 server.py
"""

import json
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote, urlparse, parse_qs
import requests
import yfinance as yf


# Configuration
PORT = 8080
INSTRUMENTS = {
    "NIFTY": {
        "index_key": "NSE_INDEX|Nifty 50",
        "option_asset": "NIFTY"
    },
    "SENSEX": {
        "index_key": "BSE_INDEX|SENSEX",
        "option_asset": "SENSEX"
    }
}

PREMIUM_PCT = {
    0: 0.54,
    1: 0.81,
    2: 1.05,
    3: 1.20,
    4: 1.38
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


def get_expiry_dates(access_token: str, instrument: str) -> list:
    """Get expiry dates for an instrument"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}

    if instrument == "NIFTY":
        url = "https://api.upstox.com/v2/option/contract?instrument_key=NSE_INDEX%7CNifty%2050"
    elif instrument == "SENSEX":
        url = "https://api.upstox.com/v2/option/contract?instrument_key=BSE_INDEX%7CSENSEX"
    else:
        return []

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data and 'data' in data:
            return sorted(set(item['expiry'] for item in data['data'] if 'expiry' in item))
    except:
        pass
    return []


def calculate_dte(expiry_date: str, today: datetime) -> int:
    """Calculate days to expiry"""
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        return (expiry - today).days
    except:
        return 999


def get_nearest_expiry_instrument(access_token: str) -> tuple:
    """Determine which instrument to trade based on nearest expiry"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    nifty_expiries = get_expiry_dates(access_token, "NIFTY")
    sensex_expiries = get_expiry_dates(access_token, "SENSEX")

    nifty_dte, nifty_expiry = 999, None
    for exp in nifty_expiries:
        dte = calculate_dte(exp, today)
        if 0 <= dte <= 2:
            nifty_dte, nifty_expiry = dte, exp
            break

    sensex_dte, sensex_expiry = 999, None
    for exp in sensex_expiries:
        dte = calculate_dte(exp, today)
        if 0 <= dte <= 1:
            sensex_dte, sensex_expiry = dte, exp
            break

    if nifty_dte <= sensex_dte and nifty_expiry:
        return "NIFTY", nifty_expiry, nifty_dte
    elif sensex_expiry:
        return "SENSEX", sensex_expiry, sensex_dte
    elif nifty_expiry:
        return "NIFTY", nifty_expiry, nifty_dte
    return None, None, None


def get_trading_days_bid() -> tuple:
    """Get trading days for BID signal"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    while today.weekday() >= 5:
        today = today - timedelta(days=1)

    is_today_trading_day = now.date() == today.date()
    is_after_market_open = now.hour > 9 or (now.hour == 9 and now.minute >= 15)
    is_market_open = is_today_trading_day and is_after_market_open

    if not is_market_open:
        today = today - timedelta(days=1)
        while today.weekday() >= 5:
            today = today - timedelta(days=1)

    prev_day = today - timedelta(days=1)
    while prev_day.weekday() >= 5:
        prev_day = prev_day - timedelta(days=1)

    return prev_day.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), is_market_open


def get_trading_days_pricegap() -> tuple:
    """Get trading day for PriceGap signal"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    while today.weekday() >= 5:
        today = today - timedelta(days=1)

    is_today_trading_day = now.date() == today.date()
    is_after_close = now.hour > 15 or (now.hour == 15 and now.minute >= 30)
    is_data_available = is_today_trading_day and is_after_close

    if not is_data_available:
        if is_today_trading_day:
            today = today - timedelta(days=1)
        while today.weekday() >= 5:
            today = today - timedelta(days=1)

    return today.strftime("%Y-%m-%d"), is_data_available


def get_330_ltp(access_token: str, instrument_key: str, date: str) -> float:
    """Get 3:30 PM LTP for a given date"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    encoded_key = quote(instrument_key, safe='')

    today = datetime.now().strftime("%Y-%m-%d")
    if date == today:
        url = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_key}/1minute"
    else:
        url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/1minute/{date}/{date}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data and 'data' in data and 'candles' in data['data']:
            candles = data['data']['candles']
            best_candle, best_time = None, None

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

    today = datetime.now().strftime("%Y-%m-%d")
    if date == today:
        url = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_key}/1minute"
    else:
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
                        return candle[1]
                except:
                    continue
    except:
        pass
    return None


def get_daily_close(instrument_key: str) -> float:
    """Get daily close from Yahoo Finance"""
    yahoo_tickers = {
        "NSE_INDEX|Nifty 50": "^NSEI",
        "BSE_INDEX|SENSEX": "^BSESN"
    }
    ticker_symbol = yahoo_tickers.get(instrument_key)
    if not ticker_symbol:
        return None

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except:
        pass
    return None


def get_sixth_sense_data(instrument: str, days: int = 5) -> list:
    """Fetch last N trading days data for SixthSense signal"""
    yahoo_tickers = {"NIFTY": "^NSEI", "SENSEX": "^BSESN"}
    ticker_symbol = yahoo_tickers.get(instrument)
    if not ticker_symbol:
        return []

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)

        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(start=start_date, end=end_date).tail(days)

        if df.empty:
            return []

        result = []
        for idx, row in df.iterrows():
            change_pct = round((row['Close'] - row['Open']) / row['Open'] * 100, 2)
            result.append({
                'date': idx.strftime('%Y-%m-%d'),
                'open': round(row['Open'], 2),
                'close': round(row['Close'], 2),
                'change': change_pct
            })
        return result
    except:
        return []


def get_spot_price(instrument: str) -> float:
    """Get current spot price"""
    yahoo_tickers = {"NIFTY": "^NSEI", "SENSEX": "^BSESN"}
    try:
        ticker = yf.Ticker(yahoo_tickers.get(instrument, "^NSEI"))
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except:
        pass
    return None


def get_next_trading_day() -> datetime:
    """Get the next trading day"""
    now = datetime.now()
    next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day = next_day + timedelta(days=1)
    return next_day


def get_dte_for_instrument_tomorrow(access_token: str, instrument: str) -> tuple:
    """Get DTE for an instrument as of next trading day"""
    next_trading_day = get_next_trading_day()
    expiries = get_expiry_dates(access_token, instrument)

    for exp in expiries:
        dte = calculate_dte(exp, next_trading_day)
        if dte >= 0:
            return dte, exp, next_trading_day.strftime("%Y-%m-%d")
    return None, None, None


def get_all_signal_data():
    """Get all signal data as JSON"""
    access_token = load_access_token()
    if not access_token:
        return {"error": "No access token found"}

    instrument, expiry_date, dte = get_nearest_expiry_instrument(access_token)
    if not instrument:
        return {"error": "No valid expiry found"}

    index_key = INSTRUMENTS[instrument]["index_key"]

    # BID Signal
    bid_prev_day, bid_today, is_market_open = get_trading_days_bid()
    ltp_330_prev = get_330_ltp(access_token, index_key, bid_prev_day)
    open_915_today = get_915_open(access_token, index_key, bid_today)

    bid_data = {
        "ltp_330": ltp_330_prev,
        "open_915": open_915_today,
        "gap": None,
        "gap_pct": None,
        "direction": None,
        "prev_date": bid_prev_day,
        "today_date": bid_today,
        "market_open": is_market_open
    }

    if ltp_330_prev and open_915_today:
        gap = round(open_915_today - ltp_330_prev, 2)
        gap_pct = round((gap / ltp_330_prev) * 100, 2)
        bid_data["gap"] = gap
        bid_data["gap_pct"] = gap_pct
        bid_data["direction"] = "up" if gap > 0 else "down" if gap < 0 else "flat"

    # PriceGap Signal
    pricegap_date, is_after_close = get_trading_days_pricegap()
    ltp_330 = get_330_ltp(access_token, index_key, pricegap_date)
    daily_close = get_daily_close(index_key)

    pricegap_data = {
        "ltp_330": ltp_330,
        "daily_close": daily_close,
        "gap": None,
        "gap_pct": None,
        "direction": None,
        "date": pricegap_date
    }

    if ltp_330 and daily_close:
        gap = round(ltp_330 - daily_close, 2)
        gap_pct = round((gap / daily_close) * 100, 2)
        pricegap_data["gap"] = gap
        pricegap_data["gap_pct"] = gap_pct
        pricegap_data["direction"] = "up" if gap > 0 else "down" if gap < 0 else "flat"

    # SixthSense Signal
    sixth_sense_data = get_sixth_sense_data(instrument, days=5)

    # Coverage Premium
    next_day = get_next_trading_day()
    coverage_data = {
        "date": next_day.strftime("%a %d %b"),
        "instruments": []
    }

    for inst in ["NIFTY", "SENSEX"]:
        inst_dte, expiry, _ = get_dte_for_instrument_tomorrow(access_token, inst)
        spot = get_spot_price(inst)

        if inst_dte is not None and spot:
            pct = PREMIUM_PCT.get(inst_dte, 0.54)
            premium = round(spot * pct / 100, 2)
            coverage_data["instruments"].append({
                "name": inst,
                "dte": inst_dte,
                "spot": spot,
                "pct": pct,
                "premium": premium
            })

    # DTE shown is for tomorrow (trading day), not today
    trading_day_dte = max(0, dte - 1)

    return {
        "instrument": instrument,
        "expiry_date": expiry_date,
        "dte": trading_day_dte,
        "timestamp": datetime.now().isoformat(),
        "bid": bid_data,
        "pricegap": pricegap_data,
        "sixthsense": sixth_sense_data,
        "coverage": coverage_data
    }


class SignalHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving dashboard and API"""

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/signals':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            data = get_all_signal_data()
            self.wfile.write(json.dumps(data, indent=2).encode())

        elif parsed.path == '/' or parsed.path == '/index.html':
            self.path = '/dashboard.html'
            return SimpleHTTPRequestHandler.do_GET(self)

        else:
            return SimpleHTTPRequestHandler.do_GET(self)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    server = HTTPServer(('localhost', PORT), SignalHandler)
    print(f"\n  🚀 Trading Signals Dashboard")
    print(f"  ────────────────────────────")
    print(f"  Dashboard: http://localhost:{PORT}")
    print(f"  API:       http://localhost:{PORT}/api/signals")
    print(f"\n  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
