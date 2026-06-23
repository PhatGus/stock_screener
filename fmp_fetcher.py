"""
Financial Modeling Prep (FMP) Data Fetcher
==========================================

Primary data source for the stock screener, replacing yfinance.  This module
replicates the per-ticker data dict that ``data_fetcher.StockDataFetcher``
historically produced from yfinance, but sources every field from FMP REST
endpoints instead.

Design goals
------------
* Drop-in replacement: :class:`FMPStockDataFetcher` exposes the same interface
  the rest of the app relies on (``fetch_stock_data``, ``fetch_batch_data``,
  the ``enable_extended``/``voo_returns`` attributes, the SQLite cache, and the
  ETA-capable progress callback), so ``app.py`` and ``screener.py`` need no
  changes -- they import ``StockDataFetcher`` from ``data_fetcher`` as before.
* No yfinance dependency here.  All network I/O goes through a single
  ``requests.Session`` with a 10-second timeout.
* Robust: any non-200 response (or parse error) is logged and yields ``None``
  for that field group; a single bad endpoint never crashes the whole fetch.

The FMP API key is read from the ``FMP_API_KEY`` environment variable.  If it is
missing, constructing a fetcher raises a clear ``RuntimeError``.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests

try:
    from ticker_cache import TickerCache
except Exception:  # pragma: no cover - cache is optional
    TickerCache = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FMP_API_KEY = os.environ.get('FMP_API_KEY')

V3_BASE = "https://financialmodelingprep.com/api/v3"
V4_BASE = "https://financialmodelingprep.com/api/v4"

REQUEST_TIMEOUT = 10  # seconds, per requirement 8

# ---------------------------------------------------------------------------
# Logging (shared error log with the rest of the screener)
# ---------------------------------------------------------------------------

ERROR_LOG_FILE = "screener_errors.log"
_logger = logging.getLogger("fmp_fetcher")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.FileHandler(ERROR_LOG_FILE)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def _log(ticker: str, endpoint: str, message: str) -> None:
    """Append a fetch failure to ``screener_errors.log`` (never raises)."""
    try:
        _logger.info(f"{ticker} | FMP:{endpoint} | {message}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

def _num(value):
    """Coerce to float, returning np.nan for None/blank/uncoercible values."""
    if value is None or value == "":
        return np.nan
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return np.nan
        return f
    except (TypeError, ValueError):
        return np.nan


def _safe_div(a, b):
    a, b = _num(a), _num(b)
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b


def _first(payload):
    """Return the first element of a list payload, else the payload/None."""
    if isinstance(payload, list):
        return payload[0] if payload else None
    return payload


class FMPStockDataFetcher:
    """Fetches and processes per-ticker stock data from Financial Modeling Prep.

    The public surface intentionally mirrors the previous yfinance-based
    ``StockDataFetcher`` so it is a drop-in replacement.
    """

    def __init__(self, rate_limit_delay: float = 0.0,
                 min_ticker_delay: float = 0.0,
                 max_ticker_delay: float = 0.0,
                 batch_size: int = 100,
                 batch_delay: float = 0.0,
                 use_cache: bool = True,
                 cache_max_age_hours: float = 24.0,
                 cache_db_path: str = "ticker_cache.db",
                 force_refresh: bool = False,
                 api_key: Optional[str] = None):
        """Initialize the FMP fetcher.

        The delay/batch arguments are accepted for interface compatibility with
        the yfinance fetcher but default to zero -- the Ultimate tier has no
        rate limits, so no throttling is required.

        Raises:
            RuntimeError: if no FMP API key is available.
        """
        self.api_key = api_key or FMP_API_KEY
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY environment variable not set")

        # Retained for interface parity (mostly unused with the Ultimate tier).
        self.rate_limit_delay = rate_limit_delay
        self.min_ticker_delay = min_ticker_delay
        self.max_ticker_delay = max_ticker_delay
        self.batch_size = max(1, batch_size)
        self.batch_delay = batch_delay

        # In-memory per-run cache (kept for parity with the old fetcher).
        self.cache = {}
        self.error_count = 0

        # Single shared session for all FMP calls (requirement 8).
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})

        # SQLite cross-run cache (requirement 5 -- unchanged behavior).
        self.use_cache = use_cache
        self.force_refresh = force_refresh
        self.cache_max_age_hours = cache_max_age_hours
        self.cache_db = None
        if use_cache and TickerCache is not None:
            try:
                self.cache_db = TickerCache(cache_db_path)
            except Exception as e:
                print(f"Could not open ticker cache ({e}); continuing without it.")
                self.cache_db = None

        # Extension hooks (parity with the yfinance fetcher).  When extended
        # data is requested we populate the extra fields natively from FMP.
        self.enable_extended = False
        self.voo_returns = None

    # ------------------------------------------------------------------
    # Cache variant + progress helpers (mirrors data_fetcher)
    # ------------------------------------------------------------------
    @property
    def cache_variant(self) -> str:
        """Namespace FMP data separately, and extended separately from base."""
        return 'fmp_ext' if self.enable_extended else 'fmp_base'

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

    # ------------------------------------------------------------------
    # Core HTTP
    # ------------------------------------------------------------------
    def _get(self, base: str, path: str, ticker: str, params: Optional[Dict] = None):
        """GET an FMP endpoint and return parsed JSON, or None on any problem.

        On non-200 responses (or network/parse errors) the failure is logged and
        None is returned so the caller can fall back to NaN for those fields.
        """
        url = f"{base}/{path}"
        query = {'apikey': self.api_key}
        if params:
            query.update(params)
        try:
            resp = self.session.get(url, params=query, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            _log(ticker, path, f"request error: {e}")
            return None
        if resp.status_code != 200:
            _log(ticker, path, f"HTTP {resp.status_code}")
            return None
        try:
            data = resp.json()
        except ValueError as e:
            _log(ticker, path, f"JSON parse error: {e}")
            return None
        # FMP returns {"Error Message": ...} on auth/quota problems with HTTP 200.
        if isinstance(data, dict) and ('Error Message' in data or 'error' in data):
            _log(ticker, path, str(data)[:200])
            return None
        return data

    # ==================================================================
    # Per-ticker fetch
    # ==================================================================
    def fetch_stock_data(self, ticker: str, period: str = "2y") -> Optional[Dict]:
        """Fetch and assemble the full per-ticker data dict from FMP.

        Returns the same base field structure the yfinance fetcher produced
        (plus extended fields when ``enable_extended`` is set), or None if the
        core quote/profile data is entirely unavailable.
        """
        # In-memory cache (1 hour) -- parity with old fetcher.
        cache_key = f"{ticker}_{self.cache_variant}"
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (datetime.now() - cache_time).seconds < 3600:
                return data

        quote = _first(self._get(V3_BASE, f"quote/{ticker}", ticker))
        profile = _first(self._get(V3_BASE, f"profile/{ticker}", ticker))

        # If we cannot even get a quote or profile, treat as a failed fetch.
        if not quote and not profile:
            _log(ticker, "quote/profile", "no core data returned")
            return None

        quote = quote or {}
        profile = profile or {}

        data: Dict = {'ticker': ticker}
        data.update(self._basic_info(ticker, quote, profile))
        data.update(self._revenue_growth(ticker))
        data.update(self._forward_estimates(ticker, quote))
        data.update(self._analyst_sentiment(ticker))

        if self.enable_extended:
            data.update(self._extended_fields(ticker, data, quote))

        self.cache[cache_key] = (datetime.now(), data)
        return data

    # ------------------------------------------------------------------
    # Basic info  -> /quote, /profile, /key-metrics
    # ------------------------------------------------------------------
    def _basic_info(self, ticker: str, quote: Dict, profile: Dict) -> Dict:
        km = _first(self._get(V3_BASE, f"key-metrics-ttm/{ticker}", ticker)) or {}
        ratios = _first(self._get(V3_BASE, f"ratios-ttm/{ticker}", ticker)) or {}

        # P/E: prefer quote.pe (trailing); forward handled separately.
        pe = _num(quote.get('pe'))
        if pd.isna(pe):
            pe = _num(km.get('peRatioTTM'))

        debt_to_equity = _num(km.get('debtToEquityTTM'))
        if pd.isna(debt_to_equity):
            debt_to_equity = _num(ratios.get('debtEquityRatioTTM'))
        # yfinance expressed D/E as a percentage-like number; FMP gives a ratio.
        if not pd.isna(debt_to_equity):
            debt_to_equity = debt_to_equity * 100

        roe = _num(km.get('roeTTM'))
        if pd.isna(roe):
            roe = _num(ratios.get('returnOnEquityTTM'))

        profit_margin = _num(ratios.get('netProfitMarginTTM'))

        return {
            'company_name': profile.get('companyName') or quote.get('name') or ticker,
            'sector': profile.get('sector') or 'Unknown',
            'industry': profile.get('industry') or 'Unknown',
            'market_cap': _num(quote.get('marketCap') if quote.get('marketCap') is not None
                               else profile.get('mktCap')),
            'current_price': _num(quote.get('price') if quote.get('price') is not None
                                  else profile.get('price')),
            'currency': profile.get('currency') or 'USD',
            'exchange': quote.get('exchange') or profile.get('exchangeShortName') or 'Unknown',
            'pe_ratio': pe,
            'peg_ratio': _num(km.get('pegRatioTTM') if km.get('pegRatioTTM') is not None
                              else ratios.get('priceEarningsToGrowthRatioTTM')),
            'price_to_book': _num(km.get('pbRatioTTM') if km.get('pbRatioTTM') is not None
                                  else ratios.get('priceToBookRatioTTM')),
            'debt_to_equity': debt_to_equity,
            'return_on_equity': roe,
            'profit_margin': profit_margin,
            '52_week_high': _num(quote.get('yearHigh')),
            '52_week_low': _num(quote.get('yearLow')),
            'average_volume': _num(quote.get('avgVolume')),
            'shares_outstanding': _num(quote.get('sharesOutstanding')),
        }

    # ------------------------------------------------------------------
    # Revenue growth  -> /income-statement (quarterly)
    # ------------------------------------------------------------------
    def _revenue_growth(self, ticker: str) -> Dict:
        out = {
            'revenue_growth_yoy': None,
            'revenue_growth_qoq': None,
            'latest_revenue': None,
            'revenue_ttm': None,
        }
        stmts = self._get(V3_BASE, f"income-statement/{ticker}",
                          ticker, {'period': 'quarter', 'limit': 8})
        if not isinstance(stmts, list) or not stmts:
            return out
        # FMP returns newest first.
        revenues = [_num(s.get('revenue')) for s in stmts]
        revenues = [r for r in revenues if not pd.isna(r)]
        if not revenues:
            return out

        out['latest_revenue'] = float(revenues[0])
        if len(revenues) >= 4:
            out['revenue_ttm'] = float(sum(revenues[:4]))
        if len(revenues) >= 5 and revenues[4] != 0:
            out['revenue_growth_yoy'] = round((revenues[0] - revenues[4]) / abs(revenues[4]) * 100, 2)
        if len(revenues) >= 2 and revenues[1] != 0:
            out['revenue_growth_qoq'] = round((revenues[0] - revenues[1]) / abs(revenues[1]) * 100, 2)
        return out

    # ------------------------------------------------------------------
    # Forward estimates  -> /analyst-estimates, /price-target-consensus
    # ------------------------------------------------------------------
    def _forward_estimates(self, ticker: str, quote: Dict) -> Dict:
        out = {
            'forward_revenue_estimate': None,
            'next_year_revenue_estimate': None,
            'forward_pe': None,
            'implied_earnings_growth': None,
            'target_mean_price': None,
            'target_high_price': None,
            'target_low_price': None,
            'recommendation_mean': None,
            'recommendation_key': None,
            'number_of_analysts': 0,
        }

        est = self._get(V3_BASE, f"analyst-estimates/{ticker}",
                        ticker, {'period': 'annual', 'limit': 2})
        if isinstance(est, list) and est:
            # Newest annual estimate first.
            cur = est[0]
            out['forward_revenue_estimate'] = _num(cur.get('estimatedRevenueAvg'))
            if len(est) >= 2:
                out['next_year_revenue_estimate'] = _num(est[1].get('estimatedRevenueAvg'))
            n_analysts = cur.get('numberAnalystEstimatedRevenue') or \
                cur.get('numberAnalystsEstimatedRevenue')
            out['number_of_analysts'] = int(_num(n_analysts)) if not pd.isna(_num(n_analysts)) else 0

            # Forward P/E from current price / forward EPS estimate.
            fwd_eps = _num(cur.get('estimatedEpsAvg'))
            price = _num(quote.get('price'))
            out['forward_pe'] = _safe_div(price, fwd_eps)

            # Implied earnings growth from this year's vs next year's EPS est.
            if len(est) >= 2:
                eps0 = _num(est[0].get('estimatedEpsAvg'))
                eps1 = _num(est[1].get('estimatedEpsAvg'))
                if not pd.isna(eps0) and not pd.isna(eps1) and eps0 != 0:
                    out['implied_earnings_growth'] = round((eps1 - eps0) / abs(eps0) * 100, 2)

        # Price targets from the consensus endpoint (v4).
        ptc = _first(self._get(V4_BASE, "price-target-consensus", ticker, {'symbol': ticker}))
        if isinstance(ptc, dict):
            out['target_mean_price'] = _num(ptc.get('targetConsensus'))
            out['target_high_price'] = _num(ptc.get('targetHigh'))
            out['target_low_price'] = _num(ptc.get('targetLow'))

        return out

    # ------------------------------------------------------------------
    # Analyst sentiment  -> /analyst-stock-recommendations, /grade
    # ------------------------------------------------------------------
    def _analyst_sentiment(self, ticker: str) -> Dict:
        out = {
            'analyst_buy_percent': None,
            'analyst_hold_percent': None,
            'analyst_sell_percent': None,
            'recent_upgrades': 0,
            'recent_downgrades': 0,
        }

        recs = self._get(V3_BASE, f"analyst-stock-recommendations/{ticker}", ticker)
        latest = _first(recs)
        if isinstance(latest, dict):
            strong_buy = _num(latest.get('analystRatingsStrongBuy'))
            buy = _num(latest.get('analystRatingsbuy'))
            hold = _num(latest.get('analystRatingsHold'))
            sell = _num(latest.get('analystRatingsSell'))
            strong_sell = _num(latest.get('analystRatingsStrongSell'))
            vals = [strong_buy, buy, hold, sell, strong_sell]
            vals = [0.0 if pd.isna(v) else v for v in vals]
            total = sum(vals)
            if total > 0:
                buys = vals[0] + vals[1]
                holds = vals[2]
                sells = vals[3] + vals[4]
                out['analyst_buy_percent'] = round(buys / total * 100, 1)
                out['analyst_hold_percent'] = round(holds / total * 100, 1)
                out['analyst_sell_percent'] = round(sells / total * 100, 1)
                # Approximate a 1(strong buy)-5(strong sell) recommendation mean.
                weighted = (vals[0] * 1 + vals[1] * 2 + vals[2] * 3 +
                            vals[3] * 4 + vals[4] * 5)
                mean = weighted / total
                out['recommendation_mean'] = round(mean, 2)
                out['recommendation_key'] = self._rec_key(mean)

        # Recent upgrades/downgrades from the grade endpoint (last 90 days).
        grades = self._get(V3_BASE, f"grade/{ticker}", ticker, {'limit': 100})
        if isinstance(grades, list) and grades:
            cutoff = datetime.now() - timedelta(days=90)
            ups = downs = 0
            for g in grades:
                try:
                    gdate = datetime.strptime(g.get('date', '')[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    continue
                if gdate < cutoff:
                    continue
                prev = self._grade_rank(g.get('previousGrade'))
                new = self._grade_rank(g.get('newGrade'))
                if prev is None or new is None:
                    continue
                # Lower rank number == more bullish, so a drop in rank = upgrade.
                if new < prev:
                    ups += 1
                elif new > prev:
                    downs += 1
            out['recent_upgrades'] = ups
            out['recent_downgrades'] = downs

        return out

    @staticmethod
    def _rec_key(mean: float) -> str:
        if mean <= 1.5:
            return 'strong_buy'
        if mean <= 2.5:
            return 'buy'
        if mean <= 3.5:
            return 'hold'
        if mean <= 4.5:
            return 'sell'
        return 'strong_sell'

    @staticmethod
    def _grade_rank(grade: Optional[str]) -> Optional[int]:
        """Map a textual analyst grade to a bullishness rank (1=most bullish)."""
        if not grade:
            return None
        g = str(grade).strip().lower()
        ranking = {
            'strong buy': 1, 'conviction buy': 1, 'buy': 2, 'outperform': 2,
            'overweight': 2, 'accumulate': 2, 'add': 2, 'positive': 2,
            'market outperform': 2, 'sector outperform': 2,
            'hold': 3, 'neutral': 3, 'equal-weight': 3, 'equal weight': 3,
            'market perform': 3, 'sector perform': 3, 'in-line': 3, 'peer perform': 3,
            'underperform': 4, 'underweight': 4, 'reduce': 4, 'negative': 4,
            'sector underperform': 4, 'market underperform': 4,
            'sell': 5, 'strong sell': 5,
        }
        return ranking.get(g)

    # ==================================================================
    # Extended fields (Groups A-E equivalents) -- populated only when
    # enable_extended is set.  Field names match screener_extension so they
    # flow straight into the output CSV / scoring.
    # ==================================================================
    def _extended_fields(self, ticker: str, base: Dict, quote: Dict) -> Dict:
        out: Dict = {}
        revenue_ttm = base.get('revenue_ttm')
        market_cap = base.get('market_cap')
        current_price = base.get('current_price')

        # ---- Income statement (annual) : margins, EBITDA, R&D ----
        inc = self._get(V3_BASE, f"income-statement/{ticker}",
                        ticker, {'period': 'annual', 'limit': 2})
        inc0 = inc[0] if isinstance(inc, list) and len(inc) >= 1 else {}
        inc1 = inc[1] if isinstance(inc, list) and len(inc) >= 2 else {}

        gm0 = _safe_div(inc0.get('grossProfit'), inc0.get('revenue'))
        gm1 = _safe_div(inc1.get('grossProfit'), inc1.get('revenue'))
        out['gross_margin'] = gm0
        out['gross_margin_prior_yr'] = gm1
        out['gross_margin_expansion'] = (gm0 - gm1) if not pd.isna(gm0) and not pd.isna(gm1) else np.nan
        out['ebitda_ttm'] = _num(inc0.get('ebitda'))
        out['rd_ratio'] = _safe_div(inc0.get('researchAndDevelopmentExpenses'), inc0.get('revenue'))

        # ---- Cash flow : OCF, capex, FCF ----
        cf = self._get(V3_BASE, f"cash-flow-statement/{ticker}",
                       ticker, {'period': 'annual', 'limit': 2})
        cf0 = cf[0] if isinstance(cf, list) and len(cf) >= 1 else {}
        cf1 = cf[1] if isinstance(cf, list) and len(cf) >= 2 else {}

        ocf = _num(cf0.get('operatingCashFlow') if cf0.get('operatingCashFlow') is not None
                   else cf0.get('netCashProvidedByOperatingActivities'))
        capex = _num(cf0.get('capitalExpenditure'))
        fcf = _num(cf0.get('freeCashFlow'))
        if pd.isna(fcf) and not pd.isna(ocf) and not pd.isna(capex):
            fcf = ocf - abs(capex)
        out['operating_cashflow'] = ocf
        out['fcf_ttm'] = fcf
        out['fcf_margin'] = _safe_div(fcf, revenue_ttm)
        out['fcf_yield'] = _safe_div(fcf, market_cap)
        out['capex_intensity'] = _safe_div(abs(capex) if not pd.isna(capex) else np.nan, revenue_ttm)

        # FCF growth YoY
        ocf1 = _num(cf1.get('operatingCashFlow') if cf1.get('operatingCashFlow') is not None
                    else cf1.get('netCashProvidedByOperatingActivities'))
        capex1 = _num(cf1.get('capitalExpenditure'))
        fcf1 = _num(cf1.get('freeCashFlow'))
        if pd.isna(fcf1) and not pd.isna(ocf1) and not pd.isna(capex1):
            fcf1 = ocf1 - abs(capex1)
        if not pd.isna(fcf) and not pd.isna(fcf1) and fcf1 != 0:
            out['fcf_growth_yoy'] = round((fcf - fcf1) / abs(fcf1) * 100, 2)
        else:
            out['fcf_growth_yoy'] = np.nan

        # Earnings quality ratio = OCF / net income
        net_income = _num(inc0.get('netIncome'))
        if not pd.isna(ocf) and not pd.isna(net_income) and net_income != 0:
            out['earnings_quality_ratio'] = max(-5.0, min(5.0, ocf / net_income))
        else:
            out['earnings_quality_ratio'] = np.nan

        # Rule of 40
        rg = base.get('revenue_growth_yoy')
        if rg is not None and not pd.isna(_num(rg)) and not pd.isna(out['fcf_margin']):
            out['rule_of_40'] = _num(rg) + out['fcf_margin'] * 100
        else:
            out['rule_of_40'] = np.nan

        # ---- Scoring-overhaul derived factors (no new fetches) ----
        # Net margin trend: current vs prior-year net margin (from inc0/inc1).
        nm0 = _safe_div(inc0.get('netIncome'), inc0.get('revenue'))
        nm1 = _safe_div(inc1.get('netIncome'), inc1.get('revenue'))
        out['net_margin_trend'] = (nm0 - nm1) if not pd.isna(nm0) and not pd.isna(nm1) else np.nan

        # Shareholder yield + net buyback yield from cash flow + market cap.
        # dividendsPaid / commonStockRepurchased are reported as negative outflows.
        div_paid = _num(cf0.get('dividendsPaid'))
        buyback = _num(cf0.get('commonStockRepurchased'))
        if not pd.isna(market_cap) and market_cap and market_cap > 0:
            div_amt = abs(div_paid) if not pd.isna(div_paid) else 0.0
            bb_amt = abs(buyback) if not pd.isna(buyback) else 0.0
            out['net_buyback_yield'] = bb_amt / market_cap
            out['shareholder_yield'] = (div_amt + bb_amt) / market_cap
        else:
            out['net_buyback_yield'] = np.nan
            out['shareholder_yield'] = np.nan

        # Factors that require data not currently fetched (balance sheet,
        # estimate-revision history, multi-quarter institutional ownership).
        # Kept as explicit NaN placeholders so the schema is stable and the
        # scoring engine simply excludes them per-ticker until populated.
        for _ph in ('revenue_estimate_revision', 'asset_growth',
                    'institutional_ownership_change', 'debt_trend'):
            out.setdefault(_ph, np.nan)

        # ---- Valuation extras ----
        km = _first(self._get(V3_BASE, f"key-metrics-ttm/{ticker}", ticker)) or {}
        out['price_to_sales'] = _num(km.get('priceToSalesRatioTTM'))
        out['ev_ebitda'] = _num(km.get('enterpriseValueOverEBITDATTM'))

        # ---- EPS estimates / revisions (quarterly) ----
        qest = self._get(V3_BASE, f"analyst-estimates/{ticker}",
                         ticker, {'period': 'quarter', 'limit': 2})
        if isinstance(qest, list) and qest:
            out['eps_estimate_current_qtr'] = _num(qest[0].get('estimatedEpsAvg'))
            if len(qest) >= 2:
                out['eps_estimate_next_qtr'] = _num(qest[1].get('estimatedEpsAvg'))
            else:
                out['eps_estimate_next_qtr'] = np.nan
        else:
            out['eps_estimate_current_qtr'] = np.nan
            out['eps_estimate_next_qtr'] = np.nan
        # FMP does not expose 30-day revision counts; leave as NaN.
        out['eps_revision_up_30d'] = np.nan
        out['eps_revision_down_30d'] = np.nan
        out['eps_revision_net'] = np.nan

        # ---- Earnings surprises ----
        out.update(self._earnings_surprises(ticker))

        # ---- Institutional ownership ----
        out['institutional_ownership_pct'] = self._institutional_ownership(ticker, base)

        # ---- Short interest ----
        out.update(self._short_interest(ticker))

        # ---- Insider transactions (last 90 days) ----
        out.update(self._insider_transactions(ticker))

        # ---- Technicals (200d MA, relative strength, volume ratio) ----
        out.update(self._technicals(ticker, base, quote))

        return out

    def _earnings_surprises(self, ticker: str) -> Dict:
        out = {'earnings_surprise_avg': np.nan, 'earnings_beat_rate': np.nan}
        es = self._get(V3_BASE, f"earnings-surprises/{ticker}", ticker)
        if not isinstance(es, list) or not es:
            return out
        last4 = es[:4]
        surprises, beats, count = [], 0, 0
        for e in last4:
            actual = _num(e.get('actualEarningResult'))
            est = _num(e.get('estimatedEarning'))
            if pd.isna(actual) or pd.isna(est) or est == 0:
                continue
            surprises.append((actual - est) / abs(est) * 100)
            beats += 1 if actual > est else 0
            count += 1
        if count:
            out['earnings_surprise_avg'] = round(float(np.mean(surprises)), 2)
            out['earnings_beat_rate'] = round(beats / count * 100, 1)
        return out

    def _institutional_ownership(self, ticker: str, base: Dict):
        # Preferred: v4 symbol-ownership gives a direct percentage.
        own = _first(self._get(V4_BASE, "institutional-ownership/symbol-ownership",
                               ticker, {'symbol': ticker, 'includeCurrentQuarter': 'true'}))
        if isinstance(own, dict):
            pct = _num(own.get('ownershipPercent') or own.get('investorsHolding'))
            if not pd.isna(_num(own.get('ownershipPercent'))):
                # Expressed as a percent (e.g. 65.3) -> store as decimal.
                return _num(own.get('ownershipPercent')) / 100

        # Fallback: sum holder shares / shares outstanding from /institutional-holder.
        holders = self._get(V3_BASE, f"institutional-holder/{ticker}", ticker)
        shares_out = _num(base.get('shares_outstanding'))
        if isinstance(holders, list) and holders and not pd.isna(shares_out) and shares_out > 0:
            total_held = sum(_num(h.get('shares')) for h in holders
                             if not pd.isna(_num(h.get('shares'))))
            if total_held > 0:
                return min(1.0, total_held / shares_out)
        return np.nan

    def _short_interest(self, ticker: str) -> Dict:
        out = {'short_interest_pct_float': np.nan, 'short_ratio': np.nan}
        sv = _first(self._get(V4_BASE, "short-volume", ticker, {'symbol': ticker}))
        if isinstance(sv, dict):
            # Short-volume endpoints vary; map what is present, else leave NaN.
            out['short_interest_pct_float'] = _num(sv.get('shortInterestPercentFloat'))
            out['short_ratio'] = _num(sv.get('shortRatio') or sv.get('daysToCover'))
        return out

    def _insider_transactions(self, ticker: str) -> Dict:
        out = {'insider_buy_3m': 0, 'insider_sell_3m': 0, 'insider_net_3m': 0}
        trades = self._get(V4_BASE, "insider-trading", ticker,
                           {'symbol': ticker, 'page': 0})
        if not isinstance(trades, list) or not trades:
            return out
        cutoff = datetime.now() - timedelta(days=90)
        buys = sells = 0
        for t in trades:
            try:
                tdate = datetime.strptime(str(t.get('transactionDate', ''))[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            if tdate < cutoff:
                continue
            ttype = str(t.get('transactionType', '')).upper()
            acq = str(t.get('acquistionOrDisposition', t.get('acquisitionOrDisposition', ''))).upper()
            # 'P' = purchase, 'S' = sale; 'A' = acquired, 'D' = disposed.
            if ttype.startswith('P') or acq == 'A':
                buys += 1
            elif ttype.startswith('S') or acq == 'D':
                sells += 1
        out['insider_buy_3m'] = buys
        out['insider_sell_3m'] = sells
        out['insider_net_3m'] = buys - sells
        return out

    def _technicals(self, ticker: str, base: Dict, quote: Dict) -> Dict:
        out = {
            'ma_200d': np.nan, 'pct_above_200d_ma': np.nan,
            'relative_strength_vs_voo_12m': np.nan,
            'relative_strength_vs_voo_6m': np.nan,
            'relative_strength_vs_voo_3m': np.nan,
            'volume_ratio_20d': np.nan,
            'momentum_12_1': np.nan,
        }
        current_price = _num(base.get('current_price'))

        # 200d MA is available directly on the quote.
        ma200 = _num(quote.get('priceAvg200'))
        out['ma_200d'] = ma200
        if not pd.isna(ma200) and ma200 != 0 and not pd.isna(current_price):
            out['pct_above_200d_ma'] = (current_price - ma200) / ma200 * 100

        hist = self._get(V3_BASE, f"historical-price-full/{ticker}",
                         ticker, {'timeseries': 400})
        closes = self._closes_from_history(hist)
        if closes is not None and len(closes) >= 2:
            # 12-1 momentum: price return from ~12 months ago to ~1 month ago
            # (excludes the most recent month to avoid short-term reversal).
            p12 = self._price_at(closes, 12)
            p1 = self._price_at(closes, 1)
            if not pd.isna(p12) and p12 != 0 and not pd.isna(p1):
                out['momentum_12_1'] = round((p1 / p12 - 1.0) * 100, 2)

            # Relative strength vs VOO if benchmark returns were preloaded.
            if self.voo_returns:
                for months, key, voo_key in [
                    (12, 'relative_strength_vs_voo_12m', 'voo_return_12m'),
                    (6, 'relative_strength_vs_voo_6m', 'voo_return_6m'),
                    (3, 'relative_strength_vs_voo_3m', 'voo_return_3m'),
                ]:
                    r = self._period_return(closes, months)
                    voo_r = _num(self.voo_returns.get(voo_key))
                    if not pd.isna(r) and not pd.isna(voo_r):
                        out[key] = round(r - voo_r, 2)

            # 20-day volume ratio vs average volume.
            volumes = self._volumes_from_history(hist)
            avg_vol = _num(base.get('average_volume'))
            if volumes is not None and len(volumes) >= 1 and not pd.isna(avg_vol) and avg_vol > 0:
                recent = np.mean(volumes[:20])
                out['volume_ratio_20d'] = round(float(recent) / avg_vol, 2)
        return out

    @staticmethod
    def _closes_from_history(hist) -> Optional[pd.Series]:
        if not isinstance(hist, dict):
            return None
        rows = hist.get('historical')
        if not isinstance(rows, list) or not rows:
            return None
        try:
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            return pd.Series(df['close'].astype(float).values, index=df['date'].values)
        except Exception:
            return None

    @staticmethod
    def _volumes_from_history(hist) -> Optional[list]:
        if not isinstance(hist, dict):
            return None
        rows = hist.get('historical')
        if not isinstance(rows, list) or not rows:
            return None
        try:
            # rows are newest-first from FMP; volume[0] == most recent day.
            return [float(r.get('volume', 0)) for r in rows]
        except Exception:
            return None

    @staticmethod
    def _price_at(closes: pd.Series, months: int) -> float:
        """Close price as of ~``months`` months ago (last on/before the cutoff)."""
        if closes is None or closes.empty:
            return np.nan
        cutoff = pd.Timestamp(closes.index[-1]) - pd.DateOffset(months=months)
        past = closes[closes.index <= cutoff]
        return float(past.iloc[-1]) if not past.empty else float(closes.iloc[0])

    @staticmethod
    def _period_return(closes: pd.Series, months: int) -> float:
        if closes is None or len(closes) < 2:
            return np.nan
        closes = closes.dropna()
        if closes.empty:
            return np.nan
        end = float(closes.iloc[-1])
        cutoff = pd.Timestamp(closes.index[-1]) - pd.DateOffset(months=months)
        past = closes[closes.index <= cutoff]
        start = float(past.iloc[-1]) if not past.empty else float(closes.iloc[0])
        if start == 0:
            return np.nan
        return (end / start - 1.0) * 100.0

    # ==================================================================
    # Batch fetch (cache-aware, ETA-capable) -- mirrors data_fetcher
    # ==================================================================
    def fetch_batch_data(self, tickers: List[str], progress_callback=None) -> pd.DataFrame:
        """Fetch many tickers, serving fresh ones from the SQLite cache.

        With the Ultimate tier there is no rate limiting, so no inter-ticker or
        inter-batch delays are applied; the cache still prevents redundant
        same-day refetches and the progress callback still reports an ETA.
        """
        results = []
        total = len(tickers)

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
                  f"fetching {len(to_fetch)} from FMP.")
            if progress_callback:
                last_cached = next((t for t in tickers if t in cached_map), tickers[0])
                self._report(progress_callback, cached_count, total, last_cached, 0.0)

        start_time = time.time()
        fetched = 0
        for ticker in to_fetch:
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

            elapsed = time.time() - start_time
            rate = fetched / elapsed if elapsed > 0 else 0
            remaining = len(to_fetch) - fetched
            eta = (remaining / rate) if rate > 0 else None
            self._report(progress_callback, current, total, ticker, eta)

            if self.max_ticker_delay > 0 and fetched < len(to_fetch):
                time.sleep(self.min_ticker_delay)

        return pd.DataFrame(results)


if __name__ == "__main__":
    # Quick coverage validation (requirement 9).
    import sys

    test_tickers = ['NVDA', 'AAPL', 'MSFT', 'JPM', 'VST']
    print("=== FMP Fetcher Validation ===")
    try:
        fetcher = FMPStockDataFetcher(use_cache=False)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Core fields we expect populated for compatibility with screener.py/app.py.
    core_fields = [
        'company_name', 'sector', 'industry', 'market_cap', 'current_price',
        'pe_ratio', 'peg_ratio', 'price_to_book', 'debt_to_equity',
        'return_on_equity', 'profit_margin', '52_week_high', '52_week_low',
        'average_volume', 'shares_outstanding', 'revenue_growth_yoy',
        'revenue_growth_qoq', 'revenue_ttm', 'forward_pe',
        'forward_revenue_estimate', 'target_mean_price', 'recommendation_key',
        'number_of_analysts', 'analyst_buy_percent', 'recent_upgrades',
    ]

    rows = {}
    for tk in test_tickers:
        data = fetcher.fetch_stock_data(tk) or {}
        rows[tk] = data

    # Print a coverage table: field -> per-ticker populated? (Y/·)
    header = "field".ljust(28) + "".join(t.rjust(8) for t in test_tickers)
    print(header)
    print("-" * len(header))
    for f in core_fields:
        cells = ""
        for tk in test_tickers:
            v = rows[tk].get(f)
            ok = v is not None and not (isinstance(v, float) and pd.isna(v))
            cells += ("Y" if ok else "·").rjust(8)
        print(f.ljust(28) + cells)

    # Per-ticker summary
    print("\nPer-ticker core coverage:")
    for tk in test_tickers:
        populated = sum(
            1 for f in core_fields
            if rows[tk].get(f) is not None
            and not (isinstance(rows[tk].get(f), float) and pd.isna(rows[tk].get(f)))
        )
        print(f"  {tk}: {populated}/{len(core_fields)} core fields populated")
