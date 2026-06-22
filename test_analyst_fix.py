#!/usr/bin/env python3
"""
Test if analyst buy percentage is fixed
"""

from data_fetcher import StockDataFetcher
import time

def test_analyst_fix():
    print("Testing Analyst Buy Percentage Fix")
    print("=" * 50)

    fetcher = StockDataFetcher(rate_limit_delay=0.2)
    test_tickers = ['AAPL', 'MSFT', 'NVDA']

    for ticker in test_tickers:
        print(f"\n{ticker}:")
        print("-" * 30)

        data = fetcher.fetch_stock_data(ticker)

        if data:
            print(f"  Company: {data.get('company_name', 'N/A')}")
            print(f"  Buy %: {data.get('analyst_buy_percent', 'N/A')}")
            print(f"  Hold %: {data.get('analyst_hold_percent', 'N/A')}")
            print(f"  Sell %: {data.get('analyst_sell_percent', 'N/A')}")
            print(f"  Recent Upgrades: {data.get('recent_upgrades', 0)}")
            print(f"  Recent Downgrades: {data.get('recent_downgrades', 0)}")
            print(f"  Number of Analysts: {data.get('number_of_analysts', 0)}")

            # Check if buy percentage is now populated
            if data.get('analyst_buy_percent') is not None:
                print(f"  ✅ Buy % is working!")
            else:
                print(f"  ❌ Buy % is still None")
        else:
            print(f"  Failed to fetch data")

        time.sleep(0.5)

    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_analyst_fix()