#!/usr/bin/env python3
"""
Fetch comprehensive list of US stock tickers from various sources
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import yfinance as yf

def get_sp500_from_wikipedia():
    """Fetch current S&P 500 list from Wikipedia"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the table
        table = soup.find('table', {'id': 'constituents'})
        if not table:
            # Try alternative selector
            table = soup.find('table', {'class': 'wikitable'})

        if table:
            # Read the table into a DataFrame
            df = pd.read_html(str(table))[0]
            # Get the Symbol column
            if 'Symbol' in df.columns:
                tickers = df['Symbol'].tolist()
                # Clean up tickers
                tickers = [str(t).replace('.', '-') for t in tickers]  # Handle BRK.B -> BRK-B
                print(f"Found {len(tickers)} S&P 500 stocks from Wikipedia")
                return tickers
            else:
                print("Symbol column not found in Wikipedia table")
                return []
        else:
            print("Could not find S&P 500 table on Wikipedia")
            return []
    except Exception as e:
        print(f"Error fetching from Wikipedia: {e}")
        return []

def get_nasdaq100_tickers():
    """Fetch NASDAQ-100 tickers"""
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the table - it's usually the 3rd or 4th table
        tables = soup.find_all('table', {'class': 'wikitable'})

        for table in tables:
            df = pd.read_html(str(table))[0]
            # Look for a table with Ticker or Symbol column
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].tolist()
                print(f"Found {len(tickers)} NASDAQ-100 stocks")
                return [str(t) for t in tickers]
            elif 'Symbol' in df.columns:
                tickers = df['Symbol'].tolist()
                print(f"Found {len(tickers)} NASDAQ-100 stocks")
                return [str(t) for t in tickers]

        print("Could not find NASDAQ-100 ticker table")
        return []
    except Exception as e:
        print(f"Error fetching NASDAQ-100: {e}")
        return []

def get_popular_stocks():
    """Get a list of popular/highly traded stocks"""
    # Most actively traded stocks and popular growth stocks
    popular = [
        # Mega caps
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
        'JPM', 'JNJ', 'V', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'BAC', 'XOM',

        # Popular tech
        'AMD', 'INTC', 'CRM', 'ORCL', 'CSCO', 'ADBE', 'AVGO', 'QCOM', 'TXN',
        'NOW', 'UBER', 'SQ', 'SHOP', 'SNAP', 'PINS', 'TWTR', 'ROKU', 'ZM',
        'DOCU', 'CRWD', 'NET', 'DDOG', 'SNOW', 'PLTR', 'U', 'RBLX', 'COIN',
        'HOOD', 'SOFI', 'UPST', 'AFRM',

        # EV & Clean Energy
        'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'F', 'GM', 'PLUG', 'FCEL',
        'ENPH', 'SEDG', 'RUN', 'NEE', 'ICLN', 'TAN', 'QCLN',

        # Biotech & Healthcare
        'MRNA', 'BNTX', 'PFE', 'ABBV', 'LLY', 'MRK', 'TMO', 'ABT', 'DHR',
        'AMGN', 'GILD', 'REGN', 'VRTX', 'BIIB', 'ILMN',

        # Finance
        'GS', 'MS', 'C', 'WFC', 'SCHW', 'BLK', 'SPGI', 'ICE', 'CME', 'COF',
        'AXP', 'USB', 'PNC', 'TFC', 'PYPL', 'SQ', 'V', 'MA',

        # Retail & Consumer
        'WMT', 'TGT', 'COST', 'CVS', 'WBA', 'KR', 'LOW', 'NKE', 'SBUX',
        'MCD', 'CMG', 'DPZ', 'YUM', 'QSR', 'LULU', 'DECK', 'ULTA', 'TJX',

        # Airlines & Travel
        'DAL', 'UAL', 'AAL', 'LUV', 'BA', 'BKNG', 'EXPE', 'ABNB', 'MAR',
        'HLT', 'CCL', 'RCL', 'NCLH',

        # Streaming & Entertainment
        'NFLX', 'DIS', 'ROKU', 'SPOT', 'WBD', 'PARA', 'CMCSA', 'T', 'VZ',

        # Real Estate
        'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'O', 'WELL', 'SPG', 'AVB',

        # Gaming & Gambling
        'DKNG', 'PENN', 'MGM', 'LVS', 'WYNN', 'CZR',

        # Cannabis
        'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL',

        # SPACs and Recent IPOs
        'GRAB', 'NU', 'RIVN', 'PATH', 'GTLB', 'DOCS', 'TOST'
    ]

    # Remove duplicates and return
    return list(set(popular))

def get_russell_1000_sample():
    """Get a sample of Russell 1000 stocks (top mid and large caps)"""
    # This is a representative sample, not the full list
    russell_sample = [
        # Additional large caps
        'CVX', 'PEP', 'KO', 'MO', 'PM', 'MDT', 'HON', 'UNP', 'CAT', 'MMM',
        'IBM', 'GE', 'RTX', 'LMT', 'NOC', 'GD', 'BA', 'DE', 'EMR', 'ETN',

        # Mid caps
        'PANW', 'MRVL', 'FTNT', 'OKTA', 'ZS', 'VEEV', 'WDAY', 'TEAM', 'HUBS',
        'TTD', 'BILL', 'GTLB', 'MDB', 'ESTC', 'CFLT', 'S', 'IOT', 'PCOR',

        # Industrials & Materials
        'MMM', 'APD', 'ECL', 'SHW', 'DD', 'PPG', 'LIN', 'FCX', 'NEM', 'NUE',

        # Energy
        'SLB', 'HAL', 'BKR', 'EOG', 'COP', 'MPC', 'PSX', 'VLO', 'DVN', 'OXY',

        # Consumer brands
        'CL', 'KMB', 'K', 'GIS', 'CPB', 'CAG', 'HSY', 'MDLZ', 'STZ', 'TAP',

        # More healthcare
        'HCA', 'ISRG', 'BSX', 'SYK', 'ZTS', 'IDXX', 'DXCM', 'MTD', 'ALGN',

        # REITs
        'DLR', 'SBAC', 'WY', 'EQR', 'VTR', 'PEAK', 'MAA', 'ARE', 'INVH'
    ]

    return russell_sample

def combine_all_tickers():
    """Combine all ticker sources and remove duplicates"""
    all_tickers = []

    # Get S&P 500
    sp500 = get_sp500_from_wikipedia()
    all_tickers.extend(sp500)

    # Get NASDAQ-100
    nasdaq100 = get_nasdaq100_tickers()
    all_tickers.extend(nasdaq100)

    # Get popular stocks
    popular = get_popular_stocks()
    all_tickers.extend(popular)

    # Get Russell 1000 sample
    russell = get_russell_1000_sample()
    all_tickers.extend(russell)

    # Remove duplicates and clean
    all_tickers = list(set(all_tickers))

    # Remove any empty strings or None values
    all_tickers = [t for t in all_tickers if t and str(t).strip()]

    # Sort alphabetically
    all_tickers.sort()

    print(f"\nTotal unique tickers collected: {len(all_tickers)}")

    return all_tickers

if __name__ == "__main__":
    print("Fetching comprehensive ticker list...")
    print("=" * 50)

    tickers = combine_all_tickers()

    print(f"\nFinal ticker count: {len(tickers)}")
    print(f"Sample tickers: {tickers[:10]}")

    # Save to file
    with open('expanded_tickers.txt', 'w') as f:
        for ticker in tickers:
            f.write(f"{ticker}\n")

    print(f"\nTickers saved to expanded_tickers.txt")