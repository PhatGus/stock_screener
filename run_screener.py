"""
Extended Stock Screener Runner
==============================

Command-line entry point that runs the existing screener with the new extended
data fields (Groups A-F) and the updated composite score, then writes:

1. The primary results CSV  : ``stock_screener_results_YYYYMMDD_HHMMSS.csv``
                              (all original columns + all new columns)
2. The score delta report   : ``screener_score_delta_YYYYMMDD.csv``
3. The error log            : ``screener_errors.log`` (written during fetching)

and prints a validation summary table to the console.

Usage examples
--------------
    python run_screener.py                       # default: high-growth watchlist
    python run_screener.py --universe sp500
    python run_screener.py --tickers AAPL,MSFT,NVDA
    python run_screener.py --min-revenue-growth 0 --min-market-cap 1e9
"""

import argparse
from datetime import datetime

import pandas as pd

from data_fetcher import StockDataFetcher
from screener import GrowthStockScreener
from screener_extension import (
    apply_extended_scoring,
    apply_macro_tags,
    build_delta_report,
    fetch_voo_returns,
)
from ticker_universe import (
    get_full_universe,
    get_high_growth_watchlist,
    get_sp500_tickers,
)

# New columns added by the extension, in logical group order, so the output CSV
# lists all original columns first and the new ones appended after.
NEW_COLUMN_ORDER = [
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
    # Group F
    'rate_sensitive', 'ai_infrastructure', 'em_fx_exposure', 'hyperscaler_dependent',
    # New scores + backward-comparison columns
    'revenue_growth_score_v1', 'forward_growth_score_v1', 'valuation_score_v1',
    'analyst_score_v1', 'momentum_score_v1', 'composite_score_v1',
    'earnings_quality_score', 'fcf_score', 'moat_score',
]


def resolve_tickers(args) -> list:
    """Resolve the ticker list from CLI arguments."""
    if args.tickers:
        return [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
    if args.universe == 'sp500':
        return get_sp500_tickers()
    if args.universe == 'full':
        return get_full_universe()
    return get_high_growth_watchlist()


def order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep all original columns first, then append the new columns in order."""
    new_cols = [c for c in NEW_COLUMN_ORDER if c in df.columns]
    original = [c for c in df.columns if c not in new_cols]
    return df[original + new_cols]


def print_validation(df: pd.DataFrame, delta: pd.DataFrame, new_columns: list) -> None:
    """Print the validation summary table to the console."""
    n = len(df)
    print("\n=== Screener Extension Validation ===")
    print(f"Tickers processed: {n}")

    # Fields with >20% NaN rate (among the new columns)
    high_nan = []
    for col in new_columns:
        if col in df.columns and df[col].dtype != bool:
            nan_rate = df[col].isna().mean()
            if nan_rate > 0.20:
                high_nan.append(f"{col} ({nan_rate*100:.0f}%)")
    print(f"Fields with >20% NaN rate: {high_nan if high_nan else 'None'}")

    avg_delta = delta['delta'].mean() if not delta.empty else 0.0
    print(f"Average composite_score delta: {avg_delta:.1f} pts")

    top5 = delta.head(5)
    bottom5 = delta.tail(5).iloc[::-1]
    top_str = ", ".join(f"{r.ticker}: {r.delta:+.1f}" for r in top5.itertuples())
    bottom_str = ", ".join(f"{r.ticker}: {r.delta:+.1f}" for r in bottom5.itertuples())
    print(f"Top 5 movers (by delta): [{top_str}]")
    print(f"Bottom 5 movers (by delta): [{bottom_str}]")
    print("=" * 38)


def main():
    parser = argparse.ArgumentParser(description="Run the extended stock screener.")
    parser.add_argument('--universe', choices=['watchlist', 'sp500', 'full'],
                        default='watchlist', help="Ticker universe to screen.")
    parser.add_argument('--tickers', type=str, default=None,
                        help="Comma-separated tickers (overrides --universe).")
    parser.add_argument('--min-revenue-growth', type=float, default=0.0,
                        help="Minimum YoY revenue growth %% filter.")
    parser.add_argument('--min-market-cap', type=float, default=1e9,
                        help="Minimum market capitalization filter.")
    parser.add_argument('--max-pe-ratio', type=float, default=0.0,
                        help="Maximum P/E ratio filter (0 = no limit).")
    parser.add_argument('--exclude-sectors', type=str, default='',
                        help="Comma-separated sectors to exclude.")
    args = parser.parse_args()

    tickers = resolve_tickers(args)
    exclude_sectors = [s.strip() for s in args.exclude_sectors.split(',') if s.strip()]

    print(f"Running extended screener on {len(tickers)} tickers...")

    # --- Preload the VOO benchmark ONCE, before the ticker loop ---
    print("Preloading VOO benchmark returns...")
    voo_returns = fetch_voo_returns(rate_limit_delay=0.5)
    print(f"  VOO 12m/6m/3m returns: "
          f"{voo_returns['voo_return_12m']:.1f}% / "
          f"{voo_returns['voo_return_6m']:.1f}% / "
          f"{voo_returns['voo_return_3m']:.1f}%")

    # --- Wire the extension into the existing fetcher (additive hook) ---
    fetcher = StockDataFetcher(rate_limit_delay=0.1)
    fetcher.enable_extended = True
    fetcher.voo_returns = voo_returns

    screener = GrowthStockScreener(fetcher, use_edgar=False)

    def progress(current, total, ticker):
        print(f"  [{current}/{total}] {ticker}", end='\r')

    df = screener.screen_stocks(
        tickers=tickers,
        min_revenue_growth=args.min_revenue_growth,
        min_market_cap=args.min_market_cap,
        max_pe_ratio=args.max_pe_ratio,
        exclude_sectors=exclude_sectors or None,
        progress_callback=progress,
    )

    if df.empty:
        print("\nNo stocks passed the screening criteria. Nothing to write.")
        return

    # --- Post-processing: macro tags (Group F), then extended scoring ---
    df = apply_macro_tags(df)
    df = apply_extended_scoring(df)

    # Re-sort by the new composite score.
    df = df.sort_values('composite_score', ascending=False).reset_index(drop=True)

    # --- Output ordering and files ---
    df = order_columns(df)

    now = datetime.now()
    results_file = f"stock_screener_results_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    delta_file = f"screener_score_delta_{now.strftime('%Y%m%d')}.csv"

    df.to_csv(results_file, index=False)
    print(f"\nPrimary results written to: {results_file}")

    delta = build_delta_report(df)
    delta.to_csv(delta_file, index=False)
    print(f"Score delta report written to: {delta_file}")

    # --- Validation summary ---
    print_validation(df, delta, NEW_COLUMN_ORDER)


if __name__ == "__main__":
    main()
