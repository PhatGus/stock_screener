#!/usr/bin/env python3
"""
Test the screener with updated yfinance
"""

from data_fetcher import StockDataFetcher
from screener import GrowthStockScreener
import time

def test_screener():
    print("Testing Stock Screener with Updated yfinance")
    print("=" * 50)

    # Test with a small set of well-known stocks
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']

    print(f"Testing with {len(test_tickers)} stocks: {', '.join(test_tickers)}")
    print()

    # Initialize components
    fetcher = StockDataFetcher(rate_limit_delay=0.2)
    screener = GrowthStockScreener(fetcher)

    # Run screening with minimal filters
    print("Running screening...")
    results = screener.screen_stocks(
        tickers=test_tickers,
        min_revenue_growth=0,  # Accept all growth rates for testing
        min_market_cap=0,       # No market cap filter
        max_pe_ratio=0,         # No P/E filter
        require_positive_earnings=False,
        require_analyst_coverage=False
    )

    print("\n" + "=" * 50)
    print("RESULTS:")

    if results.empty:
        print("❌ No stocks found - there's still an issue")
        return False
    else:
        print(f"✅ Found {len(results)} stocks!")
        print("\nStock Details:")
        for idx, row in results.iterrows():
            print(f"\n{row['ticker']} - {row['company_name']}")
            print(f"  Market Cap: ${row['market_cap']:,.0f}" if row['market_cap'] else "  Market Cap: N/A")
            print(f"  Current Price: ${row['current_price']:.2f}" if row['current_price'] else "  Current Price: N/A")
            print(f"  Revenue Growth YoY: {row['revenue_growth_yoy']}%")
            print(f"  Composite Score: {row['composite_score']}")

        return True

if __name__ == "__main__":
    success = test_screener()

    print("\n" + "=" * 50)
    if success:
        print("✅ SUCCESS! The screener is now working properly.")
        print("\nThe app should now be able to find stocks.")
        print("You can access it at http://localhost:8501")
    else:
        print("❌ FAILED - The screener is still not finding stocks.")
        print("\nTroubleshooting steps:")
        print("1. Check internet connection")
        print("2. Try again in a few minutes (rate limiting)")
        print("3. Clear cache and restart")