"""
Ticker Universe Module
Provides a curated list of liquid US-listed stocks for screening
"""

def get_additional_sp500():
    """Additional S&P 500 companies to complete the index"""
    return [
        # More S&P 500 companies not in original list
        'A', 'AAL', 'AAP', 'AAPL', 'ABBV', 'ABC', 'ABMD', 'ABT', 'ACN', 'ADBE',
        'ADI', 'ADM', 'ADP', 'ADS', 'ADSK', 'AEE', 'AEP', 'AES', 'AFL', 'AIG',
        'AIV', 'AIZ', 'AJG', 'AKAM', 'ALB', 'ALGN', 'ALK', 'ALL', 'ALLE', 'ALXN',
        'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN', 'AMP', 'AMT', 'AMZN', 'ANET', 'ANSS',
        'ANTM', 'AON', 'AOS', 'APA', 'APD', 'APH', 'APTV', 'ARE', 'ATO', 'ATVI',
        'AVB', 'AVGO', 'AVY', 'AWK', 'AXP', 'AXS', 'AZO', 'BA', 'BAC', 'BALL',
        'BAX', 'BBWI', 'BBY', 'BDX', 'BEN', 'BF.B', 'BIIB', 'BIO', 'BK', 'BKNG',
        'BKR', 'BLK', 'BLL', 'BMY', 'BR', 'BRK.B', 'BRO', 'BSX', 'BWA', 'BXP',
        'C', 'CAG', 'CAH', 'CARR', 'CAT', 'CB', 'CBOE', 'CBRE', 'CCI', 'CCL',
        'CDAY', 'CDNS', 'CDW', 'CE', 'CERN', 'CF', 'CFG', 'CHD', 'CHRW', 'CHTR',
        'CI', 'CINF', 'CL', 'CLX', 'CMA', 'CMCSA', 'CME', 'CMG', 'CMI', 'CMS',
        'CNC', 'CNP', 'COF', 'COG', 'COLM', 'COOP', 'COP', 'COST', 'COTY', 'CPB',
        'CPRT', 'CRL', 'CRM', 'CSCO', 'CSX', 'CTAS', 'CTL', 'CTSH', 'CTVA', 'CTXS',
        'CVS', 'CVX', 'CZR', 'D', 'DAL', 'DDD', 'DE', 'DELL', 'DFS', 'DG',
        'DGX', 'DHI', 'DHR', 'DIS', 'DISCK', 'DISH', 'DLR', 'DLTR', 'DLTR', 'DOV',
        'DOW', 'DPZ', 'DRE', 'DRI', 'DTE', 'DUK', 'DVA', 'DVN', 'DXC', 'DXCM',
        'EA', 'EBAY', 'ECL', 'ED', 'EFX', 'EIX', 'EL', 'EMN', 'EMR', 'ENPH',
        'EOG', 'EQIX', 'EQR', 'ES', 'ESS', 'ETFC', 'ETN', 'ETR', 'ETSY', 'EVRG',
        'EW', 'EXC', 'EXPD', 'EXPE', 'EXR', 'F', 'FANG', 'FAST', 'FB', 'FBHS',
        'FCX', 'FDX', 'FE', 'FFIV', 'FIS', 'FISV', 'FITB', 'FLIR', 'FLT', 'FMC',
        'FOX', 'FOXA', 'FRC', 'FRT', 'FTI', 'FTNT', 'FTV', 'GD', 'GE', 'GILD',
        'GIS', 'GL', 'GLW', 'GM', 'GNRC', 'GOOG', 'GOOGL', 'GPC', 'GPN', 'GPS',
        'GRMN', 'GS', 'GWW', 'HAL', 'HAS', 'HBAN', 'HBI', 'HCA', 'HD', 'HES',
        'HFC', 'HIG', 'HII', 'HLT', 'HOLX', 'HON', 'HPE', 'HPQ', 'HRL', 'HSIC',
        'HST', 'HSY', 'HUM', 'HWM', 'IBM', 'ICE', 'IDXX', 'IEX', 'IFF', 'ILMN',
        'INCY', 'INFO', 'INTC', 'INTU', 'IP', 'IPG', 'IPGP', 'IQV', 'IR', 'IRM',
        'ISRG', 'IT', 'ITW', 'IVZ', 'J', 'JBHT', 'JCI', 'JKHY', 'JNJ', 'JNPR',
        'JPM', 'K', 'KEY', 'KEYS', 'KHC', 'KIM', 'KLAC', 'KMB', 'KMI', 'KMX',
        'KO', 'KR', 'KSS', 'KSU', 'L', 'LB', 'LDOS', 'LEG', 'LEN', 'LH',
        'LHX', 'LIN', 'LKQ', 'LLY', 'LMT', 'LNC', 'LNT', 'LOW', 'LRCX', 'LUV',
        'LVS', 'LW', 'LYB', 'LYV', 'MA', 'MAA', 'MAR', 'MAS', 'MCD', 'MCHP',
        'MCK', 'MCO', 'MDLZ', 'MDT', 'MET', 'META', 'MGM', 'MHK', 'MKC', 'MKTX',
        'MLM', 'MMC', 'MMM', 'MNST', 'MO', 'MOH', 'MOS', 'MPC', 'MPWR', 'MRK',
        'MRO', 'MS', 'MSCI', 'MSFT', 'MSI', 'MTB', 'MTD', 'MU', 'MXIM', 'MYL',
        'NBL', 'NCLH', 'NDAQ', 'NEE', 'NEM', 'NFLX', 'NI', 'NKE', 'NLOK', 'NLSN',
        'NOC', 'NOV', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS', 'NUE', 'NVDA', 'NVR',
        'NWL', 'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OGN', 'OKE', 'OMC', 'ORCL',
        'ORLY', 'OTIS', 'OXY', 'PAYC', 'PAYX', 'PBCT', 'PCAR', 'PEAK', 'PEG', 'PENN',
        'PEP', 'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM', 'PKG', 'PKI', 'PLD',
        'PM', 'PNC', 'PNR', 'PNW', 'POOL', 'PPG', 'PPL', 'PRGO', 'PRU', 'PSA',
        'PSX', 'PTC', 'PVH', 'PWR', 'PXD', 'PYPL', 'QCOM', 'QRVO', 'RCL', 'RE',
        'REG', 'REGN', 'RF', 'RHI', 'RJF', 'RL', 'RMD', 'ROK', 'ROL', 'ROP',
        'ROST', 'RSG', 'RTN', 'RTX', 'SBAC', 'SBUX', 'SCHW', 'SEE', 'SHW', 'SIVB',
        'SJM', 'SLB', 'SLG', 'SNA', 'SNPS', 'SO', 'SPG', 'SPGI', 'SRE', 'STE',
        'STT', 'STX', 'STZ', 'SWK', 'SWKS', 'SYF', 'SYK', 'SYY', 'T', 'TAP',
        'TDG', 'TDY', 'TECH', 'TEL', 'TER', 'TFC', 'TFX', 'TGT', 'TIF', 'TJX',
        'TMO', 'TMUS', 'TPR', 'TRGP', 'TRIP', 'TRMB', 'TROW', 'TRV', 'TSCO', 'TSLA',
        'TSN', 'TT', 'TTWO', 'TWTR', 'TXN', 'TXT', 'TYL', 'UA', 'UAA', 'UAL',
        'UDR', 'UHS', 'ULTA', 'UNH', 'UNM', 'UNP', 'UPS', 'URI', 'USB', 'V',
        'VAR', 'VFC', 'VIAC', 'VLO', 'VMC', 'VNO', 'VRSK', 'VRSN', 'VRTX', 'VTR',
        'VTRS', 'VZ', 'WAB', 'WAT', 'WBA', 'WDC', 'WEC', 'WELL', 'WFC', 'WHR',
        'WLTW', 'WM', 'WMB', 'WMT', 'WRB', 'WRK', 'WST', 'WU', 'WY', 'WYNN',
        'XEL', 'XLNX', 'XOM', 'XRAY', 'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZION', 'ZTS'
    ]

def get_sp500_tickers():
    """
    Returns S&P 500 tickers as a base universe of liquid stocks
    This list is current as of 2024 but should be periodically updated
    """
    original = [
        # Technology
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'AVGO', 'ORCL', 'ADBE',
        'CRM', 'CSCO', 'ACN', 'NOW', 'INTC', 'AMD', 'INTU', 'IBM', 'QCOM', 'TXN',
        'AMAT', 'PANW', 'MU', 'ANET', 'LRCX', 'KLAC', 'SNPS', 'CDNS', 'CRWD', 'ADSK',
        'ADI', 'MRVL', 'NXPI', 'FTNT', 'MCHP', 'ON', 'FSLR', 'KEYS', 'MPWR', 'ENPH',

        # Healthcare & Pharmaceuticals
        'LLY', 'UNH', 'JNJ', 'ABBV', 'MRK', 'TMO', 'ABT', 'PFE', 'AMGN', 'CVS',
        'DHR', 'BMY', 'GILD', 'MDT', 'ISRG', 'REGN', 'VRTX', 'SYK', 'BSX', 'ZTS',
        'MRNA', 'HUM', 'CI', 'BIIB', 'ILMN', 'IDXX', 'DXCM', 'A', 'IQV', 'MTD',
        'HCA', 'MCK', 'CAH', 'CNC', 'MOH', 'DGX', 'LH', 'TECH', 'HOLX', 'CRL',

        # Financial Services
        'BRK.B', 'JPM', 'V', 'MA', 'BAC', 'WFC', 'GS', 'MS', 'SCHW', 'AXP',
        'SPGI', 'BLK', 'C', 'CB', 'PGR', 'MMC', 'AON', 'TFC', 'PNC', 'USB',
        'CME', 'ICE', 'MCO', 'AIG', 'MET', 'PRU', 'MSCI', 'TRV', 'ALL', 'AJG',
        'WTW', 'FITB', 'STT', 'TROW', 'NTRS', 'CBOE', 'NDAQ', 'CINF', 'WRB', 'L',

        # Consumer Discretionary
        'AMZN', 'HD', 'MCD', 'NKE', 'LOW', 'SBUX', 'TJX', 'BKNG', 'CMG', 'ORLY',
        'AZO', 'ROST', 'MAR', 'GM', 'F', 'HLT', 'YUM', 'DRI', 'LVS', 'MGM',
        'DECK', 'LULU', 'ULTA', 'DPZ', 'EXPE', 'EBAY', 'ETSY', 'POOL', 'BBY', 'TSCO',
        'DG', 'DLTR', 'TGT', 'COST', 'WMT', 'KMX', 'APTV', 'BWA', 'LKQ', 'AAP',

        # Consumer Staples
        'PG', 'KO', 'PEP', 'COST', 'PM', 'MO', 'MDLZ', 'CL', 'KMB', 'GIS',
        'ADM', 'K', 'KHC', 'MNST', 'STZ', 'KDP', 'HSY', 'CPB', 'CAG', 'SJM',
        'TAP', 'BF.B', 'EL', 'CHD', 'CLX', 'TSN', 'HRL', 'MKC', 'SYY', 'LW',

        # Energy
        'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'MPC', 'PSX', 'VLO', 'OXY', 'HES',
        'DVN', 'HAL', 'BKR', 'FANG', 'APA', 'MRO', 'TRGP', 'OKE', 'KMI', 'WMB',

        # Industrials
        'CAT', 'UNP', 'HON', 'UPS', 'BA', 'RTX', 'DE', 'LMT', 'GE', 'MMM',
        'WM', 'EMR', 'ETN', 'ITW', 'CSX', 'NSC', 'FDX', 'NOC', 'GD', 'TT',
        'CARR', 'OTIS', 'JCI', 'CTAS', 'FAST', 'PAYX', 'VRSK', 'CPRT', 'ODFL', 'JBHT',

        # Communication Services
        'DIS', 'NFLX', 'CMCSA', 'VZ', 'T', 'TMUS', 'CHTR', 'PARA', 'WBD', 'EA',
        'TTWO', 'ATVI', 'MTCH', 'SNAP', 'PINS', 'ROKU', 'SPOT', 'RBLX', 'DASH', 'UBER',

        # Real Estate
        'PLD', 'AMT', 'CCI', 'EQIX', 'PSA', 'O', 'WELL', 'DLR', 'SBAC', 'VICI',
        'WY', 'SPG', 'AVB', 'EQR', 'INVH', 'MAA', 'ARE', 'VTR', 'PEAK', 'ESS',

        # Materials
        'LIN', 'SHW', 'FCX', 'NEM', 'CTVA', 'DOW', 'DD', 'NUE', 'VMC', 'MLM',
        'APD', 'ECL', 'PPG', 'BALL', 'AMCR', 'AVY', 'PKG', 'IP', 'ALB', 'CE',

        # Utilities
        'NEE', 'SO', 'DUK', 'AEP', 'EXC', 'SRE', 'XEL', 'ED', 'WEC', 'ES',
        'D', 'PEG', 'PCG', 'EIX', 'FE', 'PPL', 'AEE', 'CMS', 'CNP', 'DTE'
    ]

    return original

