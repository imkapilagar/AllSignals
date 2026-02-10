#!/usr/bin/env python3
"""
Combined BID + PriceGap + SixthSense Signal
- Auto-detects nearest expiry (Nifty or Sensex)
- Shows BID signal: Previous day 3:30 PM LTP vs Today 9:15 AM Open
- Shows PriceGap signal: 3:30 PM LTP vs Daily Close
- Shows SixthSense: Last 5 trading days Open, Close, Change%
Usage: python3 signal.py
"""

import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote
import yfinance as yf
import pandas as pd


class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    BLUE = '\033[34m'
    WHITE = '\033[97m'
    MAGENTA = '\033[35m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


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
    """Get expiry dates for an instrument using /v2/option/contract"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}

    # Map instrument to API parameters
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
            expiry_dates = sorted(set(item['expiry'] for item in data['data'] if 'expiry' in item))
            return expiry_dates
    except Exception as e:
        print(f"  {Colors.RED}Error fetching expiry: {e}{Colors.RESET}")
    return []


def calculate_dte(expiry_date: str, today: datetime) -> int:
    """Calculate days to expiry"""
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        return (expiry - today).days
    except:
        return 999


def get_nearest_expiry_instrument(access_token: str) -> tuple:
    """
    Determine which instrument to trade based on nearest expiry
    Returns: (instrument_name, expiry_date, dte)

    Logic:
    - Nifty: Trade on 0, 1, 2 DTE (typically Mon, Tue, Wed before Thu expiry)
    - Sensex: Trade on 0, 1 DTE (typically Wed, Thu before Fri expiry)
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    nifty_expiries = get_expiry_dates(access_token, "NIFTY")
    sensex_expiries = get_expiry_dates(access_token, "SENSEX")

    # Find nearest expiry for each
    nifty_dte = 999
    nifty_expiry = None
    for exp in nifty_expiries:
        dte = calculate_dte(exp, today)
        if 0 <= dte <= 2:  # Nifty: 0, 1, 2 DTE
            nifty_dte = dte
            nifty_expiry = exp
            break

    sensex_dte = 999
    sensex_expiry = None
    for exp in sensex_expiries:
        dte = calculate_dte(exp, today)
        if 0 <= dte <= 1:  # Sensex: 0, 1 DTE
            sensex_dte = dte
            sensex_expiry = exp
            break

    # Determine which to trade
    # Priority: Lower DTE wins, if same DTE prefer Nifty
    if nifty_dte <= sensex_dte and nifty_expiry:
        return "NIFTY", nifty_expiry, nifty_dte
    elif sensex_expiry:
        return "SENSEX", sensex_expiry, sensex_dte
    elif nifty_expiry:
        return "NIFTY", nifty_expiry, nifty_dte
    else:
        return None, None, None


def get_trading_days_bid() -> tuple:
    """
    Get trading days for BID signal (3:30 PM prev → 9:15 AM today)
    Returns: (prev_day, today, is_market_open)
    """
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Skip weekends
    while today.weekday() >= 5:
        today = today - timedelta(days=1)

    # Check if market is open (after 9:15 AM on a trading day)
    is_today_trading_day = now.date() == today.date()
    is_after_market_open = now.hour > 9 or (now.hour == 9 and now.minute >= 15)
    is_market_open = is_today_trading_day and is_after_market_open

    # If market not open yet, shift to previous trading day
    if not is_market_open:
        today = today - timedelta(days=1)
        while today.weekday() >= 5:
            today = today - timedelta(days=1)

    # Previous trading day (for 3:30 PM LTP)
    prev_day = today - timedelta(days=1)
    while prev_day.weekday() >= 5:
        prev_day = prev_day - timedelta(days=1)

    return prev_day.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), is_market_open


def get_trading_days_pricegap() -> tuple:
    """
    Get trading day for PriceGap signal (3:30 PM LTP vs Daily Close)
    Returns: (date, is_after_close)
    Only valid after 3:30 PM when both values are available
    """
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Skip weekends
    while today.weekday() >= 5:
        today = today - timedelta(days=1)

    # Check if after market close (3:30 PM)
    is_today_trading_day = now.date() == today.date()
    is_after_close = now.hour > 15 or (now.hour == 15 and now.minute >= 30)
    is_data_available = is_today_trading_day and is_after_close

    # If today's data not available, use previous trading day
    if not is_data_available:
        # Use previous completed trading day
        if is_today_trading_day:
            today = today - timedelta(days=1)
        while today.weekday() >= 5:
            today = today - timedelta(days=1)

    return today.strftime("%Y-%m-%d"), is_data_available


