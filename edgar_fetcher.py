"""
EDGAR Data Fetcher Module
Fetches and analyzes SEC filings from EDGAR database
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import re
import time
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
import warnings
warnings.filterwarnings('ignore')

class EDGARDataFetcher:
    """Fetches and processes SEC filings from EDGAR"""

    def __init__(self, user_agent: str = "StockScreener/1.0 (contact@example.com)"):
        """
        Initialize EDGAR fetcher

        Args:
            user_agent: User agent string for SEC API (required by SEC)
        """
        self.base_url = "https://data.sec.gov"
        self.archives_url = "https://www.sec.gov/Archives/edgar/data"
        self.headers = {
            'User-Agent': user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'data.sec.gov'
        }
        self.cache = {}
        self.rate_limit_delay = 0.1  # SEC requires max 10 requests per second

    def get_company_filings(self, ticker: str, filing_type: str = "10-K", limit: int = 5) -> List[Dict]:
        """
        Get recent filings for a company

        Args:
            ticker: Stock ticker symbol
            filing_type: Type of filing (10-K, 10-Q, 8-K, etc.)
            limit: Maximum number of filings to return

        Returns:
            List of filing metadata
        """
        try:
            # Get CIK from ticker
            cik = self._get_cik(ticker)
            if not cik:
                return []

            # Fetch submissions
            url = f"{self.base_url}/submissions/CIK{cik:010d}.json"
            response = requests.get(url, headers=self.headers)
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                print(f"Failed to fetch submissions for {ticker}: {response.status_code}")
                return []

            data = response.json()

            # Extract recent filings
            filings = []
            recent_filings = data.get('filings', {}).get('recent', {})

            forms = recent_filings.get('form', [])
            dates = recent_filings.get('filingDate', [])
            accession_numbers = recent_filings.get('accessionNumber', [])
            primary_docs = recent_filings.get('primaryDocument', [])

            for i in range(min(len(forms), 100)):  # Check recent 100 filings
                if forms[i] == filing_type:
                    filing = {
                        'form': forms[i],
                        'filing_date': dates[i],
                        'accession_number': accession_numbers[i].replace('-', ''),
                        'primary_document': primary_docs[i],
                        'cik': cik,
                        'ticker': ticker
                    }
                    filings.append(filing)

                    if len(filings) >= limit:
                        break

            return filings

        except Exception as e:
            print(f"Error fetching filings for {ticker}: {str(e)}")
            return []

    def _get_cik(self, ticker: str) -> Optional[int]:
        """
        Get CIK (Central Index Key) from ticker symbol

        Args:
            ticker: Stock ticker symbol

        Returns:
            CIK number or None
        """
        try:
            # Check cache
            if ticker in self.cache:
                return self.cache[ticker]

            # Fetch company tickers file
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers={'User-Agent': self.headers['User-Agent']})
            time.sleep(self.rate_limit_delay)

            if response.status_code != 200:
                return None

            companies = response.json()

            # Find CIK for ticker
            for company in companies.values():
                if company.get('ticker', '').upper() == ticker.upper():
                    cik = company.get('cik_str')
                    self.cache[ticker] = cik
                    return cik

            return None

        except Exception as e:
            print(f"Error getting CIK for {ticker}: {str(e)}")
            return None

    def fetch_filing_content(self, filing: Dict) -> Optional[str]:
        """
        Fetch the actual content of a filing

        Args:
            filing: Filing metadata dictionary

        Returns:
            Filing content as string or None
        """
        try:
            cik = filing['cik']
            accession = filing['accession_number']
            document = filing['primary_document']

            url = f"{self.archives_url}/{cik:010d}/{accession}/{document}"
            response = requests.get(url, headers={'User-Agent': self.headers['User-Agent']})
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                return response.text
            else:
                print(f"Failed to fetch filing content: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error fetching filing content: {str(e)}")
            return None

    def extract_financial_data(self, filing_content: str, filing_type: str = "10-K") -> Dict:
        """
        Extract key financial metrics from filing content

        Args:
            filing_content: Raw filing HTML/XML content
            filing_type: Type of filing

        Returns:
            Dictionary of extracted metrics
        """
        metrics = {
            'revenue': None,
            'net_income': None,
            'total_assets': None,
            'total_liabilities': None,
            'cash_and_equivalents': None,
            'operating_cash_flow': None,
            'eps_diluted': None,
            'gross_margin': None,
            'operating_margin': None,
            'debt_to_equity': None,
            'current_ratio': None,
            'roe': None,
            'revenue_growth_mentioned': None,
            'guidance_mentioned': None,
            'risk_factors_count': 0
        }

        try:
            # Clean HTML/XML tags for text analysis
            text = re.sub('<[^<]+?>', ' ', filing_content)
            text = re.sub(r'\s+', ' ', text)

            # Extract financial values using regex patterns
            # Note: These patterns are simplified - production would need more robust parsing

            # Revenue patterns
            revenue_patterns = [
                r'(?:total\s+)?(?:net\s+)?revenues?\s*(?:were|of|was)?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)',
                r'(?:total\s+)?(?:net\s+)?sales\s*(?:were|of|was)?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)',
            ]

            for pattern in revenue_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).replace(',', '')
                    multiplier = 1e9 if 'billion' in match.group(0).lower() else 1e6
                    metrics['revenue'] = float(value) * multiplier
                    break

            # Net income patterns
            income_patterns = [
                r'net\s+(?:income|earnings)\s*(?:was|were|of)?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)',
                r'net\s+(?:loss|losses)\s*(?:was|were|of)?\s*\$?\s*\(([\d,]+(?:\.\d+)?)\)\s*(?:million|billion)',
            ]

            for pattern in income_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).replace(',', '')
                    multiplier = 1e9 if 'billion' in match.group(0).lower() else 1e6
                    sign = -1 if 'loss' in match.group(0).lower() else 1
                    metrics['net_income'] = sign * float(value) * multiplier
                    break

            # Extract other metrics similarly...

            # Count risk factors
            risk_matches = re.findall(r'risk\s+factor', text, re.IGNORECASE)
            metrics['risk_factors_count'] = len(risk_matches)

            # Check for revenue growth mentions
            growth_patterns = [
                r'revenue\s+(?:grew|increased|rose)\s+(?:by\s+)?([\d.]+)%',
                r'([\d.]+)%\s+(?:revenue\s+)?growth',
                r'year-over-year\s+(?:revenue\s+)?growth\s+of\s+([\d.]+)%'
            ]

            for pattern in growth_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    metrics['revenue_growth_mentioned'] = float(match.group(1))
                    break

            # Check for guidance mentions
            guidance_keywords = ['guidance', 'outlook', 'expect', 'forecast', 'anticipate']
            for keyword in guidance_keywords:
                if keyword in text.lower():
                    metrics['guidance_mentioned'] = True
                    break

        except Exception as e:
            print(f"Error extracting financial data: {str(e)}")

        return metrics

    def extract_md_analysis(self, filing_content: str) -> Dict:
        """
        Extract insights from Management Discussion & Analysis section

        Args:
            filing_content: Raw filing content

        Returns:
            Dictionary with MD&A insights
        """
        insights = {
            'sentiment': 'neutral',
            'growth_mentions': 0,
            'challenge_mentions': 0,
            'opportunity_mentions': 0,
            'key_initiatives': [],
            'market_conditions': '',
            'competitive_position': '',
            'future_outlook': ''
        }

        try:
            # Find MD&A section
            mda_pattern = r'(?:management.?s?\s+discussion\s+and\s+analysis|md&a)(.*?)(?:item\s+\d|financial\s+statements)'
            mda_match = re.search(mda_pattern, filing_content, re.IGNORECASE | re.DOTALL)

            if mda_match:
                mda_text = mda_match.group(1)
                mda_text = re.sub('<[^<]+?>', ' ', mda_text)
                mda_text = re.sub(r'\s+', ' ', mda_text)[:10000]  # Limit to first 10k chars

                # Count sentiment indicators
                positive_words = ['growth', 'increase', 'improve', 'strong', 'exceed', 'success', 'opportunity', 'positive']
                negative_words = ['decline', 'decrease', 'challenge', 'difficult', 'weakness', 'concern', 'risk', 'negative']

                positive_count = sum(1 for word in positive_words if word in mda_text.lower())
                negative_count = sum(1 for word in negative_words if word in mda_text.lower())

                insights['growth_mentions'] = mda_text.lower().count('growth')
                insights['challenge_mentions'] = mda_text.lower().count('challenge')
                insights['opportunity_mentions'] = mda_text.lower().count('opportunit')

                # Determine sentiment
                if positive_count > negative_count * 1.5:
                    insights['sentiment'] = 'positive'
                elif negative_count > positive_count * 1.5:
                    insights['sentiment'] = 'negative'
                else:
                    insights['sentiment'] = 'neutral'

                # Extract key phrases for initiatives
                initiative_patterns = [
                    r'(?:key\s+initiatives?|strategic\s+priorities?|focus\s+areas?)\s*(?:include|are|:|\.)\s*([^.]+)',
                    r'we\s+(?:are\s+focusing|plan\s+to|will|intend\s+to)\s+([^.]+)'
                ]

                for pattern in initiative_patterns:
                    matches = re.findall(pattern, mda_text, re.IGNORECASE)
                    insights['key_initiatives'].extend([m[:200] for m in matches[:3]])  # Limit to 3 initiatives

        except Exception as e:
            print(f"Error extracting MD&A: {str(e)}")

        return insights

    def get_comprehensive_analysis(self, ticker: str) -> Dict:
        """
        Get comprehensive EDGAR analysis for a ticker

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with all EDGAR insights
        """
        analysis = {
            'ticker': ticker,
            'latest_10k': {},
            'latest_10q': {},
            'recent_8k_events': [],
            'filing_history': {},
            'financial_trends': {},
            'management_insights': {},
            'risk_profile': {},
            'data_quality': 'low'
        }

        try:
            # Get latest 10-K
            annual_filings = self.get_company_filings(ticker, "10-K", 1)
            if annual_filings:
                latest_10k = annual_filings[0]
                content = self.fetch_filing_content(latest_10k)
                if content:
                    analysis['latest_10k'] = {
                        'filing_date': latest_10k['filing_date'],
                        'metrics': self.extract_financial_data(content, "10-K"),
                        'mda_insights': self.extract_md_analysis(content)
                    }
                    analysis['data_quality'] = 'medium'

            # Get latest 10-Q
            quarterly_filings = self.get_company_filings(ticker, "10-Q", 1)
            if quarterly_filings:
                latest_10q = quarterly_filings[0]
                content = self.fetch_filing_content(latest_10q)
                if content:
                    analysis['latest_10q'] = {
                        'filing_date': latest_10q['filing_date'],
                        'metrics': self.extract_financial_data(content, "10-Q")
                    }
                    analysis['data_quality'] = 'high' if analysis['latest_10k'] else 'medium'

            # Get recent 8-K events
            event_filings = self.get_company_filings(ticker, "8-K", 3)
            for filing in event_filings:
                analysis['recent_8k_events'].append({
                    'filing_date': filing['filing_date'],
                    'accession_number': filing['accession_number']
                })

            # Calculate trends if we have data
            if analysis['latest_10k'] and analysis['latest_10q']:
                analysis['financial_trends'] = self._calculate_trends(
                    analysis['latest_10k']['metrics'],
                    analysis['latest_10q']['metrics']
                )

        except Exception as e:
            print(f"Error in comprehensive analysis for {ticker}: {str(e)}")

        return analysis

    def _calculate_trends(self, annual_metrics: Dict, quarterly_metrics: Dict) -> Dict:
        """
        Calculate financial trends from annual and quarterly data

        Args:
            annual_metrics: Metrics from 10-K
            quarterly_metrics: Metrics from 10-Q

        Returns:
            Dictionary of calculated trends
        """
        trends = {
            'revenue_trajectory': 'unknown',
            'profitability_trend': 'unknown',
            'cash_flow_health': 'unknown'
        }

        try:
            # Analyze revenue trajectory
            if annual_metrics.get('revenue') and quarterly_metrics.get('revenue'):
                quarterly_annualized = quarterly_metrics['revenue'] * 4
                if quarterly_annualized > annual_metrics['revenue'] * 1.1:
                    trends['revenue_trajectory'] = 'accelerating'
                elif quarterly_annualized > annual_metrics['revenue']:
                    trends['revenue_trajectory'] = 'growing'
                elif quarterly_annualized > annual_metrics['revenue'] * 0.95:
                    trends['revenue_trajectory'] = 'stable'
                else:
                    trends['revenue_trajectory'] = 'declining'

            # Analyze profitability
            if annual_metrics.get('net_income') is not None and quarterly_metrics.get('net_income') is not None:
                if quarterly_metrics['net_income'] > 0 and annual_metrics['net_income'] > 0:
                    trends['profitability_trend'] = 'profitable'
                elif quarterly_metrics['net_income'] > annual_metrics.get('net_income', 0) / 4:
                    trends['profitability_trend'] = 'improving'
                else:
                    trends['profitability_trend'] = 'deteriorating'

        except Exception as e:
            print(f"Error calculating trends: {str(e)}")

        return trends


class EDGARScreeningEnhancer:
    """Enhances stock screening with EDGAR data"""

    def __init__(self, edgar_fetcher: Optional[EDGARDataFetcher] = None):
        """
        Initialize the enhancer

        Args:
            edgar_fetcher: Optional EDGARDataFetcher instance
        """
        self.fetcher = edgar_fetcher or EDGARDataFetcher()

    def enhance_screening_data(self, screening_df: pd.DataFrame, include_filings: List[str] = ['10-K', '10-Q']) -> pd.DataFrame:
        """
        Enhance screening results with EDGAR data

        Args:
            screening_df: DataFrame with screening results
            include_filings: Types of filings to include

        Returns:
            Enhanced DataFrame
        """
        enhanced_df = screening_df.copy()

        # Add new columns for EDGAR data
        edgar_columns = [
            'edgar_revenue', 'edgar_net_income', 'edgar_revenue_growth',
            'mda_sentiment', 'growth_mentions', 'risk_factors',
            'latest_10k_date', 'latest_10q_date', 'edgar_data_quality'
        ]

        for col in edgar_columns:
            enhanced_df[col] = None

        # Process each ticker
        for idx, row in enhanced_df.iterrows():
            ticker = row['ticker']
            print(f"Fetching EDGAR data for {ticker}...")

            try:
                analysis = self.fetcher.get_comprehensive_analysis(ticker)

                # Update row with EDGAR data
                if analysis['latest_10k']:
                    enhanced_df.at[idx, 'latest_10k_date'] = analysis['latest_10k'].get('filing_date')
                    metrics = analysis['latest_10k'].get('metrics', {})
                    enhanced_df.at[idx, 'edgar_revenue'] = metrics.get('revenue')
                    enhanced_df.at[idx, 'edgar_net_income'] = metrics.get('net_income')
                    enhanced_df.at[idx, 'edgar_revenue_growth'] = metrics.get('revenue_growth_mentioned')
                    enhanced_df.at[idx, 'risk_factors'] = metrics.get('risk_factors_count', 0)

                    mda = analysis['latest_10k'].get('mda_insights', {})
                    enhanced_df.at[idx, 'mda_sentiment'] = mda.get('sentiment')
                    enhanced_df.at[idx, 'growth_mentions'] = mda.get('growth_mentions', 0)

                if analysis['latest_10q']:
                    enhanced_df.at[idx, 'latest_10q_date'] = analysis['latest_10q'].get('filing_date')

                enhanced_df.at[idx, 'edgar_data_quality'] = analysis.get('data_quality', 'low')

            except Exception as e:
                print(f"Error processing {ticker}: {str(e)}")
                continue

        # Calculate EDGAR score
        enhanced_df = self._calculate_edgar_score(enhanced_df)

        return enhanced_df

    def _calculate_edgar_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate EDGAR-based quality score

        Args:
            df: DataFrame with EDGAR data

        Returns:
            DataFrame with EDGAR score
        """
        df['edgar_score'] = 0

        # Convert EDGAR numeric columns to ensure they're numeric
        numeric_edgar_columns = ['growth_mentions', 'risk_factors', 'edgar_revenue',
                                'edgar_net_income', 'edgar_revenue_growth']
        for col in numeric_edgar_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Sentiment score (0-20 points)
        df.loc[df['mda_sentiment'] == 'positive', 'edgar_score'] += 20
        df.loc[df['mda_sentiment'] == 'neutral', 'edgar_score'] += 10

        # Growth mentions score (0-20 points)
        mask_growth = pd.notna(df['growth_mentions'])
        df.loc[mask_growth & (df['growth_mentions'] > 10), 'edgar_score'] += 20
        df.loc[mask_growth & (df['growth_mentions'] > 5) & (df['growth_mentions'] <= 10), 'edgar_score'] += 15
        df.loc[mask_growth & (df['growth_mentions'] > 0) & (df['growth_mentions'] <= 5), 'edgar_score'] += 10

        # Risk factor score (0-20 points, inverse)
        mask_risk = pd.notna(df['risk_factors'])
        df.loc[mask_risk & (df['risk_factors'] < 20), 'edgar_score'] += 20
        df.loc[mask_risk & (df['risk_factors'] >= 20) & (df['risk_factors'] < 40), 'edgar_score'] += 10
        df.loc[mask_risk & (df['risk_factors'] >= 40) & (df['risk_factors'] < 60), 'edgar_score'] += 5

        # Data recency score (0-20 points)
        current_date = pd.Timestamp.now()

        # Handle date columns carefully
        if 'latest_10k_date' in df.columns and 'latest_10q_date' in df.columns:
            # Convert to datetime, handling None/NaN values
            df['latest_10k_date'] = pd.to_datetime(df['latest_10k_date'], errors='coerce')
            df['latest_10q_date'] = pd.to_datetime(df['latest_10q_date'], errors='coerce')

            # Get the latest date from either column
            df['latest_filing_date'] = df[['latest_10k_date', 'latest_10q_date']].max(axis=1)

            # Calculate days since filing for non-null dates
            mask_dates = pd.notna(df['latest_filing_date'])
            df.loc[mask_dates, 'days_since_filing'] = (current_date - df.loc[mask_dates, 'latest_filing_date']).dt.days

            # Apply scoring only where we have valid dates
            mask_valid = mask_dates & pd.notna(df['days_since_filing'])
            df.loc[mask_valid & (df['days_since_filing'] < 30), 'edgar_score'] += 20
            df.loc[mask_valid & (df['days_since_filing'] >= 30) & (df['days_since_filing'] < 90), 'edgar_score'] += 15
            df.loc[mask_valid & (df['days_since_filing'] >= 90) & (df['days_since_filing'] < 180), 'edgar_score'] += 10

        # Data quality bonus (0-20 points)
        df.loc[df['edgar_data_quality'] == 'high', 'edgar_score'] += 20
        df.loc[df['edgar_data_quality'] == 'medium', 'edgar_score'] += 10

        return df


