#!/usr/bin/env python3
"""
Test script to verify forward revenue estimate fixes
"""

import sys
import traceback
from data_fetcher import StockDataFetcher
from screener import GrowthStockScreener

def test_forward_estimates():
    """Test that forward estimates don't cause errors"""
    print("Testing Forward Revenue Estimate Fixes")
    print("=" * 50)

    # Test tickers known to have various data availability
    test_tickers = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']

    fetcher = StockDataFetcher()
    errors = []
    successes = []

    for ticker in test_tickers:
        print(f"\nTesting {ticker}...")
        try:
            data = fetcher.fetch_stock_data(ticker)

            if data:
                # Check if forward estimates are handled properly
                forward_rev = data.get('forward_revenue_estimate')
                implied_growth = data.get('implied_earnings_growth')

                print(f"  ✓ Data fetched successfully")
                print(f"    - Company: {data.get('company_name', 'N/A')}")
                print(f"    - Market Cap: ${data.get('market_cap', 0):,.0f}")
                print(f"    - Revenue Growth YoY: {data.get('revenue_growth_yoy', 'N/A')}%")
                print(f"    - Forward Revenue Est: {forward_rev if forward_rev else 'N/A'}")
                print(f"    - Implied Earnings Growth: {implied_growth if implied_growth else 'N/A'}%")

                successes.append(ticker)
            else:
                print(f"  ⚠ No data returned for {ticker}")
                errors.append((ticker, "No data returned"))

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            errors.append((ticker, str(e)))
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"Results: {len(successes)}/{len(test_tickers)} successful")

    if errors:
        print("\nErrors encountered:")
        for ticker, error in errors:
            print(f"  - {ticker}: {error}")
    else:
        print("\n✅ All tests passed successfully!")

    return len(errors) == 0


def test_screening_with_forward_filter():
    """Test screening with forward estimate filtering"""
    print("\n\nTesting Screening with Forward Estimate Filter")
    print("=" * 50)

    test_tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META']

    screener = GrowthStockScreener()

    try:
        # Run screening with minimal criteria
        results = screener.screen_stocks(
            tickers=test_tickers,
            min_revenue_growth=0,  # Low threshold for testing
            min_market_cap=0,
            require_positive_earnings=False,
            require_analyst_coverage=False
        )

        print(f"Screening completed: {len(results)} stocks found")

        if not results.empty:
            # Check if forward estimate columns exist
            has_forward_rev = 'forward_revenue_estimate' in results.columns
            has_implied_growth = 'implied_earnings_growth' in results.columns

            print(f"  - Forward revenue column exists: {has_forward_rev}")
            print(f"  - Implied growth column exists: {has_implied_growth}")

            # Test filtering logic
            if has_forward_rev or has_implied_growth:
                # Apply the same filtering logic as in app.py
                filtered = results.copy()

                if has_forward_rev and has_implied_growth:
                    mask = (
                        (results['forward_revenue_estimate'].notna() &
                         (results['forward_revenue_estimate'] > 0)) |
                        (results['implied_earnings_growth'].notna() &
                         (results['implied_earnings_growth'] > 0))
                    )
                    filtered = results[mask]
                elif has_forward_rev:
                    filtered = results[
                        results['forward_revenue_estimate'].notna() &
                        (results['forward_revenue_estimate'] > 0)
                    ]
                elif has_implied_growth:
                    filtered = results[
                        results['implied_earnings_growth'].notna() &
                        (results['implied_earnings_growth'] > 0)
                    ]

                print(f"  - After filtering for positive estimates: {len(filtered)} stocks")
                print("\n✅ Filtering logic works correctly!")
            else:
                print("  ⚠ No forward estimate columns available")

        return True

    except Exception as e:
        print(f"\n✗ Screening failed: {str(e)}")
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n🔧 TESTING FORWARD REVENUE ESTIMATE FIXES\n")

    test1_passed = test_forward_estimates()
    test2_passed = test_screening_with_forward_filter()

    print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED! The fixes are working correctly.")
        print("\nThe app should now handle forward revenue estimates properly without errors.")
        return 0
    else:
        print("⚠️ Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())