def get_330_ltp(access_token: str, instrument_key: str, date: str) -> float:
    """Get 3:30 PM LTP for a given date"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    encoded_key = quote(instrument_key, safe='')

    # Use intraday endpoint for today, historical for past dates
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
            best_candle = None
            best_time = None

            for candle in candles:
                try:
                    dt = datetime.fromisoformat(candle[0].replace('+05:30', ''))
                    hour, minute = dt.hour, dt.minute

                    # Look for 15:29 candle (3:30 PM LTP is the close of 15:29 candle)
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
                return best_candle[4]  # Close price of the candle
    except:
        pass
    return None


def get_915_open(access_token: str, instrument_key: str, date: str) -> float:
    """Get 9:15 AM Open for a given date"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    encoded_key = quote(instrument_key, safe='')

    # Use intraday endpoint for today, historical for past dates
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
                        return candle[1]  # Open price
                except:
                    continue
    except:
        pass
    return None


def get_daily_close(access_token: str, instrument_key: str, date: str) -> float:
    """Get daily close from Yahoo Finance"""
    # Map instrument key to Yahoo Finance ticker
    yahoo_tickers = {
        "NSE_INDEX|Nifty 50": "^NSEI",
        "BSE_INDEX|SENSEX": "^BSESN"
    }

    ticker_symbol = yahoo_tickers.get(instrument_key)
    if not ticker_symbol:
        return None

    try:
        ticker = yf.Ticker(ticker_symbol)
        # Get today's data
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except Exception as e:
        pass
    return None


def format_gap(gap: float, base: float) -> tuple:
    """Format gap with color and direction"""
    C = Colors
    gap_pct = round((gap / base) * 100, 2) if base else 0

    if gap > 0:
        color = C.GREEN
        arrow = "▲"
        direction = "Up"
    elif gap < 0:
        color = C.RED
        arrow = "▼"
        direction = "Down"
    else:
        color = C.YELLOW
        arrow = "─"
        direction = "Flat"

    return color, arrow, direction, f"{gap:+,.2f} ({gap_pct:+.2f}%)"


def get_sixth_sense_data(instrument: str, days: int = 5) -> pd.DataFrame:
    """
    Fetch last N trading days data for SixthSense signal
    Returns DataFrame with Date, Open, Close, Change_%
    """
    yahoo_tickers = {
        "NIFTY": "^NSEI",
        "SENSEX": "^BSESN"
    }

    ticker_symbol = yahoo_tickers.get(instrument)
    if not ticker_symbol:
        return None

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)

        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(start=start_date, end=end_date).tail(days)

        if df.empty:
            return None

        result = pd.DataFrame({
            'Date': df.index.strftime('%Y-%m-%d'),
            'Open': df['Open'].round(2),
            'Close': df['Close'].round(2),
            'Change_%': ((df['Close'] - df['Open']) / df['Open'] * 100).round(2)
        })

        return result
    except Exception:
        return None


def print_sixth_sense_table(instrument: str, df: pd.DataFrame):
    """Print SixthSense data as a formatted table (with header)"""
    C = Colors

    print(f"{C.BLUE}{C.BOLD}  SixthSense{C.RESET} {C.DIM}(Last 5 Days){C.RESET}")
    print(f"{C.DIM}  {'─' * 50}{C.RESET}")
    print_sixth_sense_table_content(instrument, df)


def print_sixth_sense_table_content(instrument: str, df: pd.DataFrame):
    """Print SixthSense data table content only (without header)"""
    C = Colors

    if df is None or df.empty:
        print(f"  {C.DIM}Data not available{C.RESET}")
        return

    # Header
    print(f"  {C.DIM}{'Date':<12}{'Open':>12}{'Close':>12}{'Change':>12}{C.RESET}")
    print(f"  {C.DIM}{'─' * 48}{C.RESET}")

    # Data rows
    for _, row in df.iterrows():
        change = row['Change_%']
        if change > 0:
            change_color = C.GREEN
            change_str = f"+{change:.2f}%"
        elif change < 0:
            change_color = C.RED
            change_str = f"{change:.2f}%"
        else:
            change_color = C.YELLOW
            change_str = f"{change:.2f}%"

        # Bold if change > 0.5% or < -0.5%
        bold = C.BOLD if abs(change) > 0.5 else ""

        print(f"  {row['Date']:<12}{row['Open']:>12,.2f}{row['Close']:>12,.2f}{bold}{change_color}{change_str:>12}{C.RESET}")


# Premium percentages by DTE
PREMIUM_PCT = {
    0: 0.54,
    1: 0.81,
    2: 1.05,
    3: 1.20,
    4: 1.38
}


