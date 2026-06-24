"""
Stock Screener Module
Implements screening logic for high-growth stocks
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from data_fetcher import StockDataFetcher
from ticker_universe import get_full_universe, get_ticker_sectors
from edgar_fetcher import EDGARDataFetcher, EDGARScreeningEnhancer

# Logger writing dropped-ticker reasons to the shared screener_errors.log.
_gate_logger = logging.getLogger("screener_gates")
if not _gate_logger.handlers:
    _gate_logger.setLevel(logging.INFO)
    _gh = logging.FileHandler("screener_errors.log")
    _gh.setFormatter(logging.Formatter("%(message)s"))
    _gate_logger.addHandler(_gh)
    _gate_logger.propagate = False


def _gate_log(ticker: str, gate: str, message: str) -> None:
    """Log a hard-gate drop as: TICKER | hard_gate:<gate> | message."""
    try:
        _gate_logger.info(f"{ticker} | hard_gate:{gate} | {message}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Hard universe exclusion gate thresholds (Fix 1).
# Adjustable here (or via the app sidebar) without touching gate logic.
# ---------------------------------------------------------------------------
HARD_GATE_MIN_REVENUE_TTM = 100_000_000
HARD_GATE_MAX_FCF_MARGIN_FLOOR = -0.20
HARD_GATE_MAX_EV_EBITDA = 60
HARD_GATE_BIOTECH_PROXY_GROSS_MARGIN = 0.85
HARD_GATE_BIOTECH_PROXY_MAX_REVENUE = 500_000_000
HARD_GATE_ACTIVE_LISTING = True          # exclude inactive/delisted tickers
HARD_GATE_MIN_FORWARD_REVENUE_GROWTH = 0.10  # 10% minimum forward revenue growth

# Tier-specific hard-gate thresholds (three-tier architecture). Speculative gets
# looser gates because early-stage compounders often run negative FCF / high
# valuations, and the biotech-proxy gate is skipped for it.
TIER_GATES = {
    'core': {'min_revenue_ttm': 500_000_000, 'fcf_margin_floor': -0.20,
             'max_ev_ebitda': 60, 'min_forward_revenue_growth': 0.10, 'apply_biotech': True},
    'growth': {'min_revenue_ttm': 50_000_000, 'fcf_margin_floor': -0.40,
               'max_ev_ebitda': 80, 'min_forward_revenue_growth': 0.20, 'apply_biotech': True},
    'speculative': {'min_revenue_ttm': 10_000_000, 'fcf_margin_floor': -0.60,
                    'max_ev_ebitda': 120, 'min_forward_revenue_growth': 0.30, 'apply_biotech': False},
}


def apply_hard_gates(df: pd.DataFrame,
                     min_revenue_ttm: float = HARD_GATE_MIN_REVENUE_TTM,
                     fcf_margin_floor: float = HARD_GATE_MAX_FCF_MARGIN_FLOOR,
                     max_ev_ebitda: float = HARD_GATE_MAX_EV_EBITDA,
                     biotech_gross_margin: float = HARD_GATE_BIOTECH_PROXY_GROSS_MARGIN,
                     biotech_max_revenue: float = HARD_GATE_BIOTECH_PROXY_MAX_REVENUE,
                     active_listing: bool = HARD_GATE_ACTIVE_LISTING,
                     min_forward_revenue_growth: float = HARD_GATE_MIN_FORWARD_REVENUE_GROWTH,
                     apply_biotech: bool = True):
    """Apply hard universe exclusion gates before scoring (Fix 1).

    Drops any ticker failing a gate, logs the reason to screener_errors.log, and
    returns (kept_df, stats) where stats maps each gate name to the list of
    dropped tickers (a ticker is attributed to the first gate it fails).
    """
    stats: Dict[str, List[str]] = {
        'active_listing': [], 'min_revenue_ttm': [], 'min_fcf_margin': [],
        'max_ev_ebitda': [], 'revenue_source_proxy': [], 'min_forward_revenue_growth': [],
    }
    if df is None or df.empty:
        return df, stats

    df = df.copy()
    rev = pd.to_numeric(df.get('revenue_ttm'), errors='coerce')
    fcfm = (pd.to_numeric(df['fcf_margin'], errors='coerce')
            if 'fcf_margin' in df.columns else pd.Series(np.nan, index=df.index))
    eve = (pd.to_numeric(df['ev_ebitda'], errors='coerce')
           if 'ev_ebitda' in df.columns else pd.Series(np.nan, index=df.index))
    gm = (pd.to_numeric(df['gross_margin'], errors='coerce')
          if 'gross_margin' in df.columns else pd.Series(np.nan, index=df.index))
    active = (df['is_actively_trading'] if 'is_actively_trading' in df.columns
              else pd.Series(True, index=df.index))
    fwd_rev = (pd.to_numeric(df['forward_revenue_estimate'], errors='coerce')
               if 'forward_revenue_estimate' in df.columns else pd.Series(np.nan, index=df.index))
    # Forward revenue growth in percentage points (NaN when estimate/rev missing).
    fwd_growth = (fwd_rev / rev.replace(0.0, np.nan) - 1.0) * 100
    min_fwd_pct = min_forward_revenue_growth * 100  # constant stored as a decimal

    # Gate masks (True == FAIL -> drop).
    fail_active = (active == False) if active_listing else pd.Series(False, index=df.index)  # noqa: E712
    fail_rev = rev.isna() | (rev <= 0) | (rev < min_revenue_ttm)
    fail_fcf = fcfm.notna() & (fcfm < fcf_margin_floor)
    fail_ev = eve.notna() & (eve > max_ev_ebitda)
    fail_bio = (apply_biotech & gm.notna() & rev.notna()
                & (gm > biotech_gross_margin) & (rev < biotech_max_revenue))
    # NaN forward growth is NOT excluded here (handled by the conservative
    # deceleration penalty in calculate_horizon_scores instead).
    fail_fwd = fwd_growth.notna() & (fwd_growth < min_fwd_pct)

    keep = pd.Series(True, index=df.index)
    ordered = [
        ('active_listing', fail_active,
         lambda i: "delisted_or_inactive (isActivelyTrading=False)"),
        ('min_revenue_ttm', fail_rev,
         lambda i: f"revenue_ttm={rev.get(i)} (< {min_revenue_ttm:,.0f} or NaN/zero)"),
        ('min_fcf_margin', fail_fcf,
         lambda i: f"fcf_margin={fcfm.get(i):.3f} (< {fcf_margin_floor})"),
        ('max_ev_ebitda', fail_ev,
         lambda i: f"ev_ebitda={eve.get(i):.2f} (> {max_ev_ebitda})"),
        ('revenue_source_proxy', fail_bio,
         lambda i: f"gross_margin={gm.get(i):.3f} & revenue_ttm={rev.get(i):,.0f} "
                   f"(GM>{biotech_gross_margin} & rev<{biotech_max_revenue:,.0f})"),
        ('min_forward_revenue_growth', fail_fwd,
         lambda i: f"forward_revenue_growth={fwd_growth.get(i):.1f}pp (< {min_fwd_pct:.1f}pp)"),
    ]
    for gate, fail_mask, reason_fn in ordered:
        hit = fail_mask & keep
        for i in df.index[hit]:
            ticker = df.at[i, 'ticker'] if 'ticker' in df.columns else str(i)
            stats[gate].append(ticker)
            _gate_log(ticker, gate, reason_fn(i))
        keep = keep & ~fail_mask

    return df[keep].copy(), stats

# ===========================================================================
# Horizon-based percentile-rank scoring engine
# ===========================================================================
# Principle (1): every factor is scored on its cross-sectional PERCENTILE RANK
# across the current batch (0-100, 100 = best), via rank(pct=True)*100, so the
# weights below behave as written regardless of factor distributions/outliers.
#
# Principle (2): sign discipline. 'low is good' factors have their rank inverted
# (100 - rank). The set is asserted at scoring time.
LOW_IS_GOOD = {
    'forward_pe',          # listed as fwd_pe
    'ev_ebitda',
    'accruals_ratio',      # dropped from scoring (see consolidation) but signed here
    'asset_growth',
    'short_interest_pct_float',
    'debt_trend',
}

# Principle (5): these are ranked WITHIN GICS sector (fallback to universe when a
# sector has < 5 members in the batch).
SECTOR_RANKED = {'gross_margin', 'fcf_margin'}

# Factor -> family (used for the validation weight-by-family printout).
FACTOR_FAMILY = {
    'momentum_12_1': 'Momentum',
    'relative_strength_vs_voo_12m': 'Momentum',
    'eps_revision_net': 'Earnings momentum',
    'revenue_estimate_revision': 'Earnings momentum',
    'gross_margin': 'Quality',
    'gross_margin_expansion': 'Quality',
    'earnings_quality_ratio': 'Quality',
    'net_margin_trend': 'Quality',
    'fcf_margin': 'Profitability',
    'fcf_yield': 'Value',
    'ev_ebitda': 'Value',
    'forward_pe': 'Value',
    'capital_efficiency': 'Growth',
    'revenue_growth_yoy': 'Growth',
    'forward_revenue_growth': 'Growth',
    'forward_revenue_growth_weighted': 'Growth',
    'asset_growth': 'Capital discipline',
    'shareholder_yield': 'Capital return',
    'net_buyback_yield': 'Capital return',
    'institutional_ownership_change': 'Positioning',
    'insider_net_value_normalized': 'Positioning',
    'short_interest_pct_float': 'Positioning',
    'debt_trend': 'Risk',
}

TIERS = ('core', 'growth', 'speculative')
HORIZONS = ('12m', '24m', '36m')

# Fix 3: fully separate per-horizon weight VECTORS (not a mild tilt) so 12m and
# 36m scores diverge meaningfully. The Growth tier's explicit horizon weights:
HORIZON_WEIGHTS_GROWTH = {
    '12m': {
        'forward_revenue_growth_weighted': 18, 'momentum_12_1': 16, 'eps_revision_net': 10,
        'revenue_estimate_revision': 6, 'capital_efficiency': 4, 'gross_margin': 5,
        'gross_margin_expansion': 4, 'earnings_quality_ratio': 3, 'net_margin_trend': 3,
        'fcf_margin': 3, 'fcf_yield': 1, 'ev_ebitda': 1, 'forward_pe': 1,
        'asset_growth': 3, 'shareholder_yield': 1, 'net_buyback_yield': 1,
        'institutional_ownership_change': 5, 'insider_net_value_normalized': 4,
        'short_interest_pct_float': 4, 'debt_trend': 3, 'revenue_growth_yoy': 4,
    },
    '24m': {
        'forward_revenue_growth_weighted': 10, 'momentum_12_1': 8, 'eps_revision_net': 7,
        'revenue_estimate_revision': 5, 'capital_efficiency': 6, 'gross_margin': 8,
        'gross_margin_expansion': 6, 'earnings_quality_ratio': 5, 'net_margin_trend': 5,
        'fcf_margin': 6, 'fcf_yield': 4, 'ev_ebitda': 4, 'forward_pe': 3,
        'asset_growth': 6, 'shareholder_yield': 3, 'net_buyback_yield': 2,
        'institutional_ownership_change': 4, 'insider_net_value_normalized': 4,
        'short_interest_pct_float': 3, 'debt_trend': 4, 'revenue_growth_yoy': 5,
    },
    '36m': {
        'forward_revenue_growth_weighted': 4, 'momentum_12_1': 3, 'eps_revision_net': 4,
        'revenue_estimate_revision': 3, 'capital_efficiency': 7, 'gross_margin': 10,
        'gross_margin_expansion': 8, 'earnings_quality_ratio': 7, 'net_margin_trend': 6,
        'fcf_margin': 9, 'fcf_yield': 8, 'ev_ebitda': 7, 'forward_pe': 6,
        'asset_growth': 8, 'shareholder_yield': 6, 'net_buyback_yield': 4,
        'institutional_ownership_change': 3, 'insider_net_value_normalized': 4,
        'short_interest_pct_float': 2, 'debt_trend': 5, 'revenue_growth_yoy': 5,
    },
}

# Growth tier base = per-factor mean across horizons; the horizon SHAPE is each
# factor's per-horizon multiple of that mean. Applying that shape to any tier's
# base weights gives the same aggressive 12m->36m shift, scaled proportionally
# to that tier's emphasis (Core / Speculative).
_GROWTH_BASE = {f: sum(HORIZON_WEIGHTS_GROWTH[h][f] for h in HORIZONS) / 3.0
                for f in HORIZON_WEIGHTS_GROWTH['12m']}
_HORIZON_SHAPE = {f: {h: HORIZON_WEIGHTS_GROWTH[h][f] / _GROWTH_BASE[f] for h in HORIZONS}
                  for f in _GROWTH_BASE}

# Per-tier base emphasis (single weight per factor); Core rewards value/quality,
# Speculative rewards momentum/growth. forward_revenue_growth_weighted replaces
# raw forward growth (Fix 1); relative strength is no longer a scored factor.
TIER_BASE = {
    'growth': _GROWTH_BASE,
    'core': {
        'capital_efficiency': 6, 'gross_margin': 8, 'gross_margin_expansion': 5,
        'earnings_quality_ratio': 5, 'net_margin_trend': 4, 'fcf_margin': 7,
        'fcf_yield': 4, 'ev_ebitda': 4, 'forward_pe': 4, 'momentum_12_1': 8,
        'eps_revision_net': 6, 'revenue_estimate_revision': 4, 'asset_growth': 5,
        'shareholder_yield': 4, 'net_buyback_yield': 3, 'institutional_ownership_change': 3,
        'insider_net_value_normalized': 3, 'short_interest_pct_float': 2, 'debt_trend': 2,
        'revenue_growth_yoy': 6, 'forward_revenue_growth_weighted': 6,
    },
    'speculative': {
        'capital_efficiency': 4, 'gross_margin': 5, 'gross_margin_expansion': 6,
        'earnings_quality_ratio': 3, 'net_margin_trend': 5, 'fcf_margin': 3,
        'fcf_yield': 1, 'ev_ebitda': 1, 'forward_pe': 1, 'momentum_12_1': 14,
        'eps_revision_net': 8, 'revenue_estimate_revision': 5, 'asset_growth': 3,
        'shareholder_yield': 1, 'net_buyback_yield': 1, 'institutional_ownership_change': 5,
        'insider_net_value_normalized': 5, 'short_interest_pct_float': 4, 'debt_trend': 4,
        'revenue_growth_yoy': 14, 'forward_revenue_growth_weighted': 16,
    },
}

# Back-compat alias: code/validation that referenced TIER_WEIGHTS for the scored
# factor set still works (same 21 factors).
TIER_WEIGHTS = TIER_BASE


def normalized_weights(tier: str, horizon: str) -> Dict[str, float]:
    """Per-(tier, horizon) weights: tier base emphasis shaped by the aggressive
    horizon profile, scaled to sum to 100."""
    base = TIER_BASE[tier]
    raw = {f: base[f] * _HORIZON_SHAPE[f][horizon] for f in base}
    total = float(sum(raw.values()))
    return {f: v / total * 100.0 for f, v in raw.items()}


def family_weights(tier: str, horizon: str) -> Dict[str, float]:
    """Effective normalized weight carried by each factor family (tier, horizon)."""
    fam: Dict[str, float] = {}
    for f, w in normalized_weights(tier, horizon).items():
        fam[FACTOR_FAMILY[f]] = fam.get(FACTOR_FAMILY[f], 0.0) + w
    return fam


def _sector_aware_rank(df: pd.DataFrame, col: pd.Series, min_members: int = 5) -> pd.Series:
    """Percentile rank within each sector; fall back to universe rank for
    sectors with fewer than ``min_members`` members (principle 5)."""
    universe = col.rank(pct=True) * 100
    if 'sector' not in df.columns:
        return universe
    out = universe.copy()
    sectors = df['sector'].fillna('Unknown')
    for sec in sectors.unique():
        idx = sectors.index[sectors == sec]
        sub = col.loc[idx]
        if sub.notna().sum() >= min_members:
            out.loc[idx] = sub.rank(pct=True) * 100
    return out


def _factor_rank(df: pd.DataFrame, factor: str) -> pd.Series:
    """Cross-sectional 0-100 percentile rank for a factor, with sign discipline
    (low-is-good inverted) and optional sector normalization."""
    if factor in df.columns:
        col = pd.to_numeric(df[factor], errors='coerce')
    else:
        col = pd.Series(np.nan, index=df.index)
    if factor in SECTOR_RANKED:
        rank = _sector_aware_rank(df, col)
    else:
        rank = col.rank(pct=True) * 100
    if factor in LOW_IS_GOOD:
        rank = 100 - rank
    return rank


def _assert_factor_sign(df: pd.DataFrame, factor: str, rank: pd.Series) -> None:
    """Assert each factor's rank carries the intended sign (principle 2).

    Sector-ranked factors are skipped because within-sector ranking deliberately
    breaks the global monotonic relationship between raw value and rank.
    """
    if factor in SECTOR_RANKED or factor not in df.columns:
        return
    raw = pd.to_numeric(df[factor], errors='coerce')
    valid = raw.notna() & rank.notna()
    if valid.sum() < 3 or raw[valid].nunique() < 2 or rank[valid].nunique() < 2:
        return
    corr = float(np.corrcoef(raw[valid].to_numpy(), rank[valid].to_numpy())[0, 1])
    if np.isnan(corr):
        return
    if factor in LOW_IS_GOOD:
        assert corr < 0, f"Sign error: '{factor}' is low-is-good but corr(raw, rank)={corr:.3f} >= 0"
    else:
        assert corr > 0, f"Sign error: '{factor}' is high-is-good but corr(raw, rank)={corr:.3f} <= 0"


def calculate_horizon_scores(df: pd.DataFrame, tier: str = 'growth') -> pd.DataFrame:
    """Compute composite_score_12m/24m/36m from weighted percentile ranks using
    the given tier's factor weights ('core' / 'growth' / 'speculative').

    Stores the previous composite as composite_score_v2, records the tier in a
    'tier' column, and aliases composite_score to the 12m score.
    """
    if df is None or df.empty:
        return df
    if tier not in TIER_WEIGHTS:
        tier = 'growth'
    df = df.copy()
    df['tier'] = tier

    def _col(name: str) -> pd.Series:
        """Numeric column as a Series, or an all-NaN Series if absent."""
        if name in df.columns:
            return pd.to_numeric(df[name], errors='coerce')
        return pd.Series(np.nan, index=df.index)

    # Principle (6): capital-efficiency interaction = pct rank of
    # revenue_growth_yoy / (1 + asset_growth). Missing asset_growth -> treated as
    # 0 so the term degrades to growth alone rather than dropping out.
    rg = _col('revenue_growth_yoy')
    ag = _col('asset_growth').fillna(0.0)
    ce_raw = rg / (1.0 + ag)
    df['capital_efficiency'] = ce_raw.rank(pct=True) * 100

    # Fix 6: dollar-weighted insider signal, normalized by market cap so that
    # large-cap insider buying isn't structurally disadvantaged vs small-cap.
    inv = _col('insider_net_value_3m')
    mcap = _col('market_cap')
    df['insider_net_value_normalized'] = inv / mcap.replace(0.0, np.nan)

    # Fix 2: forward-vs-trailing growth divergence (percentage points).
    fwd_rev = _col('forward_revenue_estimate')
    rev_ttm = _col('revenue_ttm')
    df['forward_revenue_growth'] = (fwd_rev / rev_ttm.replace(0.0, np.nan) - 1.0) * 100
    df['growth_deceleration'] = df['forward_revenue_growth'] - rg

    # Fix 5: when forward revenue growth is unknown (missing forward estimate),
    # assume a CONSERVATIVE 20pp deceleration rather than skipping the penalty.
    # This is a deliberate default, not a measured value; the row is flagged so
    # it's visible which stocks are penalized on assumption vs measurement.
    df['forward_estimate_missing'] = df['forward_revenue_growth'].isna()
    df.loc[df['forward_estimate_missing'], 'growth_deceleration'] = -20.0

    # Fix 1: discount forward revenue growth by analyst coverage before ranking
    # (thin coverage -> less reliable forward estimate). Raw forward growth is
    # kept for display; the weighted version is what the composite scores.
    acw = _col('analyst_coverage_weight').fillna(1.0)
    df['forward_revenue_growth_weighted'] = df['forward_revenue_growth'] * acw

    # Preserve the prior single composite as composite_score_v2 (principle 4).
    df['composite_score_v2'] = pd.to_numeric(df.get('composite_score', np.nan), errors='coerce')

    # Fix 4: data_quality_score = % of scored factors with non-NaN raw values
    # (computed BEFORE any median fallback, on the factor columns themselves).
    scored_factors = sorted(set().union(*[w.keys() for w in TIER_BASE.values()]))
    cov_cols = [f for f in scored_factors if f in df.columns]
    if cov_cols:
        df['data_quality_score'] = (df[cov_cols].notna().sum(axis=1)
                                    / len(scored_factors) * 100).round(0)
    else:
        df['data_quality_score'] = 0.0

    # Pre-compute every factor rank once (with sign + sector normalization).
    factors = sorted(set().union(*[w.keys() for w in TIER_WEIGHTS.values()]))
    ranks: Dict[str, pd.Series] = {}
    for f in factors:
        r = _factor_rank(df, f)
        _assert_factor_sign(df, f, r)
        ranks[f] = r

    # Weighted average of available ranks per horizon (per-ticker renormalization
    # over non-NaN factors keeps scores comparable when some factors are missing).
    for hz in HORIZONS:
        wn = normalized_weights(tier, hz)
        num = pd.Series(0.0, index=df.index)
        den = pd.Series(0.0, index=df.index)
        for f, w in wn.items():
            r = ranks[f]
            m = r.notna()
            num[m] = num[m] + w * r[m]
            den[m] = den[m] + w
        df[f'composite_score_{hz}'] = (num / den.replace(0.0, np.nan)).round(2)

    # Fix 2: growth-deceleration penalty / acceleration bonus applied to the
    # horizon scores after ranking. Tiers are mutually exclusive (the steeper
    # -30 penalty supersedes the -15 one); scores are clipped back to [0, 100].
    decel = df['growth_deceleration']
    penalty = pd.Series(0.0, index=df.index)
    penalty[decel < -15] = -10.0
    penalty[decel < -30] = -20.0
    bonus_12m = pd.Series(0.0, index=df.index)
    bonus_12m[decel > 10] = 5.0
    for hz in HORIZONS:
        col = f'composite_score_{hz}'
        adj = df[col] + penalty
        if hz == '12m':
            adj = adj + bonus_12m
        df[col] = adj.clip(lower=0.0, upper=100.0).round(2)

    # Backward-compatible alias (existing code references composite_score).
    df['composite_score'] = df['composite_score_12m']
    return df


class GrowthStockScreener:
    """Screen stocks based on growth metrics and other criteria"""

    def __init__(self, fetcher: Optional[StockDataFetcher] = None, use_edgar: bool = False,
                 tier: str = 'growth',
                 gate_min_revenue_ttm: Optional[float] = None,
                 gate_fcf_margin_floor: Optional[float] = None,
                 gate_max_ev_ebitda: Optional[float] = None,
                 gate_biotech_gross_margin: float = HARD_GATE_BIOTECH_PROXY_GROSS_MARGIN,
                 gate_biotech_max_revenue: float = HARD_GATE_BIOTECH_PROXY_MAX_REVENUE,
                 gate_active_listing: bool = HARD_GATE_ACTIVE_LISTING,
                 gate_min_forward_revenue_growth: Optional[float] = None):
        """
        Initialize the screener

        Args:
            fetcher: Optional StockDataFetcher instance
            use_edgar: Whether to include EDGAR data in screening
            tier: 'core' | 'growth' | 'speculative' — sets gate + scoring defaults
            gate_*: Hard-gate overrides; None falls back to the tier default
        """
        self.fetcher = fetcher or StockDataFetcher()
        self.sector_map = get_ticker_sectors()
        self.use_edgar = use_edgar
        if use_edgar:
            self.edgar_enhancer = EDGARScreeningEnhancer()
        # Tier-specific defaults; explicit gate_* args override per-run.
        self.tier = tier if tier in TIER_GATES else 'growth'
        tg = TIER_GATES[self.tier]
        self.gate_min_revenue_ttm = (gate_min_revenue_ttm if gate_min_revenue_ttm is not None
                                     else tg['min_revenue_ttm'])
        self.gate_fcf_margin_floor = (gate_fcf_margin_floor if gate_fcf_margin_floor is not None
                                      else tg['fcf_margin_floor'])
        self.gate_max_ev_ebitda = (gate_max_ev_ebitda if gate_max_ev_ebitda is not None
                                   else tg['max_ev_ebitda'])
        self.gate_biotech_gross_margin = gate_biotech_gross_margin
        self.gate_biotech_max_revenue = gate_biotech_max_revenue
        self.gate_active_listing = gate_active_listing
        self.gate_min_forward_revenue_growth = (gate_min_forward_revenue_growth
                                                if gate_min_forward_revenue_growth is not None
                                                else tg['min_forward_revenue_growth'])
        self.gate_apply_biotech = tg['apply_biotech']
        self.gate_stats: Dict[str, List[str]] = {}
        self.delisted_excluded: List[str] = []

    def screen_stocks(
        self,
        tickers: Optional[List[str]] = None,
        min_revenue_growth: float = 20.0,
        min_market_cap: float = 1e9,
        max_pe_ratio: float = 100.0,
        exclude_sectors: Optional[List[str]] = None,
        require_positive_earnings: bool = False,
        require_analyst_coverage: bool = False,
        min_analyst_buy_percent: float = 0.0,
        progress_callback=None
    ) -> pd.DataFrame:
        """
        Screen stocks based on specified criteria

        Args:
            tickers: List of tickers to screen (uses full universe if None)
            min_revenue_growth: Minimum YoY revenue growth percentage
            min_market_cap: Minimum market capitalization
            max_pe_ratio: Maximum P/E ratio
            exclude_sectors: List of sectors to exclude
            require_positive_earnings: Filter for profitable companies only
            require_analyst_coverage: Require analyst coverage
            min_analyst_buy_percent: Minimum percentage of buy ratings
            progress_callback: Optional callback for progress updates

        Returns:
            DataFrame with screened stocks
        """
        # Get tickers to screen
        if tickers is None:
            tickers = get_full_universe()

        # Preload the VOO benchmark returns ONCE before the ticker loop so
        # relative_strength_vs_voo_* can be computed (prints a startup confirm).
        preload = getattr(self.fetcher, 'preload_voo_returns', None)
        if callable(preload) and getattr(self.fetcher, 'voo_returns', None) is None:
            try:
                preload()
            except Exception as e:
                print(f"VOO preload skipped: {e}")

        # Fix 1: drop FMP-delisted tickers BEFORE fetching (saves API calls on
        # dead tickers). Only runs when the fetcher exposes a delisted set.
        self.delisted_excluded = []
        get_delisted = getattr(self.fetcher, 'get_delisted_set', None)
        if callable(get_delisted):
            try:
                delisted = get_delisted()
                if delisted:
                    before = len(tickers)
                    kept_tickers = [t for t in tickers if str(t).upper() not in delisted]
                    self.delisted_excluded = [t for t in tickers if str(t).upper() in delisted]
                    for t in self.delisted_excluded:
                        _gate_log(t, 'delisted_prefilter', 'in FMP delisted-companies set')
                    if self.delisted_excluded:
                        print(f"  Skipping {before - len(kept_tickers)} delisted tickers "
                              f"before fetch")
                    tickers = kept_tickers
            except Exception as e:
                print(f"Delisted pre-filter skipped: {e}")

        # Fetch data for all tickers
        print(f"Fetching data for {len(tickers)} tickers...")
        df = self.fetcher.fetch_batch_data(tickers, progress_callback)

        if df.empty:
            return df

        # Ensure numeric columns are properly typed
        numeric_columns = ['market_cap', 'revenue_growth_yoy', 'revenue_growth_qoq',
                          'pe_ratio', 'forward_pe', 'analyst_buy_percent',
                          'number_of_analysts', 'current_price',
                          # EDGAR columns if they exist
                          'edgar_revenue', 'edgar_net_income', 'edgar_revenue_growth',
                          'growth_mentions', 'risk_factors', 'edgar_score']

        for col in numeric_columns:
            if col in df.columns:
                # Convert to numeric, replacing any strings with NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Apply screening criteria
        print("\nApplying screening criteria...")
        initial_count = len(df)

        # Filter by market cap
        if min_market_cap > 0:
            # Ensure we're comparing numbers
            df = df[pd.notna(df['market_cap'])]
            df = df[df['market_cap'] >= min_market_cap]
            print(f"  Market cap >= ${min_market_cap:,.0f}: {len(df)}/{initial_count} stocks")

        # Filter by revenue growth (optional). Only applied when a positive
        # threshold is set, so by default every fetched/scored stock is kept
        # (including those with NaN or negative revenue growth).
        if min_revenue_growth and min_revenue_growth > 0:
            df = df[pd.notna(df['revenue_growth_yoy'])]
            df = df[df['revenue_growth_yoy'] >= min_revenue_growth]
            print(f"  Revenue growth >= {min_revenue_growth}%: {len(df)} stocks")

        # Filter by P/E ratio
        if max_pe_ratio > 0:
            df = df[(pd.isna(df['pe_ratio'])) | (df['pe_ratio'] <= max_pe_ratio)]
            df = df[(pd.isna(df['pe_ratio'])) | (df['pe_ratio'] > 0)]  # Remove negative P/E
            print(f"  P/E ratio <= {max_pe_ratio}: {len(df)} stocks")

        # Filter by positive earnings
        if require_positive_earnings:
            df = df[pd.notna(df['pe_ratio']) & (df['pe_ratio'] > 0)]
            print(f"  Positive earnings only: {len(df)} stocks")

        # Exclude sectors
        if exclude_sectors:
            df = df[~df['sector'].isin(exclude_sectors)]
            print(f"  Excluding sectors {exclude_sectors}: {len(df)} stocks")

        # Filter by analyst coverage
        if require_analyst_coverage:
            df = df[pd.notna(df['number_of_analysts']) & (df['number_of_analysts'] > 0)]
            print(f"  With analyst coverage: {len(df)} stocks")

        # Filter by analyst sentiment
        if min_analyst_buy_percent > 0:
            df = df[pd.notna(df['analyst_buy_percent'])]
            df = df[df['analyst_buy_percent'] >= min_analyst_buy_percent]
            print(f"  Buy ratings >= {min_analyst_buy_percent}%: {len(df)} stocks")

        # Hard universe exclusion gates (Fix 1) — applied BEFORE any scoring.
        if len(df) > 0:
            before = len(df)
            df, self.gate_stats = apply_hard_gates(
                df,
                min_revenue_ttm=self.gate_min_revenue_ttm,
                fcf_margin_floor=self.gate_fcf_margin_floor,
                max_ev_ebitda=self.gate_max_ev_ebitda,
                biotech_gross_margin=self.gate_biotech_gross_margin,
                biotech_max_revenue=self.gate_biotech_max_revenue,
                active_listing=self.gate_active_listing,
                min_forward_revenue_growth=self.gate_min_forward_revenue_growth,
                apply_biotech=self.gate_apply_biotech,
            )
            dropped = before - len(df)
            if dropped:
                counts = ", ".join(f"{g}={len(t)}" for g, t in self.gate_stats.items())
                print(f"  Hard gates removed {dropped} tickers ({counts}); {len(df)} remain")

        # Calculate additional metrics
        df = self._calculate_scores(df)

        # Add EDGAR data if enabled
        if self.use_edgar and len(df) > 0:
            print("\nEnhancing with EDGAR data (this may take a few minutes)...")
            df = self.edgar_enhancer.enhance_screening_data(df)
            # Recalculate composite score with EDGAR data
            df = self._calculate_scores_with_edgar(df)

        # Compute the three horizon scores (12m/24m/36m) from percentile ranks.
        # This stores the prior composite as composite_score_v2 and aliases
        # composite_score to the 12m score.
        if len(df) > 0:
            df = calculate_horizon_scores(df, tier=self.tier)

        # Sort by composite score (12m by default)
        df = df.sort_values('composite_score', ascending=False)

        print(f"\nFinal result: {len(df)} stocks passed screening criteria")

        return df

    def _calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate scoring metrics for ranking stocks

        Args:
            df: DataFrame with stock data

        Returns:
            DataFrame with additional scoring columns
        """
        # Revenue growth score (0-40 points)
        df['revenue_growth_score'] = df['revenue_growth_yoy'].apply(
            lambda x: min(40, max(0, x * 0.8)) if pd.notna(x) else 0
        )

        # Forward growth score (0-20 points)
        # Based on forward estimates and implied growth
        df['forward_growth_score'] = 0
        mask = pd.notna(df['implied_earnings_growth'])
        df.loc[mask, 'forward_growth_score'] = df.loc[mask, 'implied_earnings_growth'].apply(
            lambda x: min(20, max(0, x * 0.4))
        )

        # Valuation score (0-20 points)
        # Lower P/E and PEG get higher scores
        df['valuation_score'] = 0

        # P/E component
        mask = pd.notna(df['pe_ratio']) & (df['pe_ratio'] > 0)
        df.loc[mask, 'valuation_score'] = df.loc[mask, 'pe_ratio'].apply(
            lambda x: max(0, 10 - x/10) if x < 100 else 0
        )

        # PEG component
        mask = pd.notna(df['peg_ratio']) & (df['peg_ratio'] > 0)
        df.loc[mask, 'valuation_score'] += df.loc[mask, 'peg_ratio'].apply(
            lambda x: max(0, 10 - x*5) if x < 2 else 0
        )

        # Analyst sentiment score (0-20 points)
        df['analyst_score'] = 0
        mask = pd.notna(df['analyst_buy_percent'])
        df.loc[mask, 'analyst_score'] = df.loc[mask, 'analyst_buy_percent'] * 0.2

        # Price momentum score (0-20 points)
        # Based on position within 52-week range
        df['momentum_score'] = 0
        mask = pd.notna(df['current_price']) & pd.notna(df['52_week_high']) & pd.notna(df['52_week_low'])
        df.loc[mask, 'momentum_score'] = df.apply(
            lambda row: ((row['current_price'] - row['52_week_low']) /
                        (row['52_week_high'] - row['52_week_low']) * 20)
            if row['52_week_high'] > row['52_week_low'] else 10,
            axis=1
        )[mask]

        # Calculate composite score
        df['composite_score'] = (
            df['revenue_growth_score'] +
            df['forward_growth_score'] +
            df['valuation_score'] +
            df['analyst_score'] +
            df['momentum_score']
        )

        # Round scores for display
        score_columns = ['revenue_growth_score', 'forward_growth_score', 'valuation_score',
                        'analyst_score', 'momentum_score', 'composite_score']
        for col in score_columns:
            df[col] = df[col].round(1)

        return df

    def _calculate_scores_with_edgar(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate scoring metrics including EDGAR data

        Args:
            df: DataFrame with stock and EDGAR data

        Returns:
            DataFrame with enhanced scoring
        """
        # Start with base scores
        df = self._calculate_scores(df)

        # Add EDGAR score if available
        if 'edgar_score' in df.columns:
            # Weight: 70% original score, 30% EDGAR score
            df['composite_score'] = (df['composite_score'] * 0.7) + (df['edgar_score'] * 0.3)
            df['composite_score'] = df['composite_score'].round(1)

        return df

    def get_sector_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Get sector breakdown of screened stocks

        Args:
            df: DataFrame with screened stocks

        Returns:
            DataFrame with sector statistics
        """
        sector_stats = df.groupby('sector').agg({
            'ticker': 'count',
            'market_cap': 'mean',
            'revenue_growth_yoy': 'mean',
            'composite_score': 'mean'
        }).round(2)

        sector_stats.columns = ['Count', 'Avg Market Cap', 'Avg Revenue Growth', 'Avg Score']
        sector_stats = sector_stats.sort_values('Count', ascending=False)

        return sector_stats

    def export_results(self, df: pd.DataFrame, filename: str = 'screener_results.csv'):
        """
        Export screening results to CSV

        Args:
            df: DataFrame with screening results
            filename: Output filename
        """
        # Select columns to export
        export_columns = [
            'ticker', 'company_name', 'sector', 'market_cap', 'current_price',
            'revenue_growth_yoy', 'revenue_growth_qoq', 'pe_ratio', 'peg_ratio',
            'forward_pe', 'implied_earnings_growth', 'analyst_buy_percent',
            'target_mean_price', 'composite_score'
        ]

        # Filter columns that exist
        export_columns = [col for col in export_columns if col in df.columns]

        # Export to CSV
        df[export_columns].to_csv(filename, index=False)
        print(f"Results exported to {filename}")


if __name__ == "__main__":
    # Test the screener
    print("Testing Growth Stock Screener...")
    print("-" * 50)

    screener = GrowthStockScreener()

    # Test with a small subset of tickers
    test_tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'NFLX']

    results = screener.screen_stocks(
        tickers=test_tickers,
        min_revenue_growth=10.0,  # Lower threshold for testing
        min_market_cap=10e9,      # $10B minimum
        exclude_sectors=['Utilities', 'Real Estate'],
        require_analyst_coverage=True
    )

    if not results.empty:
        print("\nTop screened stocks:")
        print(results[['ticker', 'company_name', 'revenue_growth_yoy', 'composite_score']].head())

        # Show sector breakdown
        print("\nSector breakdown:")
        print(screener.get_sector_breakdown(results))