"""
Scoring Validation Harness
==========================

Sanity checks for the horizon-based percentile-rank scoring system
(principle 8). Run after building the scoring overhaul:

    python validate_scoring.py

It will:
  * Load the most recent cached ticker data (ticker_cache.db) if available,
    otherwise synthesize a representative batch so the checks can still run.
  * Assert every inverted ('low is good') factor has rank correlation < 0 with
    its raw value.
  * Assert the 12m and 36m score rankings differ meaningfully
    (Spearman rank correlation < 0.85).
  * Print the top 10 tickers by each horizon score (face-validity eyeball).
  * Print the effective weight each factor family carries in each horizon, so
    the momentum fade and value ramp are easy to confirm.
"""

import json
import sqlite3

import numpy as np
import pandas as pd

from screener import (
    HORIZONS,
    TIER_WEIGHTS,
    LOW_IS_GOOD,
    SECTOR_RANKED,
    calculate_horizon_scores,
    family_weights,
    _factor_rank,
)

CACHE_DB = "ticker_cache.db"
SCORED_FACTORS = sorted(set().union(*[w.keys() for w in TIER_WEIGHTS.values()]))
VALIDATION_TIER = 'growth'


def load_cached_batch() -> pd.DataFrame:
    """Load all cached FMP ticker dicts into a DataFrame, or empty if none."""
    try:
        conn = sqlite3.connect(CACHE_DB)
        rows = conn.execute(
            "SELECT data FROM ticker_data WHERE variant LIKE 'fmp%'"
        ).fetchall()
        conn.close()
    except Exception:
        return pd.DataFrame()
    records = []
    for (blob,) in rows:
        try:
            records.append(json.loads(blob))
        except Exception:
            continue
    return pd.DataFrame(records)


def synthesize_batch(n: int = 90, seed: int = 7) -> pd.DataFrame:
    """Generate a representative batch so the checks run without live data."""
    rng = np.random.default_rng(seed)
    sectors = ['Technology', 'Healthcare', 'Financials', 'Industrials',
               'Consumer Discretionary', 'Energy']
    rgy = rng.normal(15, 25, n)
    rev_ttm = rng.uniform(5e8, 4e10, n)
    data = {
        'ticker': [f'SYN{i:03d}' for i in range(n)],
        'sector': rng.choice(sectors, n),
        'market_cap': rng.uniform(2e9, 5e11, n),
        'revenue_ttm': rev_ttm,
        'revenue_growth_yoy': rgy,
        'forward_revenue_estimate': rev_ttm * (1 + rgy / 100),
        'analyst_coverage_weight': rng.choice([0.2, 0.4, 0.65, 0.85, 1.0], n),
        'momentum_12_1': rng.normal(8, 30, n),
        'eps_revision_net': rng.normal(0, 10, n),
        'revenue_estimate_revision': rng.normal(0, 3, n),
        'gross_margin': rng.uniform(0.1, 0.85, n),
        'gross_margin_expansion': rng.normal(0.0, 0.05, n),
        'earnings_quality_ratio': rng.uniform(-1, 3, n),
        'net_margin_trend': rng.normal(0, 0.04, n),
        'fcf_margin': rng.normal(0.12, 0.15, n),
        'fcf_yield': rng.normal(0.04, 0.05, n),
        'ev_ebitda': np.abs(rng.normal(18, 12, n)) + 2,         # low is good
        'forward_pe': np.abs(rng.normal(25, 18, n)) + 3,        # low is good
        'asset_growth': rng.normal(0.08, 0.2, n),               # low is good
        'shareholder_yield': np.abs(rng.normal(0.03, 0.03, n)),
        'net_buyback_yield': np.abs(rng.normal(0.02, 0.02, n)),
        'institutional_ownership_change': rng.normal(0, 0.05, n),
        'insider_net_value_3m': rng.normal(0, 5e6, n),
        'short_interest_pct_float': np.abs(rng.normal(0.05, 0.05, n)),  # low is good
        'debt_trend': rng.normal(0.0, 0.1, n),                  # low is good
        'composite_score': rng.uniform(20, 80, n),             # prior composite
    }
    df = pd.DataFrame(data)
    # AMPX: high-growth name with thin analyst coverage (weight < 0.5).
    ampx = df.iloc[0].copy()
    ampx['ticker'] = 'AMPX'
    ampx['revenue_growth_yoy'] = 90.0
    ampx['revenue_ttm'] = 3e8
    ampx['forward_revenue_estimate'] = 3e8 * 1.9
    ampx['analyst_coverage_weight'] = 0.20
    df = pd.concat([df, pd.DataFrame([ampx])], ignore_index=True)
    return df


