"""
High-Growth Stock Screener - Streamlit Application
A web-based stock screening tool for identifying high-growth US stocks
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
from typing import List, Dict, Optional

from data_fetcher import StockDataFetcher
from screener import GrowthStockScreener
from screener_extension import apply_macro_tags
from ticker_universe import (get_full_universe, get_sp500_tickers,
                             get_nasdaq100_additional, get_high_growth_watchlist,
                             get_fmp_universe, get_tiered_universe)
from screener import TIER_GATES

# Page configuration
st.set_page_config(
    page_title="High-Growth Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px;
    }
    .dataframe {
        font-size: 14px;
    }
    div[data-baseweb="select"] {
        margin-top: -25px;
    }
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_universe_options() -> Dict[str, List[str]]:
    """Load different universe options"""
    return {
        "S&P 500 (Large Cap)": get_sp500_tickers(),
        "NASDAQ 100 Additional": get_nasdaq100_additional(),
        "High Growth Watchlist": get_high_growth_watchlist(),
        "Full Universe (~800 stocks)": get_full_universe(),
    }


# Three-tier screening definitions. Order matters for the radio control.
TIER_META = {
    'core': {
        'label': '🏛️ Core ($10B+)', 'universe_key': 'tier1',
        'cap_range': '$10B+', 'growth_floor': 10,
        'emphasis': 'FCF, margins & value (quality compounders)',
    },
    'growth': {
        'label': '🚀 Growth ($1B–$10B)', 'universe_key': 'tier2',
        'cap_range': '$1B–$10B', 'growth_floor': 20,
        'emphasis': 'momentum & growth (high-growth mid-caps)',
    },
    'speculative': {
        'label': '⚡ Speculative ($250M–$1B)', 'universe_key': 'tier3',
        'cap_range': '$250M–$1B', 'growth_floor': 30,
        'emphasis': 'momentum & growth with looser gates (early compounders)',
    },
}
TIER_BY_LABEL = {m['label']: k for k, m in TIER_META.items()}


@st.cache_data(ttl=3600)
def load_tiered_universe() -> Dict[str, List[str]]:
    """Cached tiered universe ({tier1/2/3: [...]}) from FMP."""
    return get_tiered_universe()


def format_large_number(num: float) -> str:
    """Format large numbers with appropriate suffixes"""
    if pd.isna(num):
        return "N/A"
    if num >= 1e12:
        return f"${num/1e12:.2f}T"
    elif num >= 1e9:
        return f"${num/1e9:.2f}B"
    elif num >= 1e6:
        return f"${num/1e6:.2f}M"
    else:
        return f"${num:,.0f}"


def format_percentage(num: float) -> str:
    """Format percentage values"""
    if pd.isna(num):
        return "N/A"
    return f"{num:.1f}%"


def format_eta(seconds: Optional[float]) -> str:
    """Format an estimated-time-remaining value as a human-readable string."""
    if seconds is None or seconds < 0:
        return "calculating..."
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def format_pct_decimal(num: float) -> str:
    """Format a decimal ratio (e.g. 0.25) as a percentage string (e.g. 25.0%)."""
    if pd.isna(num):
        return "N/A"
    return f"{num * 100:.1f}%"


def format_signed_dollar(num: float) -> str:
    """Format a signed dollar value, e.g. +$2.4M / -$8.1M."""
    if pd.isna(num):
        return "N/A"
    sign = '+' if num >= 0 else '-'
    a = abs(num)
    if a >= 1e9:
        body = f"${a / 1e9:.1f}B"
    elif a >= 1e6:
        body = f"${a / 1e6:.1f}M"
    elif a >= 1e3:
        body = f"${a / 1e3:.1f}K"
    else:
        body = f"${a:.0f}"
    return sign + body


def color_revenue_growth(val):
    """Color code revenue growth values"""
    if pd.isna(val):
        return ''
    if val >= 50:
        color = 'darkgreen'
    elif val >= 20:
        color = 'green'
    elif val >= 0:
        color = 'orange'
    else:
        color = 'red'
    return f'color: {color}; font-weight: bold'


def main():
    """Main Streamlit application"""

    # Header
    st.title("📈 High-Growth Stock Screener")
    st.markdown("**Screen US-listed stocks for high revenue growth and forward momentum**")

    # Sidebar for screening parameters
    st.sidebar.header("🎯 Screening Criteria")

    # Primary control: three-tier selector (default Growth).
    st.sidebar.subheader("🎚️ Screening Tier")
    tier_label = st.sidebar.radio(
        "Tier",
        options=[TIER_META[k]['label'] for k in ('core', 'growth', 'speculative')],
        index=1,  # default Growth
        help="Tier sets the market-cap range, forward-growth floor, gate "
             "thresholds and factor weights",
    )
    tier = TIER_BY_LABEL[tier_label]
    tier_meta = TIER_META[tier]

    # Load this tier's universe (FMP tiered, cached; static split fallback).
    try:
        tiered = load_tiered_universe()
        tickers = tiered.get(tier_meta['universe_key'], [])
    except Exception as e:
        st.sidebar.warning(f"⚠️ Tiered universe fetch failed ({e}); static fallback.")
        tickers = get_full_universe()

    if not tickers:
        tickers = []
        st.sidebar.warning("⚠️ No tickers available for this tier.")
    else:
        st.sidebar.info(f"📊 {tier_meta['cap_range']} • {len(tickers)} stocks")

    # Revenue growth criteria
    st.sidebar.subheader("Growth Metrics")
    min_revenue_growth = st.sidebar.slider(
        "Min Revenue Growth YoY (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=5.0,
        help="Optional: minimum year-over-year revenue growth. 0 = show all."
    )

    require_positive_forward = st.sidebar.checkbox(
        "Require positive forward estimates",
        value=False,
        help="Only show stocks with positive forward revenue estimates"
    )

    # Market cap filter
    st.sidebar.subheader("Market Cap")
    market_cap_options = {
        "All Caps": 0,
        "Micro Cap (>$50M)": 50e6,
        "Small Cap (>$300M)": 300e6,
        "Mid Cap (>$2B)": 2e9,
        "Large Cap (>$10B)": 10e9,
        "Mega Cap (>$100B)": 100e9,
    }

    selected_market_cap = st.sidebar.selectbox(
        "Minimum Market Cap",
        list(market_cap_options.keys()),
        index=0,  # Default to All Caps (no cutoff)
        help="Optional: filter by minimum market capitalization"
    )
    min_market_cap = market_cap_options[selected_market_cap]

    # Valuation filters
    st.sidebar.subheader("Valuation")
    max_pe_ratio = st.sidebar.number_input(
        "Max P/E Ratio",
        min_value=0.0,
        value=0.0,
        step=10.0,
        help="Optional: maximum price-to-earnings ratio (0 = no limit)"
    )

    require_positive_earnings = st.sidebar.checkbox(
        "Profitable companies only",
        value=False,
        help="Only show companies with positive earnings"
    )

    # Sector filters
    st.sidebar.subheader("Sector Filters")
    sectors = [
        "Technology", "Healthcare", "Financials", "Consumer Discretionary",
        "Communication Services", "Industrials", "Consumer Staples",
        "Energy", "Utilities", "Real Estate", "Materials"
    ]

    exclude_sectors = st.sidebar.multiselect(
        "Exclude sectors",
        sectors,
        default=[],
        help="Optional: sectors to exclude from screening (none by default)"
    )

    # Analyst coverage
    st.sidebar.subheader("Analyst Coverage")
    require_analyst_coverage = st.sidebar.checkbox(
        "Require analyst coverage",
        value=False,
        help="Optional: only show stocks with analyst coverage"
    )

    min_analyst_buy_percent = st.sidebar.slider(
        "Min Buy Rating (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=10.0,
        help="Minimum percentage of analyst buy ratings",
        disabled=not require_analyst_coverage
    )

    # Advanced options
    with st.sidebar.expander("⚙️ Advanced Options"):
        refresh_cache = st.checkbox(
            "Force refresh data",
            value=False,
            help="Clear cache and fetch fresh data"
        )

        export_csv = st.checkbox(
            "Enable CSV export",
            value=True,
            help="Show option to export results to CSV"
        )

        show_scores = st.checkbox(
            "Show scoring metrics",
            value=False,
            help="Display detailed scoring breakdown"
        )

        use_edgar = st.checkbox(
            "Include EDGAR Analysis",
            value=False,
            help="Analyze SEC filings (10-K, 10-Q) for deeper insights. Note: This significantly increases processing time."
        )

    # Hard universe gates — defaults are tier-aware (change with the tier) and
    # still tunable. Widget keys include the tier so switching tier resets the
    # defaults to that tier's thresholds.
    tg = TIER_GATES[tier]
    st.sidebar.subheader("🚧 Hard Universe Gates")
    with st.sidebar.expander(f"Exclusion thresholds ({tier_meta['cap_range']})"):
        gate_min_revenue_ttm = st.number_input(
            "Min revenue TTM ($)", min_value=0.0, value=float(tg['min_revenue_ttm']),
            step=10_000_000.0, key=f"gate_rev_{tier}",
            help="Drop tickers with revenue_ttm NaN/zero or below this",
        )
        gate_fcf_margin_floor = st.number_input(
            "FCF margin floor", min_value=-1.0, max_value=0.0, value=float(tg['fcf_margin_floor']),
            step=0.05, key=f"gate_fcf_{tier}",
            help="Drop tickers with fcf_margin below this (e.g. -0.20 = -20%)",
        )
        gate_max_ev_ebitda = st.number_input(
            "Max EV/EBITDA", min_value=0.0, value=float(tg['max_ev_ebitda']), step=5.0,
            key=f"gate_ev_{tier}",
            help="Drop tickers with EV/EBITDA above this (NaN kept)",
        )
        gate_biotech_gross_margin = st.number_input(
            "Biotech proxy: gross margin >", min_value=0.0, max_value=1.0, value=0.85, step=0.01,
            key=f"gate_biogm_{tier}",
            help="Part of the grant/collaboration-revenue proxy gate "
                 + ("(skipped for Speculative)" if not tg['apply_biotech'] else ""),
        )
        gate_biotech_max_revenue = st.number_input(
            "Biotech proxy: revenue <", min_value=0.0, value=500_000_000.0, step=50_000_000.0,
            key=f"gate_biorev_{tier}",
            help="Drop if gross margin > threshold AND revenue below this",
        )
        gate_min_forward_growth_pct = st.slider(
            "Min forward revenue growth (%)", min_value=0.0, max_value=40.0,
            value=float(tg['min_forward_revenue_growth'] * 100), step=1.0,
            key=f"gate_fwd_{tier}",
            help="Drop tickers whose forward revenue growth is below this "
                 "(NaN forward growth is kept and penalized instead)",
        )
        exclude_flagged = st.checkbox(
            "Exclude SEC-flagged stocks", value=False, key=f"excl_sec_{tier}",
            help="Hide tickers with sec_investigation_flag = True",
        )
        exclude_china_adr = st.checkbox(
            "Exclude China ADRs", value=True, key=f"excl_cn_{tier}",
            help="Hide tickers flagged china_adr = True",
        )

    # Shared kwargs for both run buttons.
    common_kwargs = dict(
        min_revenue_growth=min_revenue_growth,
        min_market_cap=min_market_cap,
        max_pe_ratio=max_pe_ratio,
        exclude_sectors=exclude_sectors,
        require_positive_earnings=require_positive_earnings,
        require_analyst_coverage=require_analyst_coverage,
        min_analyst_buy_percent=min_analyst_buy_percent,
        require_positive_forward=require_positive_forward,
        show_scores=show_scores,
        export_csv=export_csv,
        refresh_cache=refresh_cache,
        use_edgar=use_edgar,
        gate_biotech_gross_margin=gate_biotech_gross_margin,
        gate_biotech_max_revenue=gate_biotech_max_revenue,
        exclude_flagged=exclude_flagged,
        exclude_china_adr=exclude_china_adr,
    )

    # Run screening button (single tier).
    if st.sidebar.button(f"🚀 Run {tier_meta['label'].split(' ')[1]} Screen",
                         type="primary", use_container_width=True):
        st.session_state.pop('all_tiers', None)
        run_screening(
            tickers=tickers, tier=tier,
            gate_min_revenue_ttm=gate_min_revenue_ttm,
            gate_fcf_margin_floor=gate_fcf_margin_floor,
            gate_max_ev_ebitda=gate_max_ev_ebitda,
            gate_min_forward_revenue_growth=gate_min_forward_growth_pct / 100.0,
            **common_kwargs,
        )

    # Run All Tiers button — screen every tier with its own gates/weights.
    if st.sidebar.button("🌐 Run All Tiers", use_container_width=True):
        run_all_tiers(common_kwargs)

    # Horizon to sort the results table by (12m / 24m / 36m).
    st.sidebar.subheader("Ranking Horizon")
    sort_horizon = st.sidebar.radio(
        "Sort by",
        options=['12m', '24m', '36m'],
        index=0,  # default 12m
        horizontal=True,
        help="Which horizon score ranks the results table",
    )

    # Main content area.
    if st.session_state.get('all_tiers'):
        show_all_tiers(st.session_state.all_tiers)
    elif 'results_df' in st.session_state:
        show_results(st.session_state.results_df, show_scores, export_csv, sort_horizon,
                     tier=st.session_state.get('results_tier', 'growth'))
    else:
        show_welcome_screen()


def show_welcome_screen():
    """Display welcome screen with instructions"""
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Stock Universe", "800+", "US-listed stocks")
    with col2:
        st.metric("Data Source", "yfinance", "Real-time data")
    with col3:
        st.metric("Update Frequency", "Hourly", "Cached results")

    st.markdown("---")

    st.subheader("📋 How to Use")
    st.markdown("""
    1. **Select Universe**: Choose from S&P 500, NASDAQ 100, or full universe
    2. **Set Criteria**: Adjust revenue growth, market cap, and other filters
    3. **Run Screener**: Click the button to start screening
    4. **Analyze Results**: Sort and filter the results table
    5. **Export Data**: Download results as CSV for further analysis
    """)

    st.subheader("🎯 Default Screening Criteria")
    st.markdown("""
    - **Revenue Growth**: >20% year-over-year
    - **Market Cap**: >$2 billion (Mid Cap+)
    - **P/E Ratio**: <100
    - **Excluded Sectors**: Utilities, Real Estate
    - **Analyst Coverage**: Required
    """)

    st.info("💡 **Tip**: Start with S&P 500 for faster results, then expand to full universe for comprehensive screening")


def run_screening(
    tickers: List[str],
    min_revenue_growth: float,
    min_market_cap: float,
    max_pe_ratio: float,
    exclude_sectors: List[str],
    require_positive_earnings: bool,
    require_analyst_coverage: bool,
    min_analyst_buy_percent: float,
    require_positive_forward: bool,
    show_scores: bool,
    export_csv: bool,
    refresh_cache: bool,
    use_edgar: bool = False,
    tier: str = 'growth',
    gate_min_revenue_ttm: float = None,
    gate_fcf_margin_floor: float = None,
    gate_max_ev_ebitda: float = None,
    gate_biotech_gross_margin: float = 0.85,
    gate_biotech_max_revenue: float = 500_000_000.0,
    gate_min_forward_revenue_growth: float = None,
    exclude_flagged: bool = False,
    exclude_china_adr: bool = True,
):
    """Run the stock screening process"""

    # Clear cache if requested
    if refresh_cache:
        st.cache_data.clear()

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(current, total, ticker, eta_seconds=None):
        progress = (current / total) if total else 0
        progress_bar.progress(min(max(progress, 0.0), 1.0))
        msg = f"Fetching {current}/{total}: {ticker}"
        if eta_seconds is not None:
            msg += f"  •  ~{format_eta(eta_seconds)} remaining"
        status_text.text(msg)

    # Initialize screener with rate-limit-friendly fetching + SQLite caching.
    # refresh_cache (Force refresh data) bypasses the cache for this run but
    # still writes fresh results back so later runs in the day stay fast.
    fetcher = StockDataFetcher(
        rate_limit_delay=0.1,
        min_ticker_delay=1.5,
        max_ticker_delay=2.0,
        batch_size=25,
        batch_delay=10.0,
        use_cache=True,
        cache_max_age_hours=24.0,
        force_refresh=refresh_cache,
    )
    # Fetch the extended FMP fields (gross margin, FCF, beat rate, short
    # interest, insider activity, rule of 40, etc.) so they are available as
    # display columns.
    fetcher.enable_extended = True
    screener = GrowthStockScreener(
        fetcher, use_edgar=use_edgar, tier=tier,
        gate_min_revenue_ttm=gate_min_revenue_ttm,
        gate_fcf_margin_floor=gate_fcf_margin_floor,
        gate_max_ev_ebitda=gate_max_ev_ebitda,
        gate_biotech_gross_margin=gate_biotech_gross_margin,
        gate_biotech_max_revenue=gate_biotech_max_revenue,
        gate_active_listing=True,
        gate_min_forward_revenue_growth=gate_min_forward_revenue_growth,
    )
    st.session_state.results_tier = tier

    # Run screening
    try:
        with st.spinner("Screening stocks... This may take a few minutes for large universes"):
            results_df = screener.screen_stocks(
                tickers=tickers,
                min_revenue_growth=min_revenue_growth,
                min_market_cap=min_market_cap,
                max_pe_ratio=max_pe_ratio,
                exclude_sectors=exclude_sectors,
                require_positive_earnings=require_positive_earnings,
                require_analyst_coverage=require_analyst_coverage,
                min_analyst_buy_percent=min_analyst_buy_percent,
                progress_callback=update_progress
            )

            # Filter for positive forward estimates if required
            if require_positive_forward and len(results_df) > 0:
                # Check if columns exist before filtering
                has_forward_rev = 'forward_revenue_estimate' in results_df.columns
                has_implied_growth = 'implied_earnings_growth' in results_df.columns

                if has_forward_rev and has_implied_growth:
                    # Both columns exist
                    mask = (
                        (pd.notna(results_df['forward_revenue_estimate']) &
                         (results_df['forward_revenue_estimate'] > 0)) |
                        (pd.notna(results_df['implied_earnings_growth']) &
                         (results_df['implied_earnings_growth'] > 0))
                    )
                    results_df = results_df[mask]
                elif has_forward_rev:
                    # Only forward revenue exists
                    results_df = results_df[
                        pd.notna(results_df['forward_revenue_estimate']) &
                        (results_df['forward_revenue_estimate'] > 0)
                    ]
                elif has_implied_growth:
                    # Only implied growth exists
                    results_df = results_df[
                        pd.notna(results_df['implied_earnings_growth']) &
                        (results_df['implied_earnings_growth'] > 0)
                    ]
                # If neither column exists, skip filtering

            # Add rule-based macro tags (rate_sensitive, ai_infrastructure, etc.)
            # as a post-processing step so they appear as display columns.
            if len(results_df) > 0:
                try:
                    results_df = apply_macro_tags(results_df)
                except Exception as tag_err:
                    print(f"Macro tagging failed: {tag_err}")

            # Optional filter: hide SEC-flagged stocks (filter, not gate).
            if exclude_flagged and 'sec_investigation_flag' in results_df.columns:
                results_df = results_df[results_df['sec_investigation_flag'] != True]  # noqa: E712

            # Optional filter: hide China ADRs (Fix 4 — after gates, before display).
            if exclude_china_adr and 'china_adr' in results_df.columns:
                results_df = results_df[results_df['china_adr'] != True]  # noqa: E712

            # Store results in session state
            st.session_state.results_df = results_df

            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()

            # Show success message
            st.success(f"✅ Screening complete! Found {len(results_df)} stocks matching criteria")

    except Exception as e:
        st.error(f"❌ Error during screening: {str(e)}")
        progress_bar.empty()
        status_text.empty()


def _run_tier_screen(tickers, tier, common_kwargs):
    """Screen one tier (its own gates + weights) and return the processed df."""
    fetcher = StockDataFetcher(
        rate_limit_delay=0.1, min_ticker_delay=1.5, max_ticker_delay=2.0,
        batch_size=25, batch_delay=10.0, use_cache=True, cache_max_age_hours=24.0,
        force_refresh=common_kwargs.get('refresh_cache', False),
    )
    fetcher.enable_extended = True
    screener = GrowthStockScreener(
        fetcher, use_edgar=common_kwargs.get('use_edgar', False), tier=tier,
        gate_biotech_gross_margin=common_kwargs.get('gate_biotech_gross_margin', 0.85),
        gate_biotech_max_revenue=common_kwargs.get('gate_biotech_max_revenue', 500_000_000.0),
        gate_active_listing=True,
    )
    df = screener.screen_stocks(
        tickers=tickers,
        min_revenue_growth=common_kwargs.get('min_revenue_growth', 0.0),
        min_market_cap=common_kwargs.get('min_market_cap', 0.0),
        max_pe_ratio=common_kwargs.get('max_pe_ratio', 0.0),
        exclude_sectors=common_kwargs.get('exclude_sectors') or None,
        require_positive_earnings=common_kwargs.get('require_positive_earnings', False),
        require_analyst_coverage=common_kwargs.get('require_analyst_coverage', False),
        min_analyst_buy_percent=common_kwargs.get('min_analyst_buy_percent', 0.0),
    )
    if df is None or len(df) == 0:
        return df
    try:
        df = apply_macro_tags(df)
    except Exception as e:
        print(f"Macro tagging failed: {e}")
    if common_kwargs.get('exclude_flagged') and 'sec_investigation_flag' in df.columns:
        df = df[df['sec_investigation_flag'] != True]  # noqa: E712
    if common_kwargs.get('exclude_china_adr') and 'china_adr' in df.columns:
        df = df[df['china_adr'] != True]  # noqa: E712
    return df


def run_all_tiers(common_kwargs):
    """Screen all three tiers and stash the results for the cross-tier view."""
    if common_kwargs.get('refresh_cache'):
        st.cache_data.clear()
    try:
        tiered = load_tiered_universe()
    except Exception as e:
        st.error(f"Tiered universe fetch failed: {e}")
        return
    results = {}
    prog = st.progress(0)
    status = st.empty()
    for i, t in enumerate(('core', 'growth', 'speculative')):
        meta = TIER_META[t]
        tks = tiered.get(meta['universe_key'], [])
        status.text(f"Screening {meta['label']} ({len(tks)} tickers)...")
        try:
            results[t] = _run_tier_screen(tks, t, common_kwargs)
        except Exception as e:
            st.warning(f"{meta['label']} failed: {e}")
            results[t] = None
        prog.progress((i + 1) / 3)
    prog.empty()
    status.empty()
    st.session_state.all_tiers = results
    st.session_state.pop('results_df', None)
    st.success("✅ All tiers screened.")


def show_all_tiers(results):
    """Cross-tier view: top 20 by 12m score in each tier, collapsible."""
    st.header("🌐 All Tiers — Cross-Tier View")
    st.caption("Top 20 by 12m score in each tier (each scored with its own gates & weights).")
    for t in ('core', 'growth', 'speculative'):
        meta = TIER_META[t]
        df = results.get(t)
        n = 0 if df is None else len(df)
        with st.expander(f"{meta['label']} — {n} stocks scored", expanded=(t == 'growth')):
            if df is None or n == 0:
                st.write("No stocks passed this tier's gates.")
                continue
            top = df.sort_values('composite_score_12m', ascending=False).head(20)
            cols = [c for c in ['ticker', 'company_name', 'sector', 'market_cap',
                                'revenue_growth_yoy', 'forward_revenue_growth', 'momentum_12_1',
                                'composite_score_12m', 'composite_score_24m', 'composite_score_36m']
                    if c in top.columns]
            disp = top[cols].copy()
            if 'market_cap' in disp.columns:
                disp['market_cap'] = disp['market_cap'].apply(format_large_number)
            st.dataframe(disp, hide_index=True, use_container_width=True)


# Column order for the Growth/Speculative tiers — lead with growth signals,
# push valuation later (df column names; only those present are shown).
GROWTH_TIER_COLUMN_ORDER = [
    # Identity
    'ticker', 'company_name', 'sector', 'country', 'market_cap', 'tier',
    # Growth
    'revenue_growth_yoy', 'forward_revenue_growth', 'growth_deceleration', 'net_margin_trend',
    # Momentum
    'momentum_12_1', 'return_6m', 'return_1yr', 'return_3yr', 'relative_strength_vs_voo_12m',
    # Quality
    'gross_margin', 'gross_margin_expansion', 'earnings_quality_ratio',
    # Sentiment
    'eps_revision_net', 'revenue_estimate_revision', 'analyst_buy_percent',
    'num_analysts', 'analyst_coverage_weight', 'forward_estimate_missing',
    # Profitability
    'fcf_margin', 'rule_of_40',
    # Valuation (moved later for growth tiers)
    'forward_pe', 'ev_ebitda',
    # Risk / flow
    'short_interest_pct_float', 'debt_trend', 'institutional_ownership_change', 'insider_net_value_3m',
    # Flags
    'rate_sensitive', 'ai_infrastructure', 'china_adr', 'sec_investigation_flag',
    # Data quality + scores
    'data_quality_score',
    'composite_score_12m', 'composite_score_24m', 'composite_score_36m',
]


def show_results(df: pd.DataFrame, show_scores: bool, export_csv: bool,
                 sort_horizon: str = '12m', tier: str = 'growth'):
    """Display screening results"""

    if df.empty:
        st.warning("No stocks found matching the criteria. Try adjusting the filters.")
        return

    # Sort by the selected horizon score (falls back to composite_score).
    score_cols = ['composite_score_12m', 'composite_score_24m', 'composite_score_36m']
    sort_col = f'composite_score_{sort_horizon}'
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False)
    elif 'composite_score' in df.columns:
        df = df.sort_values('composite_score', ascending=False)

    # Tier header + description.
    meta = TIER_META.get(tier, TIER_META['growth'])
    tier_word = meta['label'].split(' ')[1]
    st.header(f"{meta['label'].split(' ')[0]} {tier_word} Screen — {len(df)} stocks scored")
    st.caption(f"Market cap {meta['cap_range']} • forward-growth floor {meta['growth_floor']}% • "
               f"scoring emphasis: {meta['emphasis']}.")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Found", len(df))
    with col2:
        avg_growth = df['revenue_growth_yoy'].mean()
        st.metric("Avg Revenue Growth", format_percentage(avg_growth))
    with col3:
        total_market_cap = df['market_cap'].sum()
        st.metric("Total Market Cap", format_large_number(total_market_cap))
    with col4:
        avg_metric_col = sort_col if sort_col in df.columns else 'composite_score'
        avg_score = df[avg_metric_col].mean() if avg_metric_col in df.columns else float('nan')
        st.metric(f"Avg Score ({sort_horizon})", f"{avg_score:.1f}")

    st.markdown("---")

    # Results table
    st.subheader("📊 Screening Results")

    # Check if EDGAR data is available
    has_edgar = 'edgar_score' in df.columns

    # Column selection based on show_scores setting and EDGAR availability
    if show_scores:
        display_columns = [
            'ticker', 'company_name', 'sector', 'country', 'market_cap', 'current_price',
            'revenue_growth_yoy', 'revenue_growth_qoq', 'pe_ratio', 'forward_pe',
            'analyst_buy_percent', 'target_mean_price',
            'revenue_growth_score', 'forward_growth_score', 'valuation_score',
            'analyst_score', 'momentum_score'
        ]
        if has_edgar:
            display_columns.extend(['edgar_score', 'mda_sentiment', 'growth_mentions'])
        display_columns.extend(score_cols)
    else:
        display_columns = [
            'ticker', 'company_name', 'sector', 'country', 'market_cap', 'current_price',
            'revenue_growth_yoy', 'forward_pe', 'analyst_buy_percent',
            'target_mean_price'
        ]
        if has_edgar:
            display_columns.extend(['mda_sentiment', 'edgar_score'])
        display_columns.extend(score_cols)

    # New FMP-derived columns to surface in the table (inserted just before the
    # composite score). Only those actually present in the dataframe are added.
    new_fmp_columns = [
        # Momentum group (momentum_12_1 + display-only trailing returns)
        'momentum_12_1', 'return_6m', 'return_1yr', 'return_3yr',
        # Growth group
        'gross_margin', 'fcf_margin', 'fcf_yield', 'growth_deceleration',
        'earnings_beat_rate', 'eps_revision_net', 'rule_of_40',
        # Sentiment group
        'num_analysts', 'analyst_coverage_weight', 'forward_estimate_missing',
        # Data quality
        'data_quality_score',
        # Risk / flow group
        'short_interest_pct_float', 'insider_net_3m', 'insider_net_value_3m',
        'sec_investigation_flag', 'rate_sensitive', 'ai_infrastructure',
    ]
    present_new = [c for c in new_fmp_columns if c in df.columns]
    # Insert just before the first horizon-score column.
    insert_anchor = next((c for c in score_cols if c in display_columns), None)
    if insert_anchor is not None:
        idx = display_columns.index(insert_anchor)
        display_columns[idx:idx] = present_new
    else:
        display_columns.extend(present_new)

    # Add the 'tier' column to the identity group when present.
    if 'tier' in df.columns and 'tier' not in display_columns:
        anchor = 'market_cap' if 'market_cap' in display_columns else display_columns[0]
        display_columns.insert(display_columns.index(anchor) + 1, 'tier')

    # Growth / Speculative tiers: reorder column groups to lead with growth
    # signals and push valuation later (Core keeps the default valuation-led order).
    if tier in ('growth', 'speculative'):
        ordered_nonscore = [c for c in GROWTH_TIER_COLUMN_ORDER
                            if c in df.columns and c not in score_cols]
        extras_nonscore = [c for c in display_columns
                           if c in df.columns and c not in ordered_nonscore and c not in score_cols]
        display_columns = (ordered_nonscore + extras_nonscore
                           + [c for c in score_cols if c in df.columns])

    # Filter columns that exist
    display_columns = [col for col in display_columns if col in df.columns]

    # Format the dataframe for display
    display_df = df[display_columns].copy()

    # Percentage-formatted columns (stored as decimals -> shown as %).
    for pct_col in ['gross_margin', 'fcf_margin', 'fcf_yield']:
        if pct_col in display_df.columns:
            display_df[pct_col] = display_df[pct_col].apply(format_pct_decimal)

    # growth_deceleration kept numeric (Styler formats it as +/-pp with color).
    if 'growth_deceleration' in display_df.columns:
        display_df['growth_deceleration'] = pd.to_numeric(
            display_df['growth_deceleration'], errors='coerce').round(1)

    # Dollar-weighted insider flow -> signed dollar string (+$2.4M / -$8.1M).
    if 'insider_net_value_3m' in display_df.columns:
        display_df['insider_net_value_3m'] = display_df['insider_net_value_3m'].apply(format_signed_dollar)

    # Numeric columns rounded for tidy display.
    for num_col, ndigits in [
        ('earnings_beat_rate', 1), ('eps_revision_net', 0),
        ('short_interest_pct_float', 4), ('insider_net_3m', 0),
        ('rule_of_40', 1),
    ]:
        if num_col in display_df.columns:
            display_df[num_col] = pd.to_numeric(display_df[num_col], errors='coerce').round(ndigits)

    # Booleans displayed as-is (True/False).
    for bool_col in ['rate_sensitive', 'ai_infrastructure', 'sec_investigation_flag',
                     'forward_estimate_missing', 'china_adr']:
        if bool_col in display_df.columns:
            display_df[bool_col] = display_df[bool_col].astype('boolean')

    # Generic 1-dp rounding for the additional numeric factors surfaced in the
    # tier-ordered table (raw values; just tidy them for display).
    for num_col in ['net_margin_trend', 'momentum_12_1', 'relative_strength_vs_voo_12m',
                    'revenue_estimate_revision', 'debt_trend', 'institutional_ownership_change',
                    'forward_revenue_growth', 'ev_ebitda',
                    'return_6m', 'return_1yr', 'return_3yr']:
        if num_col in display_df.columns:
            display_df[num_col] = pd.to_numeric(display_df[num_col], errors='coerce').round(2)

    # Fix 1: coverage weight (0-1, 2dp) and analyst count (int).
    if 'analyst_coverage_weight' in display_df.columns:
        display_df['analyst_coverage_weight'] = pd.to_numeric(
            display_df['analyst_coverage_weight'], errors='coerce').round(2)
    if 'num_analysts' in display_df.columns:
        display_df['num_analysts'] = pd.to_numeric(
            display_df['num_analysts'], errors='coerce').round(0).astype('Int64')

    # Fix 4: data quality 0-100 with a ⚠ warning when < 50 (less than half the
    # scored factors populated -> interpret the composite cautiously).
    if 'data_quality_score' in display_df.columns:
        display_df['data_quality_score'] = display_df['data_quality_score'].apply(
            lambda v: (f"⚠ {int(v)}" if v < 50 else f"{int(v)}") if pd.notna(v) else "N/A")

    # Format columns
    if 'market_cap' in display_df.columns:
        display_df['market_cap'] = display_df['market_cap'].apply(format_large_number)

    if 'current_price' in display_df.columns:
        display_df['current_price'] = display_df['current_price'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")

    if 'target_mean_price' in display_df.columns:
        display_df['target_mean_price'] = display_df['target_mean_price'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")

    # Keep the three horizon score columns numeric (for the color gradient).
    for sc in score_cols:
        if sc in display_df.columns:
            display_df[sc] = pd.to_numeric(display_df[sc], errors='coerce').round(1)

    # Rename columns for display
    column_rename = {
        'composite_score_12m': 'Score 12m',
        'composite_score_24m': 'Score 24m',
        'composite_score_36m': 'Score 36m',
        'ticker': 'Ticker',
        'company_name': 'Company',
        'sector': 'Sector',
        'country': 'Country',
        'tier': 'Tier',
        'forward_estimate_missing': 'Fwd Est Missing',
        'net_margin_trend': 'Net Margin Trend',
        'momentum_12_1': 'Momentum 12-1',
        'return_6m': 'Return 6m',
        'return_1yr': 'Return 1yr',
        'return_3yr': 'Return 3yr',
        'relative_strength_vs_voo_12m': 'RS vs VOO 12m',
        'revenue_estimate_revision': 'Rev Est Revision',
        'forward_revenue_growth': 'Fwd Rev Growth %',
        'ev_ebitda': 'EV/EBITDA',
        'debt_trend': 'Debt Trend',
        'institutional_ownership_change': 'Inst Own Δ',
        'china_adr': 'China ADR',
        'market_cap': 'Market Cap',
        'current_price': 'Price',
        'revenue_growth_yoy': 'Rev Growth YoY %',
        'revenue_growth_qoq': 'Rev Growth QoQ %',
        'pe_ratio': 'P/E',
        'forward_pe': 'Fwd P/E',
        'analyst_buy_percent': 'Buy %',
        'target_mean_price': 'Target',
        'composite_score': 'Score',
        'revenue_growth_score': 'Growth Score',
        'forward_growth_score': 'Fwd Score',
        'valuation_score': 'Value Score',
        'analyst_score': 'Analyst Score',
        'momentum_score': 'Momentum Score',
        'gross_margin': 'Gross Margin',
        'fcf_margin': 'FCF Margin',
        'fcf_yield': 'FCF Yield',
        'growth_deceleration': 'Growth Decel',
        'earnings_beat_rate': 'Beat Rate %',
        'eps_revision_net': 'EPS Rev Net',
        'num_analysts': '# Analysts',
        'analyst_coverage_weight': 'Coverage Wt',
        'data_quality_score': 'Data Qual',
        'short_interest_pct_float': 'Short % Float',
        'insider_net_3m': 'Insider Net 3m',
        'insider_net_value_3m': 'Insider $ Net 3m',
        'sec_investigation_flag': 'SEC Flag',
        'rule_of_40': 'Rule of 40',
        'rate_sensitive': 'Rate Sensitive',
        'ai_infrastructure': 'AI Infra',
        'edgar_score': 'EDGAR Score',
        'mda_sentiment': 'MD&A Sentiment',
        'growth_mentions': 'Growth Mentions',
        'risk_factors': 'Risk Factors',
        'latest_10k_date': 'Latest 10-K',
        'latest_10q_date': 'Latest 10-Q',
        'edgar_data_quality': 'EDGAR Quality'
    }

    display_df = display_df.rename(columns=column_rename)

    # Color gradient (red = low, green = high) on the three horizon scores, plus
    # green/red text on the growth-deceleration column.
    score_labels = [s for s in ['Score 12m', 'Score 24m', 'Score 36m']
                    if s in display_df.columns]
    table = display_df

    def _decel_color(v):
        if pd.isna(v):
            return ''
        return 'color: green' if v > 0 else ('color: red' if v < 0 else '')

    try:
        sty = display_df.style
        fmt = {}
        if score_labels:
            sty = sty.background_gradient(cmap='RdYlGn', subset=score_labels,
                                          vmin=0, vmax=100)
            fmt.update({lbl: '{:.1f}' for lbl in score_labels})
        if 'Growth Decel' in display_df.columns:
            sty = sty.map(_decel_color, subset=['Growth Decel'])
            fmt['Growth Decel'] = lambda v: f"{v:+.1f}pp" if pd.notna(v) else "N/A"
        # Trailing returns: green/positive, red/negative, formatted +/-X.X%.
        return_labels = [lbl for lbl in ('Return 6m', 'Return 1yr', 'Return 3yr')
                         if lbl in display_df.columns]
        if return_labels:
            sty = sty.map(_decel_color, subset=return_labels)
            for lbl in return_labels:
                fmt[lbl] = lambda v: f"{v:+.1f}%" if pd.notna(v) else "N/A"
        if fmt:
            sty = sty.format(fmt)
        table = sty
    except Exception:
        table = display_df  # fall back to unstyled if Styler unavailable

    column_config = {
        "Rev Growth YoY %": st.column_config.NumberColumn(
            "Rev Growth YoY %",
            help="Year-over-year revenue growth",
            format="%.1f%%",
        ),
        "Buy %": st.column_config.NumberColumn(
            "Buy %",
            help="Percentage of analyst buy ratings",
            format="%.0f%%",
        ),
    }
    for lbl, hz in [('Score 12m', '12m'), ('Score 24m', '24m'), ('Score 36m', '36m')]:
        if lbl in display_df.columns:
            column_config[lbl] = st.column_config.NumberColumn(
                lbl, help=f"{hz} horizon composite score (0-100, higher = better)",
                format="%.1f",
            )

    # Display the dataframe with formatting
    st.dataframe(
        table,
        use_container_width=True,
        height=600,
        column_config=column_config,
        hide_index=True,
    )

    # Export functionality
    if export_csv:
        csv = df.to_csv(index=False)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name=f"stock_screener_results_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Sector breakdown
    with st.expander("📈 Sector Analysis"):
        sector_stats = df.groupby('sector').agg({
            'ticker': 'count',
            'revenue_growth_yoy': 'mean',
            'composite_score': 'mean',
            'market_cap': 'sum'
        }).round(2)

        sector_stats.columns = ['Count', 'Avg Rev Growth %', 'Avg Score', 'Total Market Cap']
        sector_stats = sector_stats.sort_values('Count', ascending=False)
        sector_stats['Total Market Cap'] = sector_stats['Total Market Cap'].apply(format_large_number)

        st.dataframe(sector_stats, use_container_width=True)

    # Top performers
    with st.expander("🏆 Top Performers"):
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Highest Revenue Growth")
            top_growth = df.nlargest(5, 'revenue_growth_yoy')[['ticker', 'company_name', 'revenue_growth_yoy']]
            top_growth['revenue_growth_yoy'] = top_growth['revenue_growth_yoy'].apply(format_percentage)
            st.dataframe(top_growth, hide_index=True, use_container_width=True)

        with col2:
            st.subheader("Highest Composite Score")
            top_score = df.nlargest(5, 'composite_score')[['ticker', 'company_name', 'composite_score']]
            st.dataframe(top_score, hide_index=True, use_container_width=True)

    # EDGAR Insights section (if available)
    if 'edgar_score' in df.columns:
        with st.expander("📑 EDGAR Filing Insights"):
            st.info("Analysis based on latest SEC filings (10-K and 10-Q)")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.subheader("Positive Sentiment Companies")
                positive_sentiment = df[df['mda_sentiment'] == 'positive'][['ticker', 'company_name', 'growth_mentions']].head(5)
                if not positive_sentiment.empty:
                    st.dataframe(positive_sentiment, hide_index=True, use_container_width=True)
                else:
                    st.write("No companies with positive MD&A sentiment")

            with col2:
                st.subheader("High Growth Mentions")
                high_growth = df.nlargest(5, 'growth_mentions')[['ticker', 'company_name', 'growth_mentions']]
                if not high_growth.empty:
                    st.dataframe(high_growth, hide_index=True, use_container_width=True)
                else:
                    st.write("No growth mentions found")

            with col3:
                st.subheader("Low Risk Profile")
                low_risk = df.nsmallest(5, 'risk_factors')[['ticker', 'company_name', 'risk_factors']]
                if not low_risk.empty:
                    st.dataframe(low_risk, hide_index=True, use_container_width=True)
                else:
                    st.write("Risk factor data not available")

            # EDGAR data quality summary
            st.subheader("EDGAR Data Coverage")
            quality_summary = df['edgar_data_quality'].value_counts()
            st.bar_chart(quality_summary)


if __name__ == "__main__":
    main()