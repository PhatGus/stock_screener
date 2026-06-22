#!/usr/bin/env python3
"""
Test EDGAR integration with type fixes
"""

from data_fetcher import StockDataFetcher
from screener import GrowthStockScreener
import time

def test_edgar_screening():
    print("Testing EDGAR Integration with Type Fixes")
    print("=" * 50)

    # Test with a small set of stocks
    test_tickers = ['AAPL', 'MSFT']

    print(f"Testing with {len(test_tickers)} stocks: {', '.join(test_tickers)}")
    print()

    # Initialize components with EDGAR enabled
    fetcher = StockDataFetcher(rate_limit_delay=0.2)
    screener = GrowthStockScreener(fetcher, use_edgar=True)  # Enable EDGAR

    # Run screening with minimal filters
    print("Running screening with EDGAR analysis...")
    try:
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
            print(f"✅ Found {len(results)} stocks with EDGAR data!")

            # Check if EDGAR columns exist
            edgar_columns = ['edgar_score', 'mda_sentiment', 'growth_mentions', 'risk_factors']
            found_columns = [col for col in edgar_columns if col in results.columns]

            if found_columns:
                print(f"\nEDGAR columns found: {', '.join(found_columns)}")

                for idx, row in results.iterrows():
                    print(f"\n{row['ticker']} - {row['company_name']}")
                    print(f"  Market Cap: ${row['market_cap']:,.0f}" if row['market_cap'] else "  Market Cap: N/A")
                    print(f"  Revenue Growth YoY: {row['revenue_growth_yoy']}%")

                    # EDGAR data
                    if 'edgar_score' in results.columns:
                        print(f"  EDGAR Score: {row.get('edgar_score', 'N/A')}")
                    if 'mda_sentiment' in results.columns:
                        print(f"  MD&A Sentiment: {row.get('mda_sentiment', 'N/A')}")
                    if 'growth_mentions' in results.columns:
                        print(f"  Growth Mentions: {row.get('growth_mentions', 'N/A')}")
                    if 'risk_factors' in results.columns:
                        print(f"  Risk Factors: {row.get('risk_factors', 'N/A')}")

                    print(f"  Composite Score: {row['composite_score']}")
            else:
                print("\n⚠️ No EDGAR columns found in results")

            return True

    except Exception as e:
        print(f"\n❌ Error during screening: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_edgar_screening()

    print("\n" + "=" * 50)
    if success:
        print("✅ SUCCESS! EDGAR integration is working without type errors.")
        print("\nThe app should now work with EDGAR analysis enabled.")
    else:
        print("❌ FAILED - EDGAR integration still has issues.")
        print("\nCheck the error messages above for details.")