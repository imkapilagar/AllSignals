# Trading Signals Dashboard

A professional trading signals dashboard for Indian stock markets (NSE/BSE) that displays 4 key strategies for options trading decisions.

![Dashboard Preview](https://img.shields.io/badge/Status-Live-brightgreen) ![Python](https://img.shields.io/badge/Python-3.8+-blue) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Strategies

| # | Strategy | Description |
|---|----------|-------------|
| 1 | **BID Signal** | Overnight gap analysis - compares previous day 3:30 PM LTP with today's 9:15 AM Open |
| 2 | **PriceGap Signal** | Compares 3:30 PM LTP with Daily Close to identify late-day price movements |
| 3 | **SixthSense** | Last 5 trading days Open, Close, and Change % for trend analysis |
| 4 | **Coverage Premium** | Calculates option premium coverage based on DTE (Days to Expiry) |

## Features

- **Auto-detects trading instrument** - Automatically selects NIFTY or SENSEX based on nearest expiry
- **Real-time data** - Fetches live data from Upstox API
- **Professional web dashboard** - Clean, screenshot-friendly interface
- **CLI support** - Run from terminal for quick checks
- **Color-coded signals** - Green for bullish, Red for bearish

## Installation

```bash
# Clone the repository
git clone https://github.com/imkapilagar/AllSignals.git
cd AllSignals

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `config.json` file with your Upstox API access token:

```json
{
  "access_token": "your_upstox_access_token_here"
}
```

> **Note:** Never commit your `config.json` file. It's already in `.gitignore`.

## Usage

### Web Dashboard

```bash
# Start the server
python3 server.py

# Open in browser
# http://localhost:8080
```

### CLI Mode

```bash
# Run all signals
python3 signal.py

# Run BID signal only
python3 bid.py
```

## Dashboard Preview

The dashboard displays all 4 strategies in a single-screen layout:

- **Dark theme** with professional aesthetics
- **Distinct color accents** for each strategy (Cyan, Purple, Yellow, Green)
- **Live updates** every 60 seconds
- **Hover effects** with card animations
- **Screenshot-friendly** design for sharing

## API Endpoint

The server exposes a JSON API:

```
GET /api/signals
```

Returns all signal data in JSON format for integration with other tools.

## Project Structure

```
AllSignals/
├── dashboard.html    # Web dashboard UI
├── server.py         # HTTP server with API
├── signal.py         # CLI tool (all strategies)
├── bid.py            # Standalone BID signal
├── requirements.txt  # Python dependencies
├── config.json       # API credentials (not tracked)
└── README.md
```

## Dependencies

- `requests` - HTTP requests to Upstox API
- `yfinance` - Yahoo Finance data for daily close prices
- `pandas` - Data manipulation

## Trading Logic

### Instrument Selection
- **NIFTY**: Trades on 0, 1, 2 DTE (Mon-Wed before Thursday expiry)
- **SENSEX**: Trades on 0, 1 DTE (Wed-Thu before Friday expiry)

### Premium Coverage by DTE
| DTE | Premium % |
|-----|-----------|
| 0 | 0.54% |
| 1 | 0.81% |
| 2 | 1.05% |
| 3 | 1.20% |
| 4 | 1.38% |

## License

MIT License - Feel free to use and modify for your trading needs.

## Disclaimer

This tool is for informational purposes only. Always do your own research before making trading decisions. Past performance does not guarantee future results.