def get_spot_price_nse(instrument: str) -> float:
    """Fetch current spot price from NSE/BSE"""
    try:
        if instrument == "NIFTY":
            url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    return data['data'][0].get('lastPrice', None)
    except Exception:
        pass

    # Fallback to Yahoo Finance
    try:
        yahoo_tickers = {"NIFTY": "^NSEI", "SENSEX": "^BSESN"}
        ticker = yf.Ticker(yahoo_tickers.get(instrument, "^NSEI"))
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except Exception:
        pass

    return None


def get_spot_price_bse(instrument: str) -> float:
    """Fetch Sensex spot price"""
    try:
        ticker = yf.Ticker("^BSESN")
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except Exception:
        pass
    return None


def get_next_trading_day() -> datetime:
    """Get the next trading day (tomorrow, skipping weekends)"""
    now = datetime.now()
    next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Skip weekends
    while next_day.weekday() >= 5:
        next_day = next_day + timedelta(days=1)

    return next_day


def get_dte_for_instrument_tomorrow(access_token: str, instrument: str) -> tuple:
    """Get DTE for an instrument as of next trading day (for coverage premium)"""
    next_trading_day = get_next_trading_day()
    expiries = get_expiry_dates(access_token, instrument)

    for exp in expiries:
        dte = calculate_dte(exp, next_trading_day)
        if dte >= 0:
            return dte, exp, next_trading_day.strftime("%Y-%m-%d")

    return None, None, None


def print_coverage_premium(access_token: str):
    """Print coverage premium for both Nifty and Sensex based on tomorrow's DTEs (with header)"""
    C = Colors

    next_day = get_next_trading_day()
    print(f"{C.WHITE}{C.BOLD}  Coverage Premium{C.RESET} {C.DIM}(for {next_day.strftime('%a %d %b')}){C.RESET}")
    print(f"{C.DIM}  {'─' * 50}{C.RESET}")
    print_coverage_premium_content(access_token)


def print_coverage_premium_content(access_token: str):
    """Print coverage premium content only (without header)"""
    C = Colors
    next_day = get_next_trading_day()

    # Header
    print(f"  {C.DIM}{'Index':<10}{'DTE':>6}{'Spot':>14}{'Pct':>8}{'Premium':>12}{C.RESET}")
    print(f"  {C.DIM}{'─' * 48}{C.RESET}")

    for instrument in ["NIFTY", "SENSEX"]:
        dte, expiry, trading_date = get_dte_for_instrument_tomorrow(access_token, instrument)

        if dte is None:
            print(f"  {instrument:<10}{C.DIM}No valid expiry{C.RESET}")
            continue

        # Get spot price
        if instrument == "NIFTY":
            spot = get_spot_price_nse(instrument)
        else:
            spot = get_spot_price_bse(instrument)

        if spot is None:
            print(f"  {instrument:<10}{dte:>6}{C.DIM}  Spot unavailable{C.RESET}")
            continue

        # Calculate premium
        pct = PREMIUM_PCT.get(dte, 0.54)
        premium = round(spot * pct / 100, 2)

        print(f"  {C.CYAN}{instrument:<10}{C.RESET}{dte:>6}{spot:>14,.2f}{pct:>7.2f}%{C.GREEN}{premium:>12,.2f}{C.RESET}")


def print_coverage_premium_section(access_token: str):
    """Print coverage premium as a distinct section with header"""
    C = Colors
    next_day = get_next_trading_day()
    print_section_header("COVERAGE PREMIUM", f"(for {next_day.strftime('%a %d %b')})", 4)
    print_coverage_premium_content(access_token)


def print_section_header(title: str, subtitle: str = "", number: int = None):
    """Print a clearly demarcated section header"""
    C = Colors
    width = 56

    # Top border
    print(f"{C.DIM}  {'═' * width}{C.RESET}")

    # Section number and title
    if number:
        print(f"{C.BOLD}{C.WHITE}  [{number}] {title}{C.RESET}", end="")
    else:
        print(f"{C.BOLD}{C.WHITE}  {title}{C.RESET}", end="")

    if subtitle:
        print(f" {C.DIM}{subtitle}{C.RESET}")
    else:
        print()

    # Bottom border
    print(f"{C.DIM}  {'─' * width}{C.RESET}")


def print_section_footer():
    """Print section footer for clear demarcation"""
    C = Colors
    print()


def main():
    C = Colors
    now = datetime.now()

    print()
    print(f"{C.CYAN}{C.BOLD}  ╔{'═' * 54}╗{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  ║{'TRADING SIGNALS':^54}║{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  ╚{'═' * 54}╝{C.RESET}")
    print(f"{C.DIM}  {now.strftime('%A, %d %b %Y %I:%M %p')}{C.RESET}")
    print()

    access_token = load_access_token()
    if not access_token:
        print(f"{C.RED}ERROR: No access token found!{C.RESET}")
        return

    # Determine which instrument to trade based on expiry
    instrument, expiry_date, dte = get_nearest_expiry_instrument(access_token)

    if not instrument:
        print(f"{C.YELLOW}No valid expiry found for trading today{C.RESET}")
        return

    instrument_info = INSTRUMENTS[instrument]
    index_key = instrument_info["index_key"]

    # Get trading days for BID and PriceGap separately
    bid_prev_day, bid_today, is_market_open = get_trading_days_bid()
    pricegap_date, is_after_close = get_trading_days_pricegap()

    # Print header info
    # DTE shown is for tomorrow (trading day), not today
    trading_day_dte = max(0, dte - 1)
    print(f"{C.DIM}  Instrument:  {C.RESET}{C.BOLD}{instrument}{C.RESET}")
    print(f"{C.DIM}  Expiry:      {C.RESET}{expiry_date} ({trading_day_dte} DTE)")
    print()

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 1: BID Signal
    # ═══════════════════════════════════════════════════════════
    print_section_header("BID SIGNAL", "(Overnight Gap)", 1)
    print(f"{C.DIM}  {bid_prev_day} 3:30 PM → {bid_today} 9:15 AM{C.RESET}")
    print(f"{C.DIM}  {'─' * 50}{C.RESET}")

    ltp_330_prev = get_330_ltp(access_token, index_key, bid_prev_day)
    open_915_today = get_915_open(access_token, index_key, bid_today)

    if ltp_330_prev and open_915_today:
        bid_gap = round(open_915_today - ltp_330_prev, 2)
        color, arrow, direction, gap_str = format_gap(bid_gap, ltp_330_prev)

        print(f"  {C.YELLOW}{'3:30 LTP:':<14}{C.RESET} {ltp_330_prev:,.2f}")
        print(f"  {C.YELLOW}{'9:15 Open:':<14}{C.RESET} {open_915_today:,.2f}")
        print(f"  {C.YELLOW}{'Gap:':<14}{C.RESET} {color}{gap_str}{C.RESET}")
        print(f"  {C.YELLOW}{'Signal:':<14}{C.RESET} {color}{arrow} Gap {direction}{C.RESET}")
    else:
        if not is_market_open:
            print(f"  {C.DIM}Market not open yet{C.RESET}")
        else:
            print(f"  {C.DIM}Data not available{C.RESET}")

    print_section_footer()

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 2: PriceGap Signal
    # ═══════════════════════════════════════════════════════════
    print_section_header("PRICEGAP SIGNAL", "(3:30 LTP vs Close)", 2)
    print(f"{C.DIM}  {pricegap_date}{C.RESET}")
    print(f"{C.DIM}  {'─' * 50}{C.RESET}")

    ltp_330 = get_330_ltp(access_token, index_key, pricegap_date)
    daily_close = get_daily_close(access_token, index_key, pricegap_date)

    if ltp_330 and daily_close:
        pricegap = round(ltp_330 - daily_close, 2)
        color, arrow, direction, gap_str = format_gap(pricegap, daily_close)

        print(f"  {C.YELLOW}{'3:30 LTP:':<14}{C.RESET} {ltp_330:,.2f}")
        print(f"  {C.YELLOW}{'Daily Close:':<14}{C.RESET} {daily_close:,.2f}")
        print(f"  {C.YELLOW}{'Gap:':<14}{C.RESET} {color}{gap_str}{C.RESET}")
        print(f"  {C.YELLOW}{'Signal:':<14}{C.RESET} {color}{arrow} LTP {'>' if pricegap > 0 else '<' if pricegap < 0 else '='} Close{C.RESET}")
    else:
        print(f"  {C.DIM}Data not available{C.RESET}")

    print_section_footer()

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 3: SixthSense Signal
    # ═══════════════════════════════════════════════════════════
    print_section_header("SIXTHSENSE SIGNAL", "(Last 5 Days)", 3)
    sixth_sense_data = get_sixth_sense_data(instrument, days=5)
    print_sixth_sense_table_content(instrument, sixth_sense_data)

    print_section_footer()

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 4: Coverage Premium
    # ═══════════════════════════════════════════════════════════
    print_coverage_premium_section(access_token)

    print()


if __name__ == "__main__":
    main()
