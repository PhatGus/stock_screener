"""
Data Fetcher Module
Handles all data retrieval from yfinance API
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import warnings
warnings.filterwarnings('ignore')

class StockDataFetcher:
    """Fetches and processes stock data from yfinance"""

    def __init__(self, rate_limit_delay: float = 0.2):
        """
        Initialize the data fetcher

        Args:
            rate_limit_delay: Delay between API calls to avoid rate limiting
        """
        self.rate_limit_delay = rate_limit_delay
        self.cache = {}
        self.error_count = 0
        self.max_retries = 3
        # Extension hooks (off by default so existing behavior is unchanged).
        # Set enable_extended=True and provide voo_returns to fetch the new
        # Group A-E fields appended to each ticker dict.
        self.enable_extended = False
        self.voo_returns = None

    def fetch_stock_data(self, ticker: str, period: str = "2y") -> Optional[Dict]:
        """
        Fetch comprehensive stock data for a single ticker

        Args:
            ticker: Stock ticker symbol
            period: Time period for historical data

        Returns:
            Dictionary with stock data or None if fetch fails
        """
        # Check cache first
        cache_key = f"{ticker}_{period}"
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (datetime.now() - cache_time).seconds < 3600:  # 1 hour cache
                return data

        # Retry logic for rate limiting
        for attempt in range(self.max_retries):
            try:
                # Add exponential backoff for retries
                if attempt > 0:
                    wait_time = self.rate_limit_delay * (2 ** attempt)
                    print(f"Rate limited, waiting {wait_time}s before retry {attempt+1}/{self.max_retries}...")
                    time.sleep(wait_time)

                # Fetch data from yfinance
                stock = yf.Ticker(ticker)

                # Get basic info
                info = stock.info

                # Check if we got valid data
                if not info or (not info.get('currentPrice') and not info.get('regularMarketPrice') and not info.get('previousClose')):
                    if attempt < self.max_retries - 1:
                        print(f"Incomplete data for {ticker}, retrying...")
                        continue  # Try again
                    else:
                        print(f"Failed to get complete data for {ticker} after {self.max_retries} attempts")
                        return None

                # Get financial data
                try:
                    financials = stock.quarterly_financials
                except Exception:
                    financials = None

                # Note: recommendations are now fetched inside _get_analyst_sentiment

                # Calculate metrics
                data = {
                    'ticker': ticker,
                    'company_name': info.get('longName', ticker),
                    'sector': info.get('sector', 'Unknown'),
                    'industry': info.get('industry', 'Unknown'),
                    'market_cap': info.get('marketCap', 0),
                    'current_price': info.get('currentPrice', info.get('previousClose', 0)),
                    'currency': info.get('currency', 'USD'),
                    'exchange': info.get('exchange', 'Unknown'),
                    'pe_ratio': info.get('forwardPE', info.get('trailingPE', None)),
                    'peg_ratio': info.get('pegRatio', None),
                    'price_to_book': info.get('priceToBook', None),
                    'debt_to_equity': info.get('debtToEquity', None),
                    'return_on_equity': info.get('returnOnEquity', None),
                    'profit_margin': info.get('profitMargins', None),
                    '52_week_high': info.get('fiftyTwoWeekHigh', None),
                    '52_week_low': info.get('fiftyTwoWeekLow', None),
                    'average_volume': info.get('averageVolume', 0),
                    'shares_outstanding': info.get('sharesOutstanding', 0),
                }

                # Calculate revenue growth
                revenue_growth = self._calculate_revenue_growth(financials)
                data.update(revenue_growth)

                # Get forward estimates
                forward_estimates = self._get_forward_estimates(stock, info)
                data.update(forward_estimates)

                # Get analyst sentiment (now passes stock object)
                analyst_sentiment = self._get_analyst_sentiment(stock)
                data.update(analyst_sentiment)

                # --- Extension: append new Group A-E fields (additive only) ---
                # This reuses the already-constructed `stock` object and the
                # per-ticker `data` dict, exactly as the existing fetches do.
                if self.enable_extended:
                    try:
                        from screener_extension import fetch_extended_fields
                        extended = fetch_extended_fields(
                            stock, data, self.voo_returns, ticker,
                            rate_limit_delay=0.5
                        )
                        data.update(extended)
                    except Exception as ext_err:
                        # Extension must never break the existing fetch.
                        print(f"Extended fetch failed for {ticker}: {ext_err}")

                # Cache the result
                self.cache[cache_key] = (datetime.now(), data)

                # Rate limiting
                time.sleep(self.rate_limit_delay)

                return data

            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    print(f"Rate limited on {ticker}, attempt {attempt+1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        continue
                else:
                    print(f"Error fetching data for {ticker}: {str(e)}")
                    if attempt < self.max_retries - 1:
                        continue

        # If all retries failed
        print(f"Failed to fetch data for {ticker} after {self.max_retries} attempts")
        return None

    def _calculate_revenue_growth(self, financials: pd.DataFrame) -> Dict:
        """Calculate year-over-year revenue growth"""
        try:
            if financials is None or financials.empty:
                return {
                    'revenue_growth_yoy': None,
                    'revenue_growth_qoq': None,
                    'latest_revenue': None,
                    'revenue_ttm': None
                }

            # Get total revenue row
            if 'Total Revenue' in financials.index:
                revenues = financials.loc['Total Revenue']
            elif 'Operating Revenue' in financials.index:
                revenues = financials.loc['Operating Revenue']
            else:
                return {
                    'revenue_growth_yoy': None,
                    'revenue_growth_qoq': None,
                    'latest_revenue': None,
                    'revenue_ttm': None
                }

            # Sort by date (newest first)
            revenues = revenues.sort_index(ascending=False)

            # Calculate TTM revenue (last 4 quarters)
            revenue_ttm = revenues.iloc[:4].sum() if len(revenues) >= 4 else None

            # Calculate YoY growth (compare to 4 quarters ago)
            if len(revenues) >= 5:
                current_quarter = revenues.iloc[0]
                year_ago_quarter = revenues.iloc[4]
                yoy_growth = ((current_quarter - year_ago_quarter) / abs(year_ago_quarter)) * 100
            else:
                yoy_growth = None

            # Calculate QoQ growth
            if len(revenues) >= 2:
                current_quarter = revenues.iloc[0]
                previous_quarter = revenues.iloc[1]
                qoq_growth = ((current_quarter - previous_quarter) / abs(previous_quarter)) * 100
            else:
                qoq_growth = None

            return {
                'revenue_growth_yoy': round(yoy_growth, 2) if yoy_growth else None,
                'revenue_growth_qoq': round(qoq_growth, 2) if qoq_growth else None,
                'latest_revenue': float(revenues.iloc[0]) if len(revenues) > 0 else None,
                'revenue_ttm': float(revenue_ttm) if revenue_ttm else None
            }

        except Exception as e:
            print(f"Error calculating revenue growth: {str(e)}")
            return {
                'revenue_growth_yoy': None,
                'revenue_growth_qoq': None,
                'latest_revenue': None,
                'revenue_ttm': None
            }

    def _get_forward_estimates(self, stock: yf.Ticker, info: Dict) -> Dict:
        """Get forward revenue and earnings estimates"""
        try:
            # Initialize estimates
            current_year_est = None
            next_year_est = None

            # Try different methods to get revenue estimates
            # Method 1: Try to get from earnings_estimate (which sometimes includes revenue)
            try:
                if hasattr(stock, 'earnings_estimate'):
                    earnings_est = stock.earnings_estimate
                    if earnings_est is not None and not earnings_est.empty:
                        # Sometimes revenue data is in earnings_estimate
                        pass
            except Exception:
                pass

            # Method 2: Try to get from recommendations_summary
            try:
                if hasattr(stock, 'recommendations_summary'):
                    rec_summary = stock.recommendations_summary
                    # Process if available
            except Exception:
                pass

            # Method 3: Get growth estimates from info dictionary
            try:
                # yfinance often provides these in the info dict
                revenue_growth = info.get('revenueGrowth', None)
                earnings_growth = info.get('earningsGrowth', None)

                # Also check for quarterly revenue growth
                quarterly_revenue_growth = info.get('revenueQuarterlyGrowth', None)

                # If we have current revenue and growth rate, estimate forward
                if info.get('totalRevenue') and revenue_growth:
                    current_revenue = info.get('totalRevenue')
                    current_year_est = current_revenue * (1 + (revenue_growth if revenue_growth else 0))
                    next_year_est = current_year_est * (1 + (revenue_growth if revenue_growth else 0))

            except Exception:
                pass

            # Get forward P/E and earnings growth from info
            forward_pe = info.get('forwardPE', None)
            peg_ratio = info.get('pegRatio', None)

            # Calculate implied earnings growth from PEG ratio
            implied_growth = None
            if peg_ratio and forward_pe:
                implied_growth = forward_pe / peg_ratio if peg_ratio != 0 else None

            # Get revenue estimates from info if available
            if current_year_est is None:
                current_year_est = info.get('revenueEstimate', {}).get('avg', None) if isinstance(info.get('revenueEstimate'), dict) else None

            return {
                'forward_revenue_estimate': current_year_est,
                'next_year_revenue_estimate': next_year_est,
                'forward_pe': forward_pe,
                'implied_earnings_growth': round(implied_growth, 2) if implied_growth else None,
                'target_mean_price': info.get('targetMeanPrice', None),
                'target_high_price': info.get('targetHighPrice', None),
                'target_low_price': info.get('targetLowPrice', None),
                'recommendation_mean': info.get('recommendationMean', None),
                'recommendation_key': info.get('recommendationKey', None),
                'number_of_analysts': info.get('numberOfAnalystOpinions', 0)
            }

        except Exception as e:
            print(f"Error getting forward estimates: {str(e)}")
            return {
                'forward_revenue_estimate': None,
                'next_year_revenue_estimate': None,
                'forward_pe': None,
                'implied_earnings_growth': None,
                'target_mean_price': None,
                'target_high_price': None,
                'target_low_price': None,
                'recommendation_mean': None,
                'recommendation_key': None,
                'number_of_analysts': 0
            }

    def _get_analyst_sentiment(self, stock: yf.Ticker) -> Dict:
        """Analyze analyst recommendations sentiment"""
        try:
            # Method 1: Try to get aggregated recommendations
            try:
                recommendations = stock.recommendations
                if recommendations is not None and not recommendations.empty:
                    # Get the most recent period (usually index 0)
                    latest = recommendations.iloc[0]

                    # Calculate totals
                    strong_buy = latest.get('strongBuy', 0)
                    buy = latest.get('buy', 0)
                    hold = latest.get('hold', 0)
                    sell = latest.get('sell', 0)
                    strong_sell = latest.get('strongSell', 0)

                    total = strong_buy + buy + hold + sell + strong_sell

                    if total > 0:
                        buy_percent = ((strong_buy + buy) / total) * 100
                        hold_percent = (hold / total) * 100
                        sell_percent = ((sell + strong_sell) / total) * 100
                    else:
                        buy_percent = hold_percent = sell_percent = None
                else:
                    buy_percent = hold_percent = sell_percent = None
            except:
                buy_percent = hold_percent = sell_percent = None

            # Method 2: Try to get upgrades/downgrades for recent activity
            upgrades = downgrades = 0
            try:
                upgrades_downgrades = stock.upgrades_downgrades
                if upgrades_downgrades is not None and not upgrades_downgrades.empty:
                    # Get recent activity (last 90 days)
                    recent_date = pd.Timestamp.now() - pd.Timedelta(days=90)
                    # Ensure index is datetime
                    upgrades_downgrades.index = pd.to_datetime(upgrades_downgrades.index)
                    recent = upgrades_downgrades[upgrades_downgrades.index > recent_date]

                    if not recent.empty:
                        # Count upgrades and downgrades
                        for _, row in recent.iterrows():
                            action = str(row.get('Action', '')).lower()
                            if 'up' in action or 'upgrade' in action or 'init' in action:
                                upgrades += 1
                            elif 'down' in action or 'downgrade' in action:
                                downgrades += 1
            except:
                pass

            return {
                'analyst_buy_percent': round(buy_percent, 1) if buy_percent is not None else None,
                'analyst_hold_percent': round(hold_percent, 1) if hold_percent is not None else None,
                'analyst_sell_percent': round(sell_percent, 1) if sell_percent is not None else None,
                'recent_upgrades': upgrades,
                'recent_downgrades': downgrades
            }

        except Exception as e:
            print(f"Error analyzing analyst sentiment: {str(e)}")
            return {
                'analyst_buy_percent': None,
                'analyst_hold_percent': None,
                'analyst_sell_percent': None,
                'recent_upgrades': 0,
                'recent_downgrades': 0
            }

    def fetch_batch_data(self, tickers: List[str], progress_callback=None) -> pd.DataFrame:
        """
        Fetch data for multiple tickers in batch

        Args:
            tickers: List of ticker symbols
            progress_callback: Optional callback for progress updates

        Returns:
            DataFrame with all stock data
        """
        results = []
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            if progress_callback:
                progress_callback(i + 1, total, ticker)

            data = self.fetch_stock_data(ticker)
            if data:
                results.append(data)

        return pd.DataFrame(results)


if __name__ == "__main__":
    # Test the fetcher
    fetcher = StockDataFetcher()

    # Test with a few tickers
    test_tickers = ['AAPL', 'MSFT', 'NVDA']
    print("Testing data fetcher with sample tickers...")

    for ticker in test_tickers:
        print(f"\nFetching data for {ticker}...")
        data = fetcher.fetch_stock_data(ticker)
        if data:
            print(f"  Company: {data['company_name']}")
            print(f"  Market Cap: ${data['market_cap']:,.0f}" if data['market_cap'] else "  Market Cap: N/A")
            print(f"  Revenue Growth YoY: {data['revenue_growth_yoy']}%")
            print(f"  Current Price: ${data['current_price']:.2f}" if data['current_price'] else "  Current Price: N/A")