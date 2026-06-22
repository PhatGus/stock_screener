#!/usr/bin/env python3
"""
Simple test to check yfinance functionality
"""

import yfinance as yf
import time

def test_single_ticker():
    """Test fetching data for a single ticker"""
    print("Testing yfinance basic functionality...")
    print("-" * 50)

    ticker = "AAPL"
    print(f"\nFetching data for {ticker}...")

    try:
        # Method 1: Direct ticker object
        stock = yf.Ticker(ticker)

        # Wait a bit
        time.sleep(1)

        # Try to get info
        print("Getting info...")
        info = stock.info

        print(f"\nInfo keys available: {len(info.keys())} keys")
        print(f"Sample keys: {list(info.keys())[:10]}")

        # Check specific fields
        print(f"\nCompany Name: {info.get('longName', 'N/A')}")
        print(f"Current Price: {info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))}")
        print(f"Market Cap: {info.get('marketCap', 'N/A')}")
        print(f"PE Ratio: {info.get('trailingPE', 'N/A')}")

        # Method 2: Try download method
        print(f"\n\nTrying download method...")
        data = yf.download(ticker, period="1d", progress=False)

        if not data.empty:
            print(f"Download successful! Got {len(data)} rows")
            latest_close = data['Close'].iloc[-1]
            print(f"Latest close price: ${float(latest_close):.2f}")
        else:
            print("Download returned empty data")

        # Method 3: Try getting financials
        print(f"\n\nTrying to get financials...")
        try:
            financials = stock.quarterly_financials
            if financials is not None and not financials.empty:
                print(f"Quarterly financials available: {financials.shape}")
                print(f"Latest quarter columns: {list(financials.columns[:2])}")
            else:
                print("No quarterly financials available")
        except Exception as e:
            print(f"Error getting financials: {e}")

        return True

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alternative_approach():
    """Test alternative data fetching approach"""
    print("\n\nTesting alternative approach...")
    print("-" * 50)

    ticker = "MSFT"

    try:
        # Use download which is often more reliable
        print(f"Downloading data for {ticker}...")
        data = yf.download(ticker, period="1mo", interval="1d", progress=False)

        if not data.empty:
            print(f"✓ Download successful!")
            print(f"  Columns: {list(data.columns)}")
            latest_close = data['Close'].iloc[-1]
            latest_volume = data['Volume'].iloc[-1]
            print(f"  Latest Close: ${float(latest_close):.2f}")
            print(f"  Latest Volume: {float(latest_volume):,.0f}")

            # Get ticker object for additional info
            stock = yf.Ticker(ticker)

            # Try fast_info which is sometimes more reliable than info
            try:
                fast_info = stock.fast_info
                print(f"\n✓ Fast info available:")
                print(f"  Market Cap: ${fast_info.get('marketCap', 'N/A'):,.0f}" if fast_info.get('marketCap') else "  Market Cap: N/A")
                print(f"  52 Week High: ${fast_info.get('fiftyTwoWeekHigh', 'N/A')}")
            except:
                print("\nFast info not available")

            return True
        else:
            print("Download failed - empty data")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("YFINANCE DIAGNOSTIC TEST")
    print("=" * 50)

    # Test basic functionality
    success1 = test_single_ticker()

    # Wait before next test
    time.sleep(2)

    # Test alternative approach
    success2 = test_alternative_approach()

    print("\n" + "=" * 50)
    if success1 or success2:
        print("✓ At least one method works - yfinance is functional")
        print("\nRecommendation: Use the working method in the app")
    else:
        print("✗ yfinance appears to be having issues")
        print("\nPossible causes:")
        print("1. Yahoo Finance API changes")
        print("2. Rate limiting")
        print("3. Network issues")
        print("\nTry: pip install --upgrade yfinance")