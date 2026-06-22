"""
Stock Screener Module
Implements screening logic for high-growth stocks
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from data_fetcher import StockDataFetcher
from ticker_universe import get_full_universe, get_ticker_sectors
from edgar_fetcher import EDGARDataFetcher, EDGARScreeningEnhancer

class GrowthStockScreener:
    """Screen stocks based on growth metrics and other criteria"""

    def __init__(self, fetcher: Optional[StockDataFetcher] = None, use_edgar: bool = False):
        """
        Initialize the screener

        Args:
            fetcher: Optional StockDataFetcher instance
            use_edgar: Whether to include EDGAR data in screening
        """
        self.fetcher = fetcher or StockDataFetcher()
        self.sector_map = get_ticker_sectors()
        self.use_edgar = use_edgar
        if use_edgar:
            self.edgar_enhancer = EDGARScreeningEnhancer()

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

        # Filter by revenue growth
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

        # Calculate additional metrics
        df = self._calculate_scores(df)

        # Add EDGAR data if enabled
        if self.use_edgar and len(df) > 0:
            print("\nEnhancing with EDGAR data (this may take a few minutes)...")
            df = self.edgar_enhancer.enhance_screening_data(df)
            # Recalculate composite score with EDGAR data
            df = self._calculate_scores_with_edgar(df)

        # Sort by composite score
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