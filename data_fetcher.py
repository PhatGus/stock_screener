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
import random
import warnings

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from ticker_cache import TickerCache
except Exception:  # pragma: no cover - cache is optional
    TickerCache = None

warnings.filterwarnings('ignore')

# Rotating pool of realistic browser User-Agent strings.  Rotating the UA (and a
# couple of correlated headers) between fetches reduces the chance Yahoo
# fingerprints the client and rate-limits the whole session at once.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) "
    "Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",
]

ACCEPT_LANGUAGES = ["en-US,en;q=0.9", "en-GB,en;q=0.8", "en-US,en;q=0.7"]


class YFinanceStockDataFetcher:
    """Fetches and processes stock data from yfinance.

    NOTE: As of the FMP migration this class is no longer the primary fetcher.
    It is retained as a *fallback* in case FMP is unavailable.  The active
    ``StockDataFetcher`` used by ``app.py`` / ``screener.py`` is re-exported at
    the bottom of this module from ``fmp_fetcher`` (see below).
    """

    def __init__(self, rate_limit_delay: float = 0.2,
                 min_ticker_delay: float = 1.5,
                 max_ticker_delay: float = 2.0,
                 batch_size: int = 25,
                 batch_delay: float = 10.0,
                 use_cache: bool = True,
                 cache_max_age_hours: float = 24.0,
                 cache_db_path: str = "ticker_cache.db",
                 force_refresh: bool = False):
        """
        Initialize the data fetcher

        Args:
            rate_limit_delay: Base delay used for retry/backoff timing
            min_ticker_delay: Minimum delay (s) between individual ticker fetches
            max_ticker_delay: Maximum delay (s) between individual ticker fetches
            batch_size: Number of tickers fetched before pausing
            batch_delay: Pause (s) between batches
            use_cache: Whether to use the SQLite cross-run cache
            cache_max_age_hours: Reuse cached tickers younger than this many hours
            cache_db_path: Path to the SQLite cache database
        """
        self.rate_limit_delay = rate_limit_delay
        self.cache = {}
        self.error_count = 0
        self.max_retries = 3

        # --- Rate-limit-avoidance configuration (Bug 2) ---
        self.min_ticker_delay = min_ticker_delay
        self.max_ticker_delay = max_ticker_delay
        self.batch_size = batch_size
        self.batch_delay = batch_delay

        # --- SQLite cross-run cache (Bug 2) ---
        self.use_cache = use_cache
        # force_refresh skips cache *reads* (always re-fetch) but still writes
        # fresh results back so later runs in the day stay fast.
        self.force_refresh = force_refresh
        self.cache_max_age_hours = cache_max_age_hours
        self.cache_db = None
        if use_cache and TickerCache is not None:
            try:
                self.cache_db = TickerCache(cache_db_path)
            except Exception as e:
                print(f"Could not open ticker cache ({e}); continuing without it.")
                self.cache_db = None

        # --- Rotating request session to avoid fingerprinting (Bug 2) ---
        self.session = None
        if requests is not None:
            try:
                self.session = requests.Session()
            except Exception:
                self.session = None

        # Extension hooks (off by default so existing behavior is unchanged).
        # Set enable_extended=True and provide voo_returns to fetch the new
        # Group A-E fields appended to each ticker dict.
        self.enable_extended = False
        self.voo_returns = None

    @property
    def cache_variant(self) -> str:
        """Cache namespace: extended data must not be mixed with base data."""
        return 'ext' if self.enable_extended else 'base'

    def _rotate_headers(self) -> None:
        """Apply a randomly chosen set of browser-like headers to the session."""
        if self.session is None:
            return
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': random.choice(ACCEPT_LANGUAGES),
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def _make_ticker(self, ticker: str):
        """Construct a yf.Ticker with a rotated session (version-tolerant)."""
        self._rotate_headers()
        if self.session is not None:
            try:
                return yf.Ticker(ticker, session=self.session)
            except TypeError:
                # Older/newer yfinance may not accept a session kwarg.
                return yf.Ticker(ticker)
        return yf.Ticker(ticker)

    @staticmethod
    def _report(progress_callback, current: int, total: int, ticker: str,
                eta_seconds: Optional[float]) -> None:
        """Invoke a progress callback, tolerating 3- or 4-argument callbacks."""
        if progress_callback is None:
            return
        try:
            progress_callback(current, total, ticker, eta_seconds)
        except TypeError:
            try:
                progress_callback(current, total, ticker)
            except Exception:
                pass
        except Exception:
            pass

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

                # Fetch data from yfinance (rotating session headers)
                stock = self._make_ticker(ticker)

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
        Fetch data for multiple tickers, using the SQLite cache and a
        rate-limit-friendly batching strategy.

        Strategy (Bug 2):
          * Tickers with fresh cached data (< cache_max_age_hours) are loaded
            from SQLite and never re-fetched.
          * Remaining tickers are fetched in batches of ``batch_size`` with a
            ``batch_delay`` pause between batches and a randomized
            ``min_ticker_delay``-``max_ticker_delay`` pause between each ticker.
          * Successful fetches are written back to the cache immediately, so an
            interrupted run still benefits subsequent runs.
          * ``progress_callback`` receives (current, total, ticker, eta_seconds);
            3-argument callbacks are also supported.

        Args:
            tickers: List of ticker symbols
            progress_callback: Optional callback for progress updates

        Returns:
            DataFrame with all stock data
        """
        results = []
        total = len(tickers)

        # --- 1. Serve fresh tickers from the cross-run cache ---
        cached_map: Dict[str, Dict] = {}
        if self.use_cache and self.cache_db is not None and not self.force_refresh:
            try:
                cached_map = self.cache_db.get_many(
                    tickers, variant=self.cache_variant,
                    max_age_hours=self.cache_max_age_hours,
                )
            except Exception as e:
                print(f"Cache read failed ({e}); fetching everything fresh.")
                cached_map = {}

        to_fetch = []
        for ticker in tickers:
            if ticker in cached_map:
                results.append(cached_map[ticker])
            else:
                to_fetch.append(ticker)

        cached_count = len(results)
        if cached_count:
            print(f"Loaded {cached_count}/{total} tickers from cache; "
                  f"fetching {len(to_fetch)} from Yahoo Finance.")
        # Report cached items as already complete so the bar starts populated.
        if cached_count and progress_callback:
            last_cached = next((t for t in tickers if t in cached_map), tickers[0])
            self._report(progress_callback, cached_count, total, last_cached, 0.0)

        # --- 2. Fetch the rest in delayed batches ---
        start_time = time.time()
        fetched = 0
        for batch_start in range(0, len(to_fetch), self.batch_size):
            batch = to_fetch[batch_start:batch_start + self.batch_size]

            for ticker in batch:
                data = self.fetch_stock_data(ticker)
                fetched += 1
                current = cached_count + fetched

                if data:
                    results.append(data)
                    if self.use_cache and self.cache_db is not None:
                        try:
                            self.cache_db.set(ticker, data, variant=self.cache_variant)
                        except Exception as e:
                            print(f"Cache write failed for {ticker}: {e}")

                # Estimate time remaining from the live fetch rate.
                elapsed = time.time() - start_time
                rate = fetched / elapsed if elapsed > 0 else 0
                remaining = len(to_fetch) - fetched
                eta = (remaining / rate) if rate > 0 else None
                # Account for the batch pauses still to come.
                if eta is not None and self.batch_size > 0:
                    pending_batches = remaining // self.batch_size
                    eta += pending_batches * self.batch_delay
                self._report(progress_callback, current, total, ticker, eta)

                # Per-ticker delay (randomized to look less robotic).
                if fetched < len(to_fetch):
                    time.sleep(random.uniform(self.min_ticker_delay, self.max_ticker_delay))

            # Pause between batches (skip after the final batch).
            if batch_start + self.batch_size < len(to_fetch):
                print(f"  Batch complete ({cached_count + fetched}/{total}); "
                      f"pausing {self.batch_delay}s to avoid rate limiting...")
                time.sleep(self.batch_delay)

        return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Primary fetcher: Financial Modeling Prep (FMP)
# ---------------------------------------------------------------------------
# This module is now a thin wrapper: it re-exports the FMP fetcher as
# ``StockDataFetcher`` so that ``app.py`` and ``screener.py`` keep importing
# ``StockDataFetcher`` from here with no changes.  The yfinance implementation
# above (``YFinanceStockDataFetcher``) is retained as a fallback.
#
# Behavior:
#   * If ``fmp_fetcher`` imports cleanly, ``StockDataFetcher`` IS the FMP fetcher.
#     A missing ``FMP_API_KEY`` then raises a clear RuntimeError at construction.
#   * If ``fmp_fetcher`` cannot be imported at all (e.g. missing dependency),
#     we fall back to the yfinance fetcher so the app still runs.
try:
    from fmp_fetcher import FMPStockDataFetcher as StockDataFetcher
except ImportError as _fmp_import_err:  # pragma: no cover - fallback path
    print(f"FMP fetcher unavailable ({_fmp_import_err}); "
          f"falling back to yfinance fetcher.")
    StockDataFetcher = YFinanceStockDataFetcher


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