# High-Growth Stock Screener

A powerful web-based stock screening application for identifying high-growth US-listed companies using real-time data from Yahoo Finance.

## Features

### Core Screening Capabilities
- **Revenue Growth Analysis**: Screen stocks by year-over-year (YoY) and quarter-over-quarter (QoQ) revenue growth
- **Forward Estimates**: Analyze forward revenue estimates and implied earnings growth
- **Market Cap Filtering**: Filter by market capitalization from micro-cap to mega-cap
- **Sector Analysis**: Include/exclude specific sectors and view sector breakdowns
- **Valuation Metrics**: Screen by P/E ratio, PEG ratio, and other valuation metrics
- **Analyst Sentiment**: Filter by analyst coverage and buy/hold/sell ratings

### User Interface
- **Interactive Web UI**: Built with Streamlit for a responsive, user-friendly experience
- **Sortable Tables**: Sort results by any column for easy analysis
- **Real-time Updates**: Fetch live data from Yahoo Finance
- **Export Functionality**: Download results as CSV for further analysis
- **Performance Scoring**: Composite scoring system to rank stocks

### Data Coverage
- **800+ Liquid US Stocks**: Curated universe including S&P 500, NASDAQ 100, and high-growth watchlist
- **Multiple Universes**: Choose from different stock universes or screen all at once
- **Comprehensive Metrics**: Over 30 data points per stock including financials, estimates, and technical indicators

## Tech Stack

- **Python 3.8+**: Core programming language
- **Streamlit**: Web application framework
- **yfinance**: Yahoo Finance data API
- **pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Internet connection for fetching real-time data

### Setup Instructions

1. **Clone or download this repository**
   ```bash
   git clone <repository-url>
   cd stock_screener
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install required packages**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   streamlit run app.py
   ```

5. **Open your browser**
   - The application will automatically open in your default browser
   - If not, navigate to: `http://localhost:8501`

## Usage Guide

### Quick Start

1. **Launch the application** using `streamlit run app.py`
2. **Select your screening criteria** in the left sidebar:
   - Choose stock universe (S&P 500, NASDAQ 100, or Full Universe)
   - Set minimum revenue growth percentage
   - Configure market cap requirements
   - Select sectors to exclude
3. **Click "Run Screener"** to start the screening process
4. **Analyze results** in the sortable table
5. **Export to CSV** for further analysis

### Screening Parameters

#### Growth Metrics
- **Min Revenue Growth YoY (%)**: Minimum year-over-year revenue growth
- **Require positive forward estimates**: Filter for stocks with positive forward revenue estimates

#### Market Cap Filters
- All Caps: No minimum
- Micro Cap: >$50M
- Small Cap: >$300M
- Mid Cap: >$2B
- Large Cap: >$10B
- Mega Cap: >$100B

#### Valuation Filters
- **Max P/E Ratio**: Maximum price-to-earnings ratio
- **Profitable companies only**: Filter for positive earnings

#### Sector Filters
- Exclude specific sectors (default: Utilities, Real Estate)
- Available sectors: Technology, Healthcare, Financials, Consumer Discretionary, Communication Services, Industrials, Consumer Staples, Energy, Materials

#### Analyst Coverage
- **Require analyst coverage**: Only show stocks with analyst ratings
- **Min Buy Rating (%)**: Minimum percentage of buy recommendations

### Understanding the Results

#### Key Metrics Displayed
- **Ticker & Company**: Stock symbol and company name
- **Sector**: Industry classification
- **Market Cap**: Current market capitalization
- **Price**: Current stock price
- **Rev Growth YoY %**: Year-over-year revenue growth percentage
- **Fwd P/E**: Forward price-to-earnings ratio
- **Buy %**: Percentage of analysts with buy ratings
- **Target**: Mean analyst price target
- **Score**: Composite growth score (0-100)

#### Composite Score Calculation
The composite score (0-100 points) consists of:
- **Revenue Growth Score** (0-40 points): Based on YoY revenue growth
- **Forward Growth Score** (0-20 points): Based on forward estimates
- **Valuation Score** (0-20 points): Based on P/E and PEG ratios
- **Analyst Score** (0-20 points): Based on analyst sentiment
- **Momentum Score** (0-20 points): Based on 52-week price range

## Project Structure

```
stock_screener/
├── app.py                 # Main Streamlit application
├── data_fetcher.py        # yfinance data retrieval module
├── screener.py            # Screening logic and scoring
├── ticker_universe.py     # Curated lists of stock tickers
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore file
└── README.md             # This file
```

### Module Descriptions

- **app.py**: Streamlit web interface with user controls and result visualization
- **data_fetcher.py**: Handles all Yahoo Finance API calls with caching and error handling
- **screener.py**: Implements screening logic, filtering, and composite scoring
- **ticker_universe.py**: Maintains curated lists of liquid US stocks

## Performance Considerations

- **API Rate Limiting**: The application includes built-in delays to respect Yahoo Finance rate limits
- **Caching**: Results are cached for 1 hour to improve performance
- **Batch Processing**: Data is fetched in batches for efficiency
- **Progress Tracking**: Real-time progress updates during screening

### Estimated Processing Times
- S&P 500 (~500 stocks): 2-5 minutes
- NASDAQ 100 Additional (~40 stocks): 30-60 seconds
- Full Universe (~800 stocks): 5-10 minutes

## Troubleshooting

### Common Issues and Solutions

1. **"No module named 'streamlit'" error**
   - Solution: Install requirements with `pip install -r requirements.txt`

2. **Application won't start**
   - Check Python version: `python --version` (must be 3.8+)
   - Ensure virtual environment is activated
   - Try: `python -m streamlit run app.py`

3. **Slow data fetching**
   - This is normal due to API rate limiting
   - Use smaller universes for faster results
   - Enable caching in Advanced Options

4. **No stocks found**
   - Adjust screening criteria (lower revenue growth threshold)
   - Expand market cap range
   - Remove sector exclusions

5. **Data appears outdated**
   - Check "Force refresh data" in Advanced Options
   - Yahoo Finance data may have delays during market hours

## Limitations

- **Data Source**: Relies on Yahoo Finance which may have occasional outages
- **Rate Limiting**: API calls are throttled to prevent blocking
- **Historical Data**: Limited to data available through yfinance
- **Real-time Updates**: Data may be delayed 15-20 minutes during market hours

## Future Enhancements

Potential improvements for future versions:
- Additional data sources (Alpha Vantage, IEX Cloud)
- Technical indicators and chart integration
- Backtesting capabilities
- Email alerts for screening criteria
- Saved screening templates
- Portfolio tracking integration
- Machine learning-based predictions

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Disclaimer

**Important**: This tool is for informational and educational purposes only. It should not be considered as financial advice. Always do your own research and consult with a qualified financial advisor before making investment decisions.

The accuracy of the data depends on Yahoo Finance and may contain errors or delays. Past performance does not guarantee future results.

## License

This project is provided as-is for educational purposes. Feel free to modify and distribute according to your needs.

## Support

For issues, questions, or suggestions, please open an issue in the repository or contact the maintainer.

---

**Happy Screening!** 📈

*Built with Python, Streamlit, and yfinance*