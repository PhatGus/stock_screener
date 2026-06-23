"""
Validation for the five universe-construction fixes.

Runs the delisted pre-filter + hard gates + horizon scoring against cached FMP
data if available (ticker_cache.db), otherwise a representative synthetic batch
that includes SPLK (delisted), some inactive listings, China ADRs, and the
slowing-software names ZM / DOCU / OKTA / DBX. Prints:

  * tickers eliminated by the active-listing gate,
  * whether SPLK is in the delisted set and excluded before fetching,
  * tickers eliminated by the forward-growth floor,
  * tickers flagged as China ADR,
  * whether ZM/DOCU/OKTA/DBX are caught by the floor or the decel penalty,
  * top 10 by 12m score after all fixes.
"""

import json
import sqlite3

import numpy as np
import pandas as pd

from screener import apply_hard_gates, calculate_horizon_scores
from fmp_fetcher import CHINA_ADR_TICKERS

CACHE_DB = "ticker_cache.db"
WATCH = ['ZM', 'DOCU', 'OKTA', 'DBX']
# Simulated FMP delisted set (real run pulls /delisted-companies).
MOCK_DELISTED = {'SPLK', 'TWTR', 'ATVI'}


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


def _row(ticker, sector='Technology', rev=1e9, mcap=2e10, fcf=0.12, ev=25.0,
         gm=0.70, rgy=20.0, fwd=None, active=True, country='US'):
    return {
        'ticker': ticker, 'sector': sector, 'country': country,
        'is_actively_trading': active, 'china_adr': ticker in CHINA_ADR_TICKERS
        or country in {'CN', 'China', 'HK', 'Hong Kong'},
        'revenue_ttm': rev, 'market_cap': mcap, 'fcf_margin': fcf, 'ev_ebitda': ev,
        'gross_margin': gm, 'revenue_growth_yoy': rgy, 'forward_revenue_estimate': fwd,
        'momentum_12_1': 8.0, 'eps_revision_net': 1.0, 'earnings_quality_ratio': 1.2,
        'gross_margin_expansion': 0.01, 'fcf_yield': 0.03, 'forward_pe': 25.0,
        'asset_growth': 0.08, 'shareholder_yield': 0.02, 'insider_net_value_3m': 1e6,
        'sec_investigation_flag': False,
    }


def synthesize_batch() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    rows = []
    for i in range(30):
        rgy = float(rng.uniform(12, 35))
        rows.append(_row(f'OK{i:03d}', rev=float(rng.uniform(5e8, 4e10)),
                         mcap=float(rng.uniform(3e9, 4e11)),
                         rgy=rgy, fwd=None))
        rows[-1]['forward_revenue_estimate'] = rows[-1]['revenue_ttm'] * (1 + rgy / 100)
    specials = [
        _row('SPLK', rev=4e9, rgy=20, fwd=4.8e9),           # delisted (acquired) -> pre-filter
        _row('TWTR', rev=5e9, rgy=15, fwd=5.7e9),           # delisted -> pre-filter
        _row('DEADCO', active=False),                       # active-listing gate
        _row('STALE2', active=False),                       # active-listing gate
        _row('BABA', country='CN', rgy=10, fwd=1.12e9, rev=1e9),  # China ADR (kept unless filtered)
        _row('NIO', country='CN', rgy=8, fwd=1.05e9, rev=1e9),    # China ADR + low fwd growth
        _row('ZM', rev=1e9, rgy=10, fwd=1.05e9),            # fwd growth 5% -> floor
        _row('DOCU', rev=1e9, rgy=12, fwd=1.08e9),          # fwd growth 8% -> floor
        _row('OKTA', rev=1e9, rgy=18, fwd=None),            # missing estimate -> conservative decel
        _row('DBX', rev=2e9, rgy=40, fwd=2.3e9),            # 15% fwd vs 40% trailing -> decel penalty
    ]
    return pd.DataFrame(rows + specials)


def main():
    df = load_cached_batch()
    source = "cache"
    if df.empty or 'is_actively_trading' not in df.columns:
        df = synthesize_batch()
        source = "synthetic (no cached FMP data found)"

    print("=" * 68)
    print(f"Universe-fix validation — source: {source}; tickers in: {len(df)}")
    print("=" * 68)

    # Fix 1: delisted pre-filter (mirrors screen_stocks logic).
    all_tickers = list(df['ticker'])
    kept_tickers = [t for t in all_tickers if str(t).upper() not in MOCK_DELISTED]
    excluded_delisted = [t for t in all_tickers if str(t).upper() in MOCK_DELISTED]
    df = df[df['ticker'].isin(kept_tickers)].copy()

    print("\n[1] Delisted pre-filter (before fetch):")
    print(f"    delisted set (sample): {sorted(list(MOCK_DELISTED))}")
    print(f"    SPLK in delisted set: {'SPLK' in MOCK_DELISTED}; "
          f"excluded before fetch: {'SPLK' in excluded_delisted}")
    print(f"    excluded as delisted: {excluded_delisted}")

    kept, stats = apply_hard_gates(df)

    print("\n[2] Active-listing gate eliminations:")
    print(f"    {len(stats['active_listing'])}: {stats['active_listing']}")

    print("\n[3] Forward-growth-floor eliminations:")
    print(f"    {len(stats['min_forward_revenue_growth'])}: {stats['min_forward_revenue_growth']}")

    print("\n[4] China ADR flagged (in full batch):")
    china = df[df['china_adr'] == True]['ticker'].tolist()  # noqa: E712
    print(f"    {len(china)}: {china}")

    # Score the survivors so we can inspect the deceleration penalty.
    scored = calculate_horizon_scores(kept) if len(kept) else kept

    print("\n[5] ZM / DOCU / OKTA / DBX — floor vs deceleration penalty:")
    gate_of = {t: g for g, ts in stats.items() for t in ts}
    for t in WATCH:
        if t in gate_of:
            print(f"    {t}: ELIMINATED by gate '{gate_of[t]}'")
        elif len(scored) and t in set(scored['ticker']):
            r = scored[scored['ticker'] == t].iloc[0]
            decel = r.get('growth_deceleration')
            missing = bool(r.get('forward_estimate_missing'))
            penalized = pd.notna(decel) and decel < -15
            why = "missing fwd est -> conservative -20pp" if missing else f"decel={decel:+.1f}pp"
            print(f"    {t}: kept, deceleration penalty {'APPLIED' if penalized else 'none'} ({why})")
        else:
            print(f"    {t}: not in batch")

    if len(scored):
        print("\n[6] Top 10 by 12m score (after all fixes):")
        top = scored.sort_values('composite_score_12m', ascending=False).head(10)
        for r in top.itertuples():
            print(f"    {r.ticker:8} 12m={r.composite_score_12m:5.1f}")

    print("\nValidation complete.")


if __name__ == "__main__":
    main()
