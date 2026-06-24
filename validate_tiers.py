"""
Validation for the three-tier screening architecture.

Prints:
  * ticker counts for each tier universe,
  * how many pass the tier-specific hard gates,
  * top 5 by 12m score in each tier,
  * confirms a high-growth mid-cap (CRDO/AXON) scores higher in Growth than Core,
  * confirms a quality large-cap (AVGO/MSFT) scores higher in Core than Growth.

Uses cached FMP data if available, otherwise a representative synthetic batch.
"""

import json
import sqlite3

import numpy as np
import pandas as pd

from screener import (TIERS, TIER_GATES, apply_hard_gates, calculate_horizon_scores)
from ticker_universe import get_tiered_universe

CACHE_DB = "ticker_cache.db"


def load_cached_batch() -> pd.DataFrame:
    try:
        conn = sqlite3.connect(CACHE_DB)
        rows = conn.execute("SELECT data FROM ticker_data WHERE variant LIKE 'fmp%'").fetchall()
        conn.close()
    except Exception:
        return pd.DataFrame()
    recs = []
    for (blob,) in rows:
        try:
            recs.append(json.loads(blob))
        except Exception:
            continue
    return pd.DataFrame(recs)


def _row(ticker, sector='Technology', rev=2e9, mcap=2e10, fcf=0.15, ev=25.0, gm=0.6,
         rgy=25.0, fwd_mult=1.25, mom=15.0, rs=10.0, eps_rev=2.0, fcf_yield=0.03,
         fpe=25.0, eqr=1.3, gme=0.02, ag=0.08, sy=0.02, nmt=0.01, active=True):
    fwd = rev * fwd_mult
    return {'ticker': ticker, 'sector': sector, 'revenue_ttm': rev, 'market_cap': mcap,
            'fcf_margin': fcf, 'ev_ebitda': ev, 'gross_margin': gm, 'revenue_growth_yoy': rgy,
            'forward_revenue_estimate': fwd, 'momentum_12_1': mom,
            'relative_strength_vs_voo_12m': rs, 'eps_revision_net': eps_rev,
            'revenue_estimate_revision': 2.0, 'earnings_quality_ratio': eqr,
            'gross_margin_expansion': gme, 'net_margin_trend': nmt, 'fcf_yield': fcf_yield,
            'forward_pe': fpe, 'asset_growth': ag, 'shareholder_yield': sy,
            'net_buyback_yield': 0.01, 'institutional_ownership_change': 0.0,
            'insider_net_value_3m': 0.0, 'short_interest_pct_float': 0.03,
            'debt_trend': 0.0, 'is_actively_trading': active}


def synth_for_tier(tier, n=40, seed=3):
    """Random batch within a tier's cap range that passes its gates."""
    rng = np.random.default_rng(seed + hash(tier) % 1000)
    caps = {'core': (1.2e10, 5e11), 'growth': (1.2e9, 9e9), 'speculative': (3e8, 9e8)}
    revs = {'core': (6e8, 4e10), 'growth': (6e7, 5e9), 'speculative': (1.5e7, 9e8)}
    floor = TIER_GATES[tier]['min_forward_revenue_growth']
    rows = []
    for i in range(n):
        rgy = float(rng.uniform(floor * 100 + 2, floor * 100 + 40))
        rows.append(_row(f'{tier[:2].upper()}{i:03d}',
                         rev=float(rng.uniform(*revs[tier])),
                         mcap=float(rng.uniform(*caps[tier])),
                         fcf=float(rng.uniform(0.0, 0.3)), ev=float(rng.uniform(10, 50)),
                         gm=float(rng.uniform(0.3, 0.7)), rgy=rgy,
                         fwd_mult=1 + rgy / 100, mom=float(rng.normal(12, 18)),
                         rs=float(rng.normal(5, 12)), eps_rev=float(rng.integers(-2, 5))))
    return pd.DataFrame(rows)


def crossover_batch():
    rng = np.random.default_rng(9)
    rows = [_row(f'BG{i:03d}', mcap=5e10, rgy=float(rng.uniform(10, 30)),
                 mom=float(rng.normal(8, 18)), rs=float(rng.normal(0, 12)),
                 fcf=float(rng.uniform(0.05, 0.3)), gm=float(rng.uniform(0.35, 0.7)))
            for i in range(40)]
    # High-growth mid-cap profile (CRDO/AXON): huge momentum/growth, weak FCF/value.
    rows.append(_row('CRDO', mcap=6e9, rev=1e9, rgy=60, fwd_mult=1.7, mom=85, rs=60,
                     eps_rev=5, fcf=0.02, fcf_yield=0.004, ev=95, fpe=70, gm=0.45,
                     eqr=0.7, gme=0.05, ag=0.3))
    rows.append(_row('AXON', mcap=8e9, rev=1.6e9, rgy=33, fwd_mult=1.4, mom=70, rs=48,
                     eps_rev=4, fcf=0.08, fcf_yield=0.01, ev=80, fpe=85, gm=0.6,
                     eqr=1.0, gme=0.04, ag=0.25))
    # Quality large-cap profile (AVGO/MSFT): strong FCF/margin/value, moderate growth.
    rows.append(_row('AVGO', mcap=6e11, rev=1.4e11, rgy=12, fwd_mult=1.14, mom=10, rs=5,
                     eps_rev=2, fcf=0.45, fcf_yield=0.05, ev=20, fpe=22, gm=0.75,
                     eqr=1.8, gme=0.02, ag=0.05, sy=0.03))
    rows.append(_row('MSFT', mcap=3e12, rev=2.4e11, rgy=15, fwd_mult=1.16, mom=12, rs=6,
                     eps_rev=2, fcf=0.30, fcf_yield=0.035, ev=24, fpe=30, gm=0.69,
                     eqr=1.7, gme=0.02, ag=0.07, sy=0.025))
    return pd.DataFrame(rows)


def main():
    print("=" * 68)
    print("Three-tier validation")
    print("=" * 68)

    # [1] Tier universe counts.
    print("\n[1] Tier universe sizes:")
    try:
        tiered = get_tiered_universe()
        for k in ('tier1', 'tier2', 'tier3'):
            print(f"    {k}: {len(tiered.get(k, []))}")
    except Exception as e:
        print(f"    universe fetch failed ({e})")

    # [2] Gate pass counts + [3] top 5 per tier (synthetic if no cache).
    cached = load_cached_batch()
    print("\n[2] Hard-gate pass counts + [3] top 5 by 12m, per tier:")
    for tier in TIERS:
        tg = {k: v for k, v in TIER_GATES[tier].items() if k != 'apply_biotech'}
        df = synth_for_tier(tier) if cached.empty else cached.copy()
        n_in = len(df)
        kept, _ = apply_hard_gates(df, apply_biotech=TIER_GATES[tier]['apply_biotech'], **tg)
        scored = calculate_horizon_scores(kept, tier=tier) if len(kept) else kept
        print(f"\n    {tier.upper():12} in={n_in}  passed_gates={len(kept)}")
        if len(scored):
            top = scored.sort_values('composite_score_12m', ascending=False).head(5)
            for r in top.itertuples():
                print(f"        {r.ticker:8} 12m={r.composite_score_12m:5.1f}")

    # [4]/[5] cross-tier scoring crossover.
    print("\n[4/5] Cross-tier scoring crossover (same batch, different tier weights):")
    batch = crossover_batch()
    core = calculate_horizon_scores(batch.copy(), tier='core').set_index('ticker')
    growth = calculate_horizon_scores(batch.copy(), tier='growth').set_index('ticker')

    def s(name, frame):
        return float(frame.loc[name, 'composite_score_12m'])

    for name in ('CRDO', 'AXON'):
        g, c = s(name, growth), s(name, core)
        ok = g > c
        print(f"    {name}: Growth={g:.1f} Core={c:.1f}  Growth>Core: {ok}")
        assert ok, f"FAIL: {name} should score higher in Growth than Core"
    for name in ('AVGO', 'MSFT'):
        c, g = s(name, core), s(name, growth)
        ok = c > g
        print(f"    {name}: Core={c:.1f} Growth={g:.1f}  Core>Growth: {ok}")
        assert ok, f"FAIL: {name} should score higher in Core than Growth"

    print("\nAll tier assertions passed.")


if __name__ == "__main__":
    main()
