"""
Validation for the six universe/scoring fixes.

Runs the hard gates + horizon scoring against cached FMP data if available
(ticker_cache.db), otherwise a representative synthetic batch that includes
BEAM, FUBO and RUN so the gate behavior can be demonstrated. Prints:

  * how many tickers each hard gate eliminated,
  * whether BEAM / FUBO / RUN were eliminated and by which gate,
  * the top 10 results by 12m score after all fixes,
  * any tickers with sec_investigation_flag = True.
"""

import json
import sqlite3

import numpy as np
import pandas as pd

from screener import apply_hard_gates, calculate_horizon_scores

CACHE_DB = "ticker_cache.db"
WATCH = ['BEAM', 'FUBO', 'RUN']


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


def synthesize_batch(seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sectors = ['Technology', 'Healthcare', 'Financials', 'Industrials',
               'Consumer Discretionary', 'Energy']
    n = 40
    rows = []
    for i in range(n):
        rows.append({
            'ticker': f'OK{i:03d}', 'sector': rng.choice(sectors),
            'revenue_ttm': float(rng.uniform(3e8, 5e10)),
            'market_cap': float(rng.uniform(2e9, 5e11)),
            'fcf_margin': float(rng.uniform(0.0, 0.3)),
            'ev_ebitda': float(rng.uniform(8, 45)),
            'gross_margin': float(rng.uniform(0.3, 0.7)),
            'revenue_growth_yoy': float(rng.uniform(5, 40)),
            'forward_revenue_estimate': None,
            'momentum_12_1': float(rng.normal(10, 25)),
            'eps_revision_net': float(rng.integers(-3, 6)),
            'earnings_quality_ratio': float(rng.uniform(0.5, 2.5)),
            'gross_margin_expansion': float(rng.normal(0.01, 0.03)),
            'fcf_yield': float(rng.uniform(0.0, 0.08)),
            'forward_pe': float(rng.uniform(10, 40)),
            'asset_growth': float(rng.uniform(-0.05, 0.25)),
            'shareholder_yield': float(rng.uniform(0.0, 0.06)),
            'insider_net_value_3m': float(rng.normal(0, 5e6)),
            'sec_investigation_flag': False,
        })
    # forward revenue estimate ~ trailing * (1 + growth/100) with noise
    for r in rows:
        r['forward_revenue_estimate'] = r['revenue_ttm'] * (1 + r['revenue_growth_yoy'] / 100
                                                            + rng.normal(0, 0.05))

    # Named cases that should be eliminated by specific gates.
    specials = [
        # BEAM: pre-commercial biotech, sub-$100M collaboration revenue -> min_revenue_ttm
        {'ticker': 'BEAM', 'sector': 'Healthcare', 'revenue_ttm': 6.0e7, 'market_cap': 3e9,
         'fcf_margin': -2.5, 'ev_ebitda': float('nan'), 'gross_margin': 0.92,
         'revenue_growth_yoy': 10.0, 'forward_revenue_estimate': 6.5e7,
         'insider_net_value_3m': -1e6, 'sec_investigation_flag': False},
        # FUBO: real revenue but structural cash burner -> min_fcf_margin
        {'ticker': 'FUBO', 'sector': 'Communication Services', 'revenue_ttm': 1.4e9,
         'market_cap': 5e8, 'fcf_margin': -0.28, 'ev_ebitda': float('nan'),
         'gross_margin': 0.12, 'revenue_growth_yoy': 25.0, 'forward_revenue_estimate': 1.6e9,
         'insider_net_value_3m': 2e5, 'sec_investigation_flag': False},
        # RUN: heavy negative FCF -> min_fcf_margin
        {'ticker': 'RUN', 'sector': 'Energy', 'revenue_ttm': 2.0e9, 'market_cap': 4e9,
         'fcf_margin': -0.55, 'ev_ebitda': 80.0, 'gross_margin': 0.10,
         'revenue_growth_yoy': 12.0, 'forward_revenue_estimate': 2.1e9,
         'insider_net_value_3m': -5e5, 'sec_investigation_flag': False},
        # A biotech-proxy case (100M-500M revenue, >85% GM) -> revenue_source_proxy
        {'ticker': 'GRNT', 'sector': 'Healthcare', 'revenue_ttm': 3.0e8, 'market_cap': 6e9,
         'fcf_margin': 0.05, 'ev_ebitda': 30.0, 'gross_margin': 0.90,
         'revenue_growth_yoy': 30.0, 'forward_revenue_estimate': 3.6e8,
         'insider_net_value_3m': 1e6, 'sec_investigation_flag': False},
        # An EV/EBITDA ceiling case -> max_ev_ebitda
        {'ticker': 'HOTX', 'sector': 'Technology', 'revenue_ttm': 8.0e8, 'market_cap': 8e10,
         'fcf_margin': 0.10, 'ev_ebitda': 95.0, 'gross_margin': 0.60,
         'revenue_growth_yoy': 45.0, 'forward_revenue_estimate': 1.0e9,
         'insider_net_value_3m': 3e6, 'sec_investigation_flag': False},
        # A passing name carrying an SEC flag (kept, just flagged)
        {'ticker': 'FLAG', 'sector': 'Technology', 'revenue_ttm': 5.0e9, 'market_cap': 4e10,
         'fcf_margin': 0.15, 'ev_ebitda': 22.0, 'gross_margin': 0.55,
         'revenue_growth_yoy': 20.0, 'forward_revenue_estimate': 5.6e9,
         'insider_net_value_3m': -2e6, 'sec_investigation_flag': True},
    ]
    # Fill scoring factors for specials with neutral-ish values.
    for s in specials:
        for k, v in {'momentum_12_1': 5.0, 'eps_revision_net': 0.0,
                     'earnings_quality_ratio': 1.0, 'gross_margin_expansion': 0.0,
                     'fcf_yield': 0.03, 'forward_pe': 25.0, 'asset_growth': 0.1,
                     'shareholder_yield': 0.01}.items():
            s.setdefault(k, v)
        rows.append(s)

    return pd.DataFrame(rows)


def main():
    df = load_cached_batch()
    source = "cache"
    if df.empty or 'fcf_margin' not in df.columns:
        df = synthesize_batch()
        source = "synthetic (no cached FMP data found)"

    print("=" * 66)
    print(f"Fix validation — data source: {source}; tickers in: {len(df)}")
    print("=" * 66)

    kept, stats = apply_hard_gates(df)

    print("\n[A] Tickers eliminated by each hard gate:")
    for gate in ('min_revenue_ttm', 'min_fcf_margin', 'max_ev_ebitda', 'revenue_source_proxy'):
        names = stats.get(gate, [])
        preview = ", ".join(names[:12]) + (" ..." if len(names) > 12 else "")
        print(f"    {gate:22} {len(names):4d}   {preview}")
    print(f"    {'(remaining)':22} {len(kept):4d}")

    print("\n[B] BEAM / FUBO / RUN elimination:")
    gate_of = {t: g for g, ts in stats.items() for t in ts}
    for t in WATCH:
        if t not in set(df['ticker']):
            print(f"    {t}: not in batch")
        elif t in gate_of:
            print(f"    {t}: ELIMINATED by '{gate_of[t]}'")
        else:
            print(f"    {t}: kept (passed all gates)")

    if len(kept) == 0:
        print("\nNo tickers survived the gates; nothing to score.")
        return

    scored = calculate_horizon_scores(kept)

    print("\n[C] Top 10 by 12m score (after all fixes):")
    top = scored.sort_values('composite_score_12m', ascending=False).head(10)
    for r in top.itertuples():
        decel = getattr(r, 'growth_deceleration', float('nan'))
        decel_s = f"{decel:+.1f}pp" if pd.notna(decel) else "n/a"
        print(f"    {r.ticker:8} 12m={r.composite_score_12m:5.1f}  decel={decel_s}")

    print("\n[D] Tickers with sec_investigation_flag = True:")
    if 'sec_investigation_flag' in scored.columns:
        flagged = scored[scored['sec_investigation_flag'] == True]['ticker'].tolist()  # noqa: E712
        print(f"    {flagged if flagged else 'none'}")
    else:
        print("    column not present")

    print("\nValidation complete.")


if __name__ == "__main__":
    main()
