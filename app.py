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
from ticker_universe import get_full_universe, get_sp500_tickers, get_nasdaq100_additional, get_high_growth_watchlist

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

    # Universe selection
    st.sidebar.subheader("Stock Universe")
    universe_options = load_universe_options()
    selected_universe = st.sidebar.selectbox(
        "Select stock universe",
        list(universe_options.keys()),
        index=0,
        help="Choose the set of stocks to screen"
    )
    tickers = universe_options.get(selected_universe)
    # Guard against a universe source returning None/empty (e.g. a failed
    # network fetch or a list builder that forgot to return) so we never call
    # len() on None.
    if not tickers:
        tickers = []
        st.sidebar.warning(f"⚠️ No tickers available for '{selected_universe}'.")
    else:
        st.sidebar.info(f"📊 Screening {len(tickers)} stocks")

    # Revenue growth criteria
    st.sidebar.subheader("Growth Metrics")
    min_revenue_growth = st.sidebar.slider(
        "Min Revenue Growth YoY (%)",
        min_value=0.0,
        max_value=100.0,
        value=20.0,
        step=5.0,
        help="Minimum year-over-year revenue growth percentage"
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
        index=3,  # Default to Mid Cap
        help="Filter by minimum market capitalization"
    )
    min_market_cap = market_cap_options[selected_market_cap]

    # Valuation filters
    st.sidebar.subheader("Valuation")
    max_pe_ratio = st.sidebar.number_input(
        "Max P/E Ratio",
        min_value=0.0,
        value=100.0,
        step=10.0,
        help="Maximum price-to-earnings ratio (0 for no limit)"
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
        default=["Utilities", "Real Estate"],
        help="Sectors to exclude from screening"
    )

    # Analyst coverage
    st.sidebar.subheader("Analyst Coverage")
    require_analyst_coverage = st.sidebar.checkbox(
        "Require analyst coverage",
        value=True,
        help="Only show stocks with analyst coverage"
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

    # Run screening button
    if st.sidebar.button("🚀 Run Screener", type="primary", use_container_width=True):
        run_screening(
            tickers=tickers,
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
            use_edgar=use_edgar
        )

    # Main content area - default view
    if 'results_df' not in st.session_state:
        show_welcome_screen()
    else:
        show_results(st.session_state.results_df, show_scores, export_csv)


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
    use_edgar: bool = False
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
    screener = GrowthStockScreener(fetcher, use_edgar=use_edgar)

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


def show_results(df: pd.DataFrame, show_scores: bool, export_csv: bool):
    """Display screening results"""

    if df.empty:
        st.warning("No stocks found matching the criteria. Try adjusting the filters.")
        return

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
        avg_score = df['composite_score'].mean()
        st.metric("Avg Score", f"{avg_score:.1f}")

    st.markdown("---")

    # Results table
    st.subheader("📊 Screening Results")

    # Check if EDGAR data is available
    has_edgar = 'edgar_score' in df.columns

    # Column selection based on show_scores setting and EDGAR availability
    if show_scores:
        display_columns = [
            'ticker', 'company_name', 'sector', 'market_cap', 'current_price',
            'revenue_growth_yoy', 'revenue_growth_qoq', 'pe_ratio', 'forward_pe',
            'analyst_buy_percent', 'target_mean_price',
            'revenue_growth_score', 'forward_growth_score', 'valuation_score',
            'analyst_score', 'momentum_score'
        ]
        if has_edgar:
            display_columns.extend(['edgar_score', 'mda_sentiment', 'growth_mentions'])
        display_columns.append('composite_score')
    else:
        display_columns = [
            'ticker', 'company_name', 'sector', 'market_cap', 'current_price',
            'revenue_growth_yoy', 'forward_pe', 'analyst_buy_percent',
            'target_mean_price'
        ]
        if has_edgar:
            display_columns.extend(['mda_sentiment', 'edgar_score'])
        display_columns.append('composite_score')

    # Filter columns that exist
    display_columns = [col for col in display_columns if col in df.columns]

    # Format the dataframe for display
    display_df = df[display_columns].copy()

    # Format columns
    if 'market_cap' in display_df.columns:
        display_df['market_cap'] = display_df['market_cap'].apply(format_large_number)

    if 'current_price' in display_df.columns:
        display_df['current_price'] = display_df['current_price'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")

    if 'target_mean_price' in display_df.columns:
        display_df['target_mean_price'] = display_df['target_mean_price'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")

    # Rename columns for display
    column_rename = {
        'ticker': 'Ticker',
        'company_name': 'Company',
        'sector': 'Sector',
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
        'edgar_score': 'EDGAR Score',
        'mda_sentiment': 'MD&A Sentiment',
        'growth_mentions': 'Growth Mentions',
        'risk_factors': 'Risk Factors',
        'latest_10k_date': 'Latest 10-K',
        'latest_10q_date': 'Latest 10-Q',
        'edgar_data_quality': 'EDGAR Quality'
    }

    display_df = display_df.rename(columns=column_rename)

    # Display the dataframe with formatting
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
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
            "Score": st.column_config.ProgressColumn(
                "Score",
                help="Composite growth score (0-100)",
                format="%.1f",
                min_value=0,
                max_value=100,
            ),
        },
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