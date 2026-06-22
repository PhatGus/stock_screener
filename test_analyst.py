#!/usr/bin/env python3
"""
Test analyst recommendations data structure in new yfinance
"""

import yfinance as yf
import pandas as pd
import time

def test_analyst_data():
    print("Testing Analyst Recommendations Data Structure")
    print("=" * 50)

    tickers = ['AAPL', 'MSFT']

    for ticker_symbol in tickers:
        print(f"\n{ticker_symbol}:")
        print("-" * 30)

        try:
            stock = yf.Ticker(ticker_symbol)

            # Test 1: Check recommendations
            print("\n1. Testing stock.recommendations:")
            try:
                recs = stock.recommendations
                if recs is not None and not recs.empty:
                    print(f"   Shape: {recs.shape}")
                    print(f"   Columns: {list(recs.columns)}")
                    print(f"   Index type: {type(recs.index)}")
                    print(f"   Sample data (last 2 rows):")
                    print(recs.tail(2))
                else:
                    print("   No recommendations data")
            except Exception as e:
                print(f"   Error: {e}")

            # Test 2: Check analyst_recommendations property
            print("\n2. Testing stock.analyst_recommendations:")
            try:
                if hasattr(stock, 'analyst_recommendations'):
                    analyst_recs = stock.analyst_recommendations
                    if analyst_recs is not None and not analyst_recs.empty:
                        print(f"   Shape: {analyst_recs.shape}")
                        print(f"   Columns: {list(analyst_recs.columns)}")
                        print(f"   Sample data (last 2 rows):")
                        print(analyst_recs.tail(2))
                    else:
                        print("   No analyst recommendations")
                else:
                    print("   Property doesn't exist")
            except Exception as e:
                print(f"   Error: {e}")

            # Test 3: Check info for recommendation data
            print("\n3. Testing stock.info for recommendation fields:")
            info = stock.info
            rec_fields = [
                'recommendationMean', 'recommendationKey', 'numberOfAnalystOpinions',
                'targetMeanPrice', 'targetHighPrice', 'targetLowPrice'
            ]
            for field in rec_fields:
                value = info.get(field)
                if value is not None:
                    print(f"   {field}: {value}")

            # Test 4: Check upgrades/downgrades
            print("\n4. Testing stock.upgrades_downgrades:")
            try:
                if hasattr(stock, 'upgrades_downgrades'):
                    upgrades = stock.upgrades_downgrades
                    if upgrades is not None and not upgrades.empty:
                        print(f"   Shape: {upgrades.shape}")
                        print(f"   Columns: {list(upgrades.columns)}")
                        print(f"   Sample data (last 2 rows):")
                        print(upgrades.tail(2))
                    else:
                        print("   No upgrades/downgrades data")
                else:
                    print("   Property doesn't exist")
            except Exception as e:
                print(f"   Error: {e}")

            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"Error for {ticker_symbol}: {e}")

    print("\n" + "=" * 50)
    print("Analysis Complete!")
    print("\nRecommendations for fixing Buy %:")
    print("1. Use the correct property name for recommendations")
    print("2. Check the correct column names in the DataFrame")
    print("3. Use info fields as fallback for summary stats")

if __name__ == "__main__":
    test_analyst_data()