def main():
    df = load_cached_batch()
    source = "cache"
    if df.empty or not set(SCORED_FACTORS).intersection(df.columns):
        df = synthesize_batch()
        source = "synthetic (no cached data found)"

    print("=" * 64)
    print(f"Scoring validation — data source: {source}; tickers: {len(df)}")
    print("=" * 64)

    scored = calculate_horizon_scores(df)

    # --- Check 1: inverted factors have rank corr < 0 with raw value ---
    print("\n[1] Sign discipline — inverted factors (expect rank corr < 0):")
    inverted_present = [f for f in LOW_IS_GOOD
                        if f in SCORED_FACTORS and f in scored.columns]
    for f in sorted(inverted_present):
        raw = pd.to_numeric(scored[f], errors='coerce')
        rank = _factor_rank(scored, f)
        valid = raw.notna() & rank.notna()
        if valid.sum() < 3 or raw[valid].nunique() < 2:
            print(f"    {f:32} corr=  n/a  (insufficient data — skipped)")
            continue
        corr = float(np.corrcoef(raw[valid], rank[valid])[0, 1])
        assert corr < 0, f"FAIL: inverted factor '{f}' has rank corr {corr:.3f} >= 0"
        print(f"    {f:32} corr={corr:+.3f}  OK")

    # --- Check 1b: factor NaN-coverage report (target: core factors > 80%) ---
    print("\n[1b] Factor coverage (% non-NaN across the batch; target > 80%):")
    low_cov = []
    for f in SCORED_FACTORS:
        cov = scored[f].notna().mean() * 100 if f in scored.columns else 0.0
        flag = '' if cov > 80 else '  <-- LOW'
        if cov <= 80:
            low_cov.append(f)
        print(f"    {f:34} {cov:5.1f}%{flag}")
    print(f"    factors below 80% coverage: {low_cov if low_cov else 'none'}")
    if 'data_quality_score' in scored.columns:
        print(f"    mean data_quality_score: {scored['data_quality_score'].mean():.0f}")

    # --- Check 2: horizon rank correlations (target 12m vs 36m < 0.75) ---
    def _spearman(a, b):
        p = scored[[a, b]].dropna()
        return p.corr(method='spearman').iloc[0, 1] if len(p) > 2 else float('nan')
    sp_12_24 = _spearman('composite_score_12m', 'composite_score_24m')
    sp_24_36 = _spearman('composite_score_24m', 'composite_score_36m')
    sp_12_36 = _spearman('composite_score_12m', 'composite_score_36m')
    print("\n[2] Horizon Spearman rank correlations:")
    print(f"    12m vs 24m = {sp_12_24:.3f}")
    print(f"    24m vs 36m = {sp_24_36:.3f}")
    print(f"    12m vs 36m = {sp_12_36:.3f}  (target < 0.75)")
    assert sp_12_36 < 0.75, f"FAIL: 12m and 36m rankings too similar ({sp_12_36:.3f})"
    print("    OK — horizons differ meaningfully")

    # --- Check 3: top 10 by 12m and by 36m (should look different) ---
    print("\n[3] Top 10 by 12m vs by 36m score:")
    for hz in ('12m', '36m'):
        col = f'composite_score_{hz}'
        top = scored.sort_values(col, ascending=False).head(10)
        names = ", ".join(f"{r.ticker}({getattr(r, col):.0f})" for r in top.itertuples())
        print(f"    {hz}: {names}")

    # --- Check 5: AMPX analyst-coverage discount ---
    if 'AMPX' in set(scored['ticker']):
        a = scored[scored['ticker'] == 'AMPX'].iloc[0]
        acw = a.get('analyst_coverage_weight')
        raw = a.get('forward_revenue_growth')
        wtd = a.get('forward_revenue_growth_weighted')
        print(f"\n[5] AMPX: analyst_coverage_weight={acw:.2f} (expect < 0.5); "
              f"fwd_growth raw={raw:.1f} weighted={wtd:.1f}")
        assert acw < 0.5, "FAIL: AMPX coverage weight should be < 0.5"
        assert pd.notna(wtd) and wtd < raw, "FAIL: AMPX weighted fwd growth should be < raw"
        print("    OK — thin coverage discounts the forward estimate")

    # --- Check 4: effective weight per family per horizon ---
    print("\n[4] Effective weight per factor family (normalized to 100):")
    families = sorted({fam for hz in HORIZONS for fam in family_weights(VALIDATION_TIER, hz)})
    header = "    " + "family".ljust(20) + "".join(h.rjust(9) for h in HORIZONS)
    print(header)
    print("    " + "-" * (20 + 9 * len(HORIZONS)))
    fam_by_hz = {hz: family_weights(VALIDATION_TIER, hz) for hz in HORIZONS}
    for fam in families:
        cells = "".join(f"{fam_by_hz[hz].get(fam, 0.0):8.1f}" for hz in HORIZONS)
        print("    " + fam.ljust(20) + cells)
    totals = "".join(f"{sum(fam_by_hz[hz].values()):8.1f}" for hz in HORIZONS)
    print("    " + "TOTAL".ljust(20) + totals)

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