if __name__ == "__main__":
    # Test EDGAR fetcher
    print("Testing EDGAR Data Fetcher...")
    print("-" * 50)

    fetcher = EDGARDataFetcher()

    # Test with a sample ticker
    test_ticker = "AAPL"
    print(f"\nFetching EDGAR data for {test_ticker}...")

    # Get recent filings
    filings = fetcher.get_company_filings(test_ticker, "10-K", 2)
    if filings:
        print(f"Found {len(filings)} 10-K filings")
        for filing in filings:
            print(f"  - {filing['form']} filed on {filing['filing_date']}")

    # Get comprehensive analysis
    print(f"\nPerforming comprehensive analysis for {test_ticker}...")
    analysis = fetcher.get_comprehensive_analysis(test_ticker)

    if analysis['latest_10k']:
        print(f"Latest 10-K: {analysis['latest_10k'].get('filing_date')}")
        metrics = analysis['latest_10k'].get('metrics', {})
        if metrics.get('revenue'):
            print(f"  Revenue: ${metrics['revenue']:,.0f}")
        if metrics.get('net_income'):
            print(f"  Net Income: ${metrics['net_income']:,.0f}")

        mda = analysis['latest_10k'].get('mda_insights', {})
        if mda:
            print(f"  MD&A Sentiment: {mda.get('sentiment')}")
            print(f"  Growth Mentions: {mda.get('growth_mentions')}")

    print(f"\nData Quality: {analysis.get('data_quality')}")