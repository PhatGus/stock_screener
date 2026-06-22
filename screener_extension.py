"""
Screener Extension Module
=========================

Adds new data fields and an updated composite score to the existing stock
screener WITHOUT rewriting the existing screener logic.

The module is split into four concerns:

1. Per-ticker field fetching (Groups A-E) -- :func:`fetch_extended_fields`.
   These are appended to the per-ticker dict built in
   ``StockDataFetcher.fetch_stock_data`` (see the small hook there).

2. A one-time VOO benchmark preload (:func:`fetch_voo_returns`) used for the
   relative-strength calculations.  This is fetched ONCE before the ticker loop
   and passed into every per-ticker fetch.

3. Rule-based macro sensitivity tags (Group F) -- :func:`apply_macro_tags`.
   These operate on the final DataFrame as a post-processing step.

4. The updated composite score (:func:`apply_extended_scoring`) which adds three
   new sub-scores (earnings quality, FCF, moat), rebalances the existing five
   sub-scores by 65/100, and stores the pre-rebalance values as ``*_score_v1``.

All new fields are wrapped in try/except.  On any exception the field is set to
NaN (or 0 for insider transaction counts) and a line is written to
``screener_errors.log`` with the format ``TICKER | field_group | error message``.
"""

import logging
import math
import time
from typing import Dict, Optional

import numpy as np
import pandas as pd

try:  # yfinance is the primary data source; imported lazily-safe
    import yfinance as yf
except Exception:  # pragma: no cover - import guard only
    yf = None


# ---------------------------------------------------------------------------
# Error logging
# ---------------------------------------------------------------------------

ERROR_LOG_FILE = "screener_errors.log"

_logger = logging.getLogger("screener_extension")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.FileHandler(ERROR_LOG_FILE)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def log_error(ticker: str, field_group: str, message: str) -> None:
    """Write a fetch/compute failure to ``screener_errors.log``.

    Format: ``TICKER | field_group | error message``
    """
    try:
        _logger.info(f"{ticker} | {field_group} | {message}")
    except Exception:
        pass  # logging must never break the screener


# Hardcoded tag sets (Group F)
AI_INFRA_TICKERS = {
    'NVDA', 'AVGO', 'AMD', 'ANET', 'CRDO', 'CLS', 'COHR', 'MU',
    'WDC', 'STX', 'LRCX', 'MRVL', 'ADI', 'APH', 'MPWR', 'DIOD',
}
AI_INFRA_INDUSTRIES = {'Semiconductors', 'Electronic Components'}
EM_FX_TICKERS = {'MELI', 'GRAB', 'DLO', 'GLBE', 'FUTU'}

# Benchmark FCF yield used by the FCF sub-score (~3.5% for VOO / S&P 500)
VOO_FCF_YIELD_BENCHMARK = 0.035


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _rl_retry(fn, ticker: str, group: str):
    """Call ``fn``; on a yfinance rate-limit error back off 10s and retry once.

    Returns the function result, or raises the final exception so the caller's
    try/except can record a NaN for the field group.
    """
    try:
        return fn()
    except Exception as e:
        if "429" in str(e) or "Too Many Requests" in str(e).lower() or "rate" in str(e).lower():
            log_error(ticker, group, f"rate limited, backing off 10s: {e}")
            time.sleep(10)
            return fn()  # retry once; let any exception propagate to caller
        raise


def _row_value(df: pd.DataFrame, labels, col_idx: int = 0):
    """Return ``df.loc[label].iloc[col_idx]`` for the first matching label.

    ``labels`` may be a single string or an iterable of candidate row labels
    (yfinance uses slightly different labels across versions).  Returns NaN when
    no label matches or the value is missing.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return np.nan
    if isinstance(labels, str):
        labels = [labels]
    for label in labels:
        if label in df.index:
            try:
                val = df.loc[label].iloc[col_idx]
                if pd.notna(val):
                    return float(val)
            except Exception:
                continue
    return np.nan


def _period_return(close: pd.Series, months: int) -> float:
    """Percentage price return over the trailing ``months`` window."""
    if close is None or len(close) < 2:
        return np.nan
    close = close.dropna()
    if close.empty:
        return np.nan
    end_price = float(close.iloc[-1])
    cutoff = close.index[-1] - pd.DateOffset(months=months)
    past = close[close.index <= cutoff]
    start_price = float(past.iloc[-1]) if not past.empty else float(close.iloc[0])
    if start_price == 0:
        return np.nan
    return (end_price / start_price - 1.0) * 100.0


# ---------------------------------------------------------------------------
# One-time VOO benchmark preload
# ---------------------------------------------------------------------------

def fetch_voo_returns(rate_limit_delay: float = 0.5) -> Dict[str, float]:
    """Fetch VOO price history ONCE and compute 12/6/3-month returns.

    Called before the ticker loop; the result is passed into every per-ticker
    extended fetch for the relative-strength calculations.
    """
    result = {
        'voo_return_12m': np.nan,
        'voo_return_6m': np.nan,
        'voo_return_3m': np.nan,
    }
    if yf is None:
        log_error('VOO', 'benchmark', 'yfinance not available')
        return result
    try:
        voo = yf.Ticker('VOO')
        hist = _rl_retry(lambda: voo.history(period='1y'), 'VOO', 'benchmark')
        time.sleep(rate_limit_delay)
        if hist is None or hist.empty or 'Close' not in hist:
            log_error('VOO', 'benchmark', 'empty history')
            return result
        close = hist['Close']
        result['voo_return_12m'] = _period_return(close, 12)
        result['voo_return_6m'] = _period_return(close, 6)
        result['voo_return_3m'] = _period_return(close, 3)
    except Exception as e:
        log_error('VOO', 'benchmark', str(e))
    return result


# ---------------------------------------------------------------------------
# Per-ticker extended field fetch (Groups A-E)
# ---------------------------------------------------------------------------

# All new per-ticker columns, used to guarantee the keys always exist.
EXTENDED_FIELDS = [
    # Group A
    'eps_estimate_current_qtr', 'eps_estimate_next_qtr',
    'eps_revision_up_30d', 'eps_revision_down_30d', 'eps_revision_net',
    'earnings_surprise_avg', 'earnings_beat_rate',
    'operating_cashflow', 'fcf_ttm', 'earnings_quality_ratio',
    # Group B
    'fcf_margin', 'fcf_yield', 'capex_intensity', 'fcf_growth_yoy', 'rule_of_40',
    # Group C
    'gross_margin', 'gross_margin_prior_yr', 'gross_margin_expansion',
    'ebitda_ttm', 'ev_ebitda', 'price_to_sales', 'rd_ratio',
    # Group D
    'institutional_ownership_pct', 'short_interest_pct_float', 'short_ratio',
    'insider_buy_3m', 'insider_sell_3m', 'insider_net_3m',
    # Group E
    'ma_200d', 'pct_above_200d_ma',
    'relative_strength_vs_voo_12m', 'relative_strength_vs_voo_6m',
    'relative_strength_vs_voo_3m', 'volume_ratio_20d',
]


def fetch_extended_fields(stock, data: Dict, voo_returns: Optional[Dict],
                          ticker: str, rate_limit_delay: float = 0.5) -> Dict:
    """Fetch all Group A-E fields for a single ticker.

    ``stock`` is the already-constructed ``yf.Ticker`` object from the existing
    fetch loop; ``data`` is the per-ticker dict already populated with the
    existing fields (used for ``revenue_ttm``, ``market_cap``, ``current_price``).

    Every field is wrapped so a failure yields NaN (0 for insider counts) and a
    logged error rather than aborting the ticker.
    """
    # Initialise every field so the output row always has the columns.
    out = {f: np.nan for f in EXTENDED_FIELDS}
    out['insider_buy_3m'] = 0
    out['insider_sell_3m'] = 0
    out['insider_net_3m'] = 0

    # Rate limiting between ticker fetches for the new data groups.
    time.sleep(rate_limit_delay)

    info = {}
    try:
        info = stock.info or {}
    except Exception as e:
        log_error(ticker, 'info', str(e))
        info = {}

    revenue_ttm = data.get('revenue_ttm')
    market_cap = data.get('market_cap')
    current_price = data.get('current_price')

    # ---- shared financial statements (fetched once, reused across groups) ----
    cashflow = None
    financials = None
    try:
        cashflow = _rl_retry(lambda: stock.cashflow, ticker, 'cashflow')
    except Exception as e:
        log_error(ticker, 'cashflow', str(e))
    try:
        financials = _rl_retry(lambda: stock.financials, ticker, 'financials')
    except Exception as e:
        log_error(ticker, 'financials', str(e))

    # =====================================================================
    # Group A: Earnings Quality & Estimate Revision Momentum
    # =====================================================================
    # EPS consensus estimates
    try:
        est = _rl_retry(lambda: stock.earnings_estimate, ticker, 'earnings_estimate')
        if isinstance(est, pd.DataFrame) and not est.empty and 'avg' in est.columns:
            if '0q' in est.index:
                out['eps_estimate_current_qtr'] = float(est.loc['0q', 'avg'])
            if '+1q' in est.index:
                out['eps_estimate_next_qtr'] = float(est.loc['+1q', 'avg'])
        # Fallback for current-quarter estimate from info
        if pd.isna(out['eps_estimate_current_qtr']):
            fwd_eps = info.get('forwardEps')
            if fwd_eps is not None:
                out['eps_estimate_current_qtr'] = float(fwd_eps)
    except Exception as e:
        log_error(ticker, 'eps_estimate', str(e))

    # EPS revisions (last 30 days)
    try:
        rev = _rl_retry(lambda: stock.eps_revisions, ticker, 'eps_revisions')
        if isinstance(rev, pd.DataFrame) and not rev.empty:
            row = rev.loc['0q'] if '0q' in rev.index else rev.iloc[0]
            up = row.get('upLast30days', row.get('upLast30Days', np.nan))
            down = row.get('downLast30days', row.get('downLast30Days', np.nan))
            if pd.notna(up):
                out['eps_revision_up_30d'] = float(up)
            if pd.notna(down):
                out['eps_revision_down_30d'] = float(down)
            if pd.notna(out['eps_revision_up_30d']) and pd.notna(out['eps_revision_down_30d']):
                out['eps_revision_net'] = out['eps_revision_up_30d'] - out['eps_revision_down_30d']
    except Exception as e:
        log_error(ticker, 'eps_revisions', str(e))

    # Earnings surprise / beat rate over last 4 quarters
    try:
        hist = _rl_retry(lambda: stock.earnings_history, ticker, 'earnings_history')
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            est_col = 'epsEstimate' if 'epsEstimate' in hist.columns else None
            act_col = 'epsActual' if 'epsActual' in hist.columns else None
            if est_col and act_col:
                last4 = hist.tail(4)
                surprises = []
                beats = 0
                count = 0
                for _, r in last4.iterrows():
                    e_est = r.get(est_col)
                    e_act = r.get(act_col)
                    if pd.notna(e_est) and pd.notna(e_act) and e_est != 0:
                        surprises.append((e_act - e_est) / abs(e_est) * 100.0)
                        beats += 1 if e_act > e_est else 0
                        count += 1
                if count > 0:
                    out['earnings_surprise_avg'] = float(np.mean(surprises))
                    out['earnings_beat_rate'] = beats / count * 100.0
    except Exception as e:
        log_error(ticker, 'earnings_history', str(e))

    # Operating cash flow, FCF, earnings quality ratio
    capex = np.nan
    try:
        op_cf = _row_value(cashflow, ['Operating Cash Flow',
                                      'Total Cash From Operating Activities',
                                      'Cash Flow From Continuing Operating Activities'], 0)
        out['operating_cashflow'] = op_cf
        capex = _row_value(cashflow, ['Capital Expenditure', 'Capital Expenditures'], 0)
        if pd.notna(op_cf) and pd.notna(capex):
            out['fcf_ttm'] = op_cf - abs(capex)
    except Exception as e:
        log_error(ticker, 'operating_cashflow', str(e))

    try:
        net_income_ttm = _row_value(financials, ['Net Income',
                                                 'Net Income Common Stockholders',
                                                 'Net Income From Continuing Operation Net Minority Interest'], 0)
        op_cf = out['operating_cashflow']
        if pd.notna(op_cf) and pd.notna(net_income_ttm):
            if net_income_ttm == 0:
                out['earnings_quality_ratio'] = np.nan
            else:
                ratio = op_cf / net_income_ttm
                out['earnings_quality_ratio'] = max(-5.0, min(5.0, ratio))
    except Exception as e:
        log_error(ticker, 'earnings_quality_ratio', str(e))

    # =====================================================================
    # Group B: Free Cash Flow Metrics
    # =====================================================================
    try:
        fcf = out['fcf_ttm']
        if pd.notna(fcf) and revenue_ttm and revenue_ttm != 0:
            out['fcf_margin'] = fcf / revenue_ttm
        if pd.notna(fcf) and market_cap and market_cap != 0:
            out['fcf_yield'] = fcf / market_cap
        if pd.notna(capex) and revenue_ttm and revenue_ttm != 0:
            out['capex_intensity'] = abs(capex) / revenue_ttm
    except Exception as e:
        log_error(ticker, 'fcf_metrics', str(e))

    # FCF growth YoY (most recent annual FCF vs prior year)
    try:
        op_cf_0 = _row_value(cashflow, ['Operating Cash Flow',
                                        'Total Cash From Operating Activities'], 0)
        op_cf_1 = _row_value(cashflow, ['Operating Cash Flow',
                                        'Total Cash From Operating Activities'], 1)
        capex_0 = _row_value(cashflow, ['Capital Expenditure', 'Capital Expenditures'], 0)
        capex_1 = _row_value(cashflow, ['Capital Expenditure', 'Capital Expenditures'], 1)
        if pd.notna(op_cf_0) and pd.notna(capex_0) and pd.notna(op_cf_1) and pd.notna(capex_1):
            fcf_0 = op_cf_0 - abs(capex_0)
            fcf_1 = op_cf_1 - abs(capex_1)
            if fcf_1 != 0:
                out['fcf_growth_yoy'] = (fcf_0 - fcf_1) / abs(fcf_1) * 100.0
    except Exception as e:
        log_error(ticker, 'fcf_growth_yoy', str(e))

    # Rule of 40 (revenue growth + fcf margin %)
    try:
        rev_growth = data.get('revenue_growth_yoy')
        if pd.notna(rev_growth) and pd.notna(out['fcf_margin']):
            out['rule_of_40'] = rev_growth + out['fcf_margin'] * 100.0
    except Exception as e:
        log_error(ticker, 'rule_of_40', str(e))

    # =====================================================================
    # Group C: Gross Margin & Moat Proxies
    # =====================================================================
    try:
        gp_0 = _row_value(financials, ['Gross Profit'], 0)
        tr_0 = _row_value(financials, ['Total Revenue', 'Operating Revenue'], 0)
        gp_1 = _row_value(financials, ['Gross Profit'], 1)
        tr_1 = _row_value(financials, ['Total Revenue', 'Operating Revenue'], 1)
        if pd.notna(gp_0) and pd.notna(tr_0) and tr_0 != 0:
            out['gross_margin'] = gp_0 / tr_0
        if pd.notna(gp_1) and pd.notna(tr_1) and tr_1 != 0:
            out['gross_margin_prior_yr'] = gp_1 / tr_1
        if pd.notna(out['gross_margin']) and pd.notna(out['gross_margin_prior_yr']):
            out['gross_margin_expansion'] = out['gross_margin'] - out['gross_margin_prior_yr']
    except Exception as e:
        log_error(ticker, 'gross_margin', str(e))

    # EBITDA (info first, fall back to financials)
    try:
        ebitda = info.get('ebitda')
        if ebitda is None or (isinstance(ebitda, float) and math.isnan(ebitda)):
            ebitda = _row_value(financials, ['EBITDA', 'Normalized EBITDA'], 0)
        if ebitda is not None and pd.notna(ebitda):
            out['ebitda_ttm'] = float(ebitda)
    except Exception as e:
        log_error(ticker, 'ebitda_ttm', str(e))

    # EV / EBITDA
    try:
        ebitda = out['ebitda_ttm']
        total_debt = info.get('totalDebt')
        total_cash = info.get('totalCash')
        if (pd.notna(ebitda) and ebitda > 0 and market_cap
                and total_debt is not None and total_cash is not None):
            ev = market_cap + total_debt - total_cash
            out['ev_ebitda'] = ev / ebitda
    except Exception as e:
        log_error(ticker, 'ev_ebitda', str(e))

    # Price / Sales (directly from info)
    try:
        ps = info.get('priceToSalesTrailing12Months')
        if ps is not None:
            out['price_to_sales'] = float(ps)
    except Exception as e:
        log_error(ticker, 'price_to_sales', str(e))

    # R&D ratio
    try:
        rd = _row_value(financials, ['Research And Development',
                                     'Research Development'], 0)
        tr_0 = _row_value(financials, ['Total Revenue', 'Operating Revenue'], 0)
        if pd.notna(rd) and pd.notna(tr_0) and tr_0 != 0:
            out['rd_ratio'] = rd / tr_0
    except Exception as e:
        log_error(ticker, 'rd_ratio', str(e))

    # =====================================================================
    # Group D: Institutional & Short Interest
    # =====================================================================
    try:
        held = info.get('heldPercentInstitutions')
        if held is not None:
            out['institutional_ownership_pct'] = float(held)
    except Exception as e:
        log_error(ticker, 'institutional_ownership_pct', str(e))
    try:
        spf = info.get('shortPercentOfFloat')
        if spf is not None:
            out['short_interest_pct_float'] = float(spf)
    except Exception as e:
        log_error(ticker, 'short_interest_pct_float', str(e))
    try:
        sr = info.get('shortRatio')
        if sr is not None:
            out['short_ratio'] = float(sr)
    except Exception as e:
        log_error(ticker, 'short_ratio', str(e))

    # Insider transactions (last ~3 months)
    try:
        ip = _rl_retry(lambda: stock.insider_purchases, ticker, 'insider_purchases')
        if isinstance(ip, pd.DataFrame) and not ip.empty:
            # yfinance returns a small summary frame; the descriptive label is in
            # the first column and the transaction count in a 'Trans' column.
            label_col = ip.columns[0]
            trans_col = 'Trans' if 'Trans' in ip.columns else None
            buys = 0
            sells = 0
            for _, r in ip.iterrows():
                label = str(r.get(label_col, '')).lower()
                trans = r.get(trans_col) if trans_col else None
                n = int(trans) if trans is not None and pd.notna(trans) else 0
                if 'purchase' in label or 'buy' in label:
                    buys += n
                elif 'sale' in label or 'sell' in label or 'sold' in label:
                    sells += n
            out['insider_buy_3m'] = buys
            out['insider_sell_3m'] = sells
            out['insider_net_3m'] = buys - sells
    except Exception as e:
        log_error(ticker, 'insider_purchases', str(e))

    # =====================================================================
    # Group E: Technical / Price Structure
    # =====================================================================
    try:
        price_hist = _rl_retry(lambda: stock.history(period='1y'), ticker, 'price_history')
        if isinstance(price_hist, pd.DataFrame) and not price_hist.empty:
            close = price_hist['Close'].dropna()
            volume = price_hist['Volume'].dropna() if 'Volume' in price_hist else pd.Series(dtype=float)

            # 200-day SMA
            if len(close) >= 1:
                window = close.tail(200)
                out['ma_200d'] = float(window.mean())
                if pd.notna(current_price) and out['ma_200d'] and out['ma_200d'] != 0:
                    out['pct_above_200d_ma'] = (current_price - out['ma_200d']) / out['ma_200d'] * 100.0

            # Relative strength vs VOO
            if voo_returns:
                r12 = _period_return(close, 12)
                r6 = _period_return(close, 6)
                r3 = _period_return(close, 3)
                if pd.notna(r12) and pd.notna(voo_returns.get('voo_return_12m')):
                    out['relative_strength_vs_voo_12m'] = r12 - voo_returns['voo_return_12m']
                if pd.notna(r6) and pd.notna(voo_returns.get('voo_return_6m')):
                    out['relative_strength_vs_voo_6m'] = r6 - voo_returns['voo_return_6m']
                if pd.notna(r3) and pd.notna(voo_returns.get('voo_return_3m')):
                    out['relative_strength_vs_voo_3m'] = r3 - voo_returns['voo_return_3m']

            # Volume ratio (last 20 days vs average volume)
            avg_vol = data.get('average_volume')
            if len(volume) >= 1 and avg_vol and avg_vol != 0:
                recent_vol = volume.tail(20).mean()
                out['volume_ratio_20d'] = float(recent_vol) / avg_vol
    except Exception as e:
        log_error(ticker, 'price_structure', str(e))

    return out


# ---------------------------------------------------------------------------
# Group F: rule-based macro sensitivity tags (post-processing on the DataFrame)
# ---------------------------------------------------------------------------

def apply_macro_tags(df: pd.DataFrame) -> pd.DataFrame:
    """Add the four rule-based macro tags to the final DataFrame."""
    if df is None or df.empty:
        return df

    sector = df.get('sector', pd.Series(['Unknown'] * len(df), index=df.index)).fillna('Unknown')
    industry = df.get('industry', pd.Series(['Unknown'] * len(df), index=df.index)).fillna('Unknown')
    d2e = pd.to_numeric(df.get('debt_to_equity'), errors='coerce')
    mcap = pd.to_numeric(df.get('market_cap'), errors='coerce')

    # rate_sensitive
    df['rate_sensitive'] = (
        sector.isin(['Real Estate', 'Utilities'])
        | industry.str.contains('REIT', case=False, na=False)
        | (d2e > 150)
    )

    # ai_infrastructure: (semis/electronic components AND Technology sector) OR hardcoded ticker
    df['ai_infrastructure'] = (
        (industry.isin(AI_INFRA_INDUSTRIES) & (sector == 'Technology'))
        | df['ticker'].isin(AI_INFRA_TICKERS)
    )

    # em_fx_exposure
    df['em_fx_exposure'] = df['ticker'].isin(EM_FX_TICKERS)

    # hyperscaler_dependent: ai_infrastructure AND sub-$100B market cap
    df['hyperscaler_dependent'] = df['ai_infrastructure'] & (mcap < 100_000_000_000)

    return df


# ---------------------------------------------------------------------------
# Updated composite score
# ---------------------------------------------------------------------------

# Existing five sub-scores that get rebalanced by 65/100.
_EXISTING_SUBSCORES = [
    'revenue_growth_score', 'forward_growth_score', 'valuation_score',
    'analyst_score', 'momentum_score',
]

# New scoring inputs that use a batch-median fallback when NaN.
_SCORING_FIELDS = [
    'earnings_beat_rate', 'eps_revision_net', 'earnings_quality_ratio',
    'fcf_margin', 'fcf_yield', 'gross_margin', 'gross_margin_expansion',
]


def _linear(value, low, high, max_pts):
    """Linear scale ``value`` from ``low``->0pts to ``high``->``max_pts``, clamped."""
    if pd.isna(value):
        return np.nan
    if high == low:
        return max_pts
    frac = (value - low) / (high - low)
    return max(0.0, min(max_pts, frac * max_pts))


def apply_extended_scoring(df: pd.DataFrame) -> pd.DataFrame:
    """Add the three new sub-scores, rebalance the existing five, and recompute
    ``composite_score``.

    Stores the pre-rebalance sub-scores (and old composite) as ``*_score_v1``.
    NaN scoring inputs fall back to the batch median (logged once per field).
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # Ensure the existing sub-scores exist (the base screener may not have run
    # them, e.g. if called standalone) -- treat missing as 0.
    for col in _EXISTING_SUBSCORES:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # Preserve pre-rebalance ("v1") values.
    for col in _EXISTING_SUBSCORES:
        df[f"{col}_v1"] = df[col]
    df['composite_score_v1'] = df[_EXISTING_SUBSCORES].sum(axis=1).round(1)

    # ---- batch-median fallback for scoring inputs ----
    medians = {}
    for field in _SCORING_FIELDS:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors='coerce')
            medians[field] = df[field].median()
        else:
            df[field] = np.nan
            medians[field] = np.nan

    def val(row, field):
        """Field value with batch-median fallback; logs when fallback used."""
        v = row.get(field)
        if pd.isna(v):
            med = medians.get(field)
            log_error(row.get('ticker', '?'), 'scoring_fallback',
                      f"{field} is NaN, using batch median {med}")
            return med
        return v

    # ---- new sub-scores ----
    eq_scores, fcf_scores, moat_scores = [], [], []
    for _, row in df.iterrows():
        # earnings_quality_score: raw 0-20, normalized to 0-15 (weight ~15)
        beat = val(row, 'earnings_beat_rate')
        net = val(row, 'eps_revision_net')
        eqr = val(row, 'earnings_quality_ratio')
        eq_raw = 0.0
        eq_raw += _linear(beat, 0, 75, 8) if pd.notna(beat) else 0.0      # 0-8
        eq_raw += _linear(net, -3, 5, 7) if pd.notna(net) else 0.0        # 0-7
        eq_raw += _linear(eqr, 0.5, 1.5, 5) if pd.notna(eqr) else 0.0     # 0-5
        eq_scores.append(eq_raw * (15.0 / 20.0))                          # -> 0-15

        # fcf_score: 0-10 (weight ~10)
        fm = val(row, 'fcf_margin')
        fy = val(row, 'fcf_yield')
        fcf_raw = 0.0
        fcf_raw += _linear(fm, 0, 0.20, 6) if pd.notna(fm) else 0.0       # 0-6
        fcf_raw += _linear(fy, 0, 0.05, 4) if pd.notna(fy) else 0.0       # 0-4
        fcf_scores.append(fcf_raw)

        # moat_score: 0-10 (weight ~10)
        gm = val(row, 'gross_margin')
        gme = val(row, 'gross_margin_expansion')
        moat_raw = 0.0
        moat_raw += _linear(gm, 0.10, 0.60, 6) if pd.notna(gm) else 0.0   # 0-6
        moat_raw += _linear(gme, -0.02, 0.05, 4) if pd.notna(gme) else 0.0  # 0-4
        moat_scores.append(moat_raw)

    df['earnings_quality_score'] = np.round(eq_scores, 1)
    df['fcf_score'] = np.round(fcf_scores, 1)
    df['moat_score'] = np.round(moat_scores, 1)

    # ---- rebalance existing five sub-scores by 65/100 ----
    for col in _EXISTING_SUBSCORES:
        df[col] = (df[f"{col}_v1"] * 0.65).round(1)

    # ---- new composite (max 65 + 15 + 10 + 10 = 100) ----
    df['composite_score'] = (
        df[_EXISTING_SUBSCORES].sum(axis=1)
        + df['earnings_quality_score']
        + df['fcf_score']
        + df['moat_score']
    ).round(1)

    return df


def build_delta_report(df: pd.DataFrame) -> pd.DataFrame:
    """Build the score delta report DataFrame (sorted by delta descending)."""
    delta = pd.DataFrame({
        'ticker': df['ticker'],
        'composite_score_v1': df['composite_score_v1'],
        'composite_score': df['composite_score'],
        'earnings_quality_score': df['earnings_quality_score'],
        'fcf_score': df['fcf_score'],
        'moat_score': df['moat_score'],
    })
    delta['delta'] = (delta['composite_score'] - delta['composite_score_v1']).round(1)
    delta = delta[['ticker', 'composite_score_v1', 'composite_score', 'delta',
                   'earnings_quality_score', 'fcf_score', 'moat_score']]
    return delta.sort_values('delta', ascending=False).reset_index(drop=True)