def get_nasdaq100_additional():
    """
    Additional NASDAQ-100 tickers not in S&P 500
    """
    return [
        'TEAM', 'DDOG', 'NET', 'ZM', 'DOCU', 'OKTA', 'ZS', 'VEEV', 'WDAY', 'SPLK',
        'PDD', 'JD', 'BIDU', 'NTES', 'BABA', 'TCOM', 'MELI', 'SE', 'GRAB', 'NU',
        'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'SQ', 'PYPL', 'ABNB', 'LYFT', 'PATH',
        'SHOP', 'TTD', 'APPS', 'U', 'RBLX', 'TWLO', 'DBX', 'BOX', 'DOCN', 'GTLB'
    ]

def get_high_growth_watchlist():
    """
    Additional high-growth stocks to monitor
    """
    return [
        # AI & Cloud
        'AI', 'PLTR', 'SNOW', 'MDB', 'ESTC', 'CFLT', 'S', 'GTLB', 'IOT', 'BILL',

        # Biotech & Healthcare Tech
        'TDOC', 'DOCS', 'HIMS', 'ACCD', 'CERT', 'RXRX', 'BEAM', 'CRSP', 'EDIT', 'NTLA',

        # Fintech
        'TOST', 'FLYW', 'PAYO', 'FOUR', 'RELY', 'MKTX', 'RYAN', 'HUBS', 'PCOR', 'AVDX',

        # E-commerce & Digital
        'CPNG', 'WISH', 'FTCH', 'W', 'CVNA', 'OSTK', 'PRCH', 'BIGC', 'VTEX', 'BMBL',

        # EV & Clean Energy
        'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'FSR', 'CHPT', 'BLNK', 'EVGO', 'RUN',

        # Gaming & Entertainment
        'DKNG', 'PENN', 'RSI', 'GENI', 'FUBO', 'SONO', 'GPRO', 'VZIO', 'BGFV', 'ZNGA',

        # Enterprise Software
        'MNDY', 'ASAN', 'SMAR', 'BRZE', 'CWAN', 'SUMO', 'FROG', 'API', 'NEWR', 'RPD'
    ]

def get_sector_etfs():
    """
    Sector ETFs for comparison and sector filtering
    """
    return {
        'XLK': 'Technology',
        'XLV': 'Healthcare',
        'XLF': 'Financials',
        'XLY': 'Consumer Discretionary',
        'XLP': 'Consumer Staples',
        'XLE': 'Energy',
        'XLI': 'Industrials',
        'XLC': 'Communication Services',
        'XLRE': 'Real Estate',
        'XLB': 'Materials',
        'XLU': 'Utilities'
    }

def get_full_universe():
    """
    Get the complete universe of tickers to screen
    Returns approximately 800-900 liquid US stocks
    """
    # Try to use the comprehensive ticker list first
    try:
        from comprehensive_tickers import get_all_tickers
        return get_all_tickers()
    except ImportError:
        # Fallback to the original method if comprehensive_tickers is not available
        # Combine all ticker lists and remove duplicates
        all_tickers = list(set(
            get_sp500_tickers() +
            get_nasdaq100_additional() +
            get_high_growth_watchlist()
        ))

        # Sort alphabetically for consistency
        all_tickers.sort()

        return all_tickers

def get_ticker_sectors():
    """
    Returns a dictionary mapping tickers to their sectors
    This is a simplified mapping - in production, this would come from a data provider
    """
    sector_map = {
        # Technology
        'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology',
        'GOOGL': 'Communication Services', 'META': 'Communication Services',
        'TSLA': 'Consumer Discretionary', 'AVGO': 'Technology', 'ORCL': 'Technology',
        'ADBE': 'Technology', 'CRM': 'Technology', 'CSCO': 'Technology',
        'INTC': 'Technology', 'AMD': 'Technology', 'QCOM': 'Technology',

        # Healthcare
        'LLY': 'Healthcare', 'UNH': 'Healthcare', 'JNJ': 'Healthcare',
        'ABBV': 'Healthcare', 'MRK': 'Healthcare', 'PFE': 'Healthcare',

        # Financials
        'JPM': 'Financials', 'V': 'Financials', 'MA': 'Financials',
        'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials',

        # Consumer
        'AMZN': 'Consumer Discretionary', 'HD': 'Consumer Discretionary',
        'MCD': 'Consumer Discretionary', 'NKE': 'Consumer Discretionary',
        'PG': 'Consumer Staples', 'KO': 'Consumer Staples', 'PEP': 'Consumer Staples',

        # Energy
        'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy',

        # Add more mappings as needed
    }

    return sector_map

if __name__ == "__main__":
    # Test the module
    universe = get_full_universe()
    print(f"Total tickers in universe: {len(universe)}")
    print(f"First 10 tickers: {universe[:10]}")
    print(f"Sector ETFs: {get_sector_etfs()}")