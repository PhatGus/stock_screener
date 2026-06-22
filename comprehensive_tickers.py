#!/usr/bin/env python3
"""
Comprehensive list of US stock tickers including S&P 500, NASDAQ-100,
Russell 1000, and other major stocks
"""

def get_sp500_tickers():
    """Complete S&P 500 list as of 2024"""
    return [
        'A', 'AAPL', 'ABBV', 'ABNB', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI', 'ADM',
        'ADP', 'ADSK', 'AEE', 'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG', 'AKAM',
        'ALB', 'ALGN', 'ALK', 'ALL', 'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN',
        'AMP', 'AMT', 'AMZN', 'ANET', 'ANSS', 'AON', 'AOS', 'APA', 'APD', 'APH',
        'APTV', 'ARE', 'ATO', 'AVB', 'AVGO', 'AVY', 'AWK', 'AXON', 'AXP', 'AZO',
        'BA', 'BAC', 'BALL', 'BAX', 'BBWI', 'BBY', 'BDX', 'BEN', 'BF-B', 'BG',
        'BIIB', 'BIO', 'BK', 'BKNG', 'BKR', 'BLDR', 'BLK', 'BMY', 'BR', 'BRK-B',
        'BRO', 'BSX', 'BWA', 'BX', 'BXP', 'C', 'CAG', 'CAH', 'CARR', 'CAT',
        'CB', 'CBOE', 'CBRE', 'CCI', 'CCL', 'CDAY', 'CDNS', 'CDW', 'CE', 'CEG',
        'CF', 'CFG', 'CHD', 'CHRW', 'CHTR', 'CI', 'CINF', 'CL', 'CLX', 'CMA',
        'CMCSA', 'CME', 'CMG', 'CMI', 'CMS', 'CNC', 'CNP', 'COF', 'COO', 'COP',
        'COR', 'COST', 'CPAY', 'CPB', 'CPRT', 'CPT', 'CRL', 'CRM', 'CSCO', 'CSGP',
        'CSX', 'CTAS', 'CTLT', 'CTRA', 'CTSH', 'CTVA', 'CVS', 'CVX', 'CZR', 'D',
        'DAL', 'DAY', 'DD', 'DE', 'DECK', 'DFS', 'DG', 'DGX', 'DHI', 'DHR',
        'DIS', 'DLR', 'DLTR', 'DOC', 'DOV', 'DOW', 'DPZ', 'DRI', 'DTE', 'DUK',
        'DVA', 'DVN', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED', 'EFX', 'EG', 'EIX',
        'EL', 'ELV', 'EMN', 'EMR', 'ENPH', 'EOG', 'EPAM', 'EQIX', 'EQR', 'EQT',
        'ES', 'ESS', 'ETN', 'ETR', 'ETSY', 'EVRG', 'EW', 'EXC', 'EXPD', 'EXPE',
        'EXR', 'F', 'FANG', 'FAST', 'FCX', 'FDS', 'FDX', 'FE', 'FFIV', 'FI',
        'FICO', 'FIS', 'FITB', 'FLT', 'FMC', 'FOX', 'FOXA', 'FRT', 'FSLR', 'FTNT',
        'FTV', 'GD', 'GDDY', 'GE', 'GEHC', 'GEN', 'GEV', 'GILD', 'GIS', 'GL',
        'GLW', 'GM', 'GNRC', 'GOOG', 'GOOGL', 'GPC', 'GPN', 'GRMN', 'GS', 'GWW',
        'HAL', 'HAS', 'HBAN', 'HCA', 'HD', 'HES', 'HIG', 'HII', 'HLT', 'HOLX',
        'HON', 'HPE', 'HPQ', 'HRL', 'HSIC', 'HST', 'HSY', 'HUBB', 'HUM', 'HWM',
        'IBM', 'ICE', 'IDXX', 'IEX', 'IFF', 'ILMN', 'INCY', 'INTC', 'INTU', 'INVH',
        'IP', 'IPG', 'IQV', 'IR', 'IRM', 'ISRG', 'IT', 'ITW', 'IVZ', 'J',
        'JBHT', 'JBL', 'JCI', 'JKHY', 'JNJ', 'JNPR', 'JPM', 'K', 'KDP', 'KEY',
        'KEYS', 'KHC', 'KIM', 'KLAC', 'KMB', 'KMI', 'KMX', 'KO', 'KR', 'KVUE',
        'L', 'LDOS', 'LEN', 'LH', 'LHX', 'LIN', 'LKQ', 'LLY', 'LMT', 'LNT',
        'LOW', 'LRCX', 'LULU', 'LUV', 'LVS', 'LW', 'LYB', 'LYV', 'MA', 'MAA',
        'MAR', 'MAS', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDLZ', 'MDT', 'MET', 'META',
        'MGM', 'MHK', 'MKC', 'MKTX', 'MLM', 'MMC', 'MMM', 'MNST', 'MO', 'MOH',
        'MOS', 'MPC', 'MPWR', 'MRK', 'MRNA', 'MRO', 'MS', 'MSCI', 'MSFT', 'MSI',
        'MTB', 'MTCH', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN', 'NEE', 'NEM', 'NFLX',
        'NI', 'NKE', 'NOC', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS', 'NUE', 'NVDA',
        'NVR', 'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OGN', 'OKE', 'OMC', 'ON',
        'ORCL', 'ORLY', 'OTIS', 'OXY', 'PANW', 'PARA', 'PAYC', 'PAYX', 'PCAR', 'PCG',
        'PEG', 'PEP', 'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM', 'PKG', 'PLD',
        'PM', 'PNC', 'PNR', 'PNW', 'PODD', 'POOL', 'PPG', 'PPL', 'PRU', 'PSA',
        'PSX', 'PTC', 'PWR', 'PYPL', 'QCOM', 'QRVO', 'RCL', 'REG', 'REGN', 'RF',
        'RHI', 'RJF', 'RL', 'RMD', 'ROK', 'ROL', 'ROP', 'ROST', 'RSG', 'RTX',
        'RVTY', 'SBAC', 'SBUX', 'SCHW', 'SHW', 'SJM', 'SLB', 'SMCI', 'SNA', 'SNPS',
        'SO', 'SOLV', 'SPG', 'SPGI', 'SRE', 'STE', 'STLD', 'STT', 'STX', 'STZ',
        'SWK', 'SWKS', 'SYF', 'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TECH',
        'TEL', 'TER', 'TFC', 'TFX', 'TGT', 'TJX', 'TMO', 'TMUS', 'TPR', 'TRGP',
        'TRMB', 'TROW', 'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTWO', 'TXN', 'TXT',
        'TYL', 'UAL', 'UBER', 'UDR', 'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI',
        'USB', 'V', 'VICI', 'VLO', 'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRTX', 'VST',
        'VTR', 'VTRS', 'VZ', 'WAB', 'WAT', 'WBA', 'WBD', 'WDC', 'WEC', 'WELL',
        'WFC', 'WM', 'WMB', 'WMT', 'WRB', 'WRK', 'WST', 'WTW', 'WY', 'WYNN',
        'XEL', 'XOM', 'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZTS'
    ]

def get_nasdaq100_tickers():
    """NASDAQ-100 tickers"""
    return [
        'AAPL', 'ABNB', 'ADBE', 'ADI', 'ADP', 'ADSK', 'AEP', 'ALGN', 'AMAT', 'AMD',
        'AMGN', 'AMZN', 'ANSS', 'ASML', 'AVGO', 'AZN', 'BIIB', 'BKNG', 'BKR', 'CCEP',
        'CDNS', 'CDW', 'CEG', 'CHTR', 'CMCSA', 'COST', 'CPRT', 'CRWD', 'CSCO', 'CSGP',
        'CSX', 'CTAS', 'CTSH', 'DDOG', 'DLTR', 'DXCM', 'EA', 'EXC', 'FANG', 'FAST',
        'FTNT', 'GEHC', 'GFS', 'GILD', 'GOOG', 'GOOGL', 'HON', 'IDXX', 'ILMN', 'INTC',
        'INTU', 'ISRG', 'KDP', 'KHC', 'KLAC', 'LIN', 'LRCX', 'LULU', 'MAR', 'MCHP',
        'MDLZ', 'MELI', 'META', 'MNST', 'MRNA', 'MRVL', 'MSFT', 'MU', 'NFLX', 'NVDA',
        'NXPI', 'ODFL', 'ON', 'ORLY', 'PANW', 'PAYX', 'PCAR', 'PDD', 'PEP', 'PYPL',
        'QCOM', 'REGN', 'ROP', 'ROST', 'SBUX', 'SMCI', 'SNPS', 'TEAM', 'TMUS', 'TSLA',
        'TTD', 'TTWO', 'TXN', 'VRSK', 'VRTX', 'WBD', 'WDAY', 'XEL', 'ZS'
    ]

def get_russell_1000_additional():
    """Additional Russell 1000 stocks not in S&P 500"""
    return [
        'AAP', 'ACIW', 'ACLS', 'AGNC', 'AGCO', 'AGL', 'AGNC', 'AGIO', 'AJRD', 'AKRO',
        'ALKS', 'ALNY', 'ALSN', 'ALTM', 'AMCX', 'AMED', 'AMKR', 'AMTD', 'ANGO', 'ANIP',
        'APLS', 'APPF', 'APPN', 'ARES', 'ARKO', 'ARMK', 'ARRY', 'ARVN', 'ASB', 'ASGN',
        'ASND', 'ATEN', 'ATKR', 'ATMU', 'ATUS', 'ATVI', 'AUB', 'AVNT', 'AVTR', 'AVYA',
        'AWI', 'AXTA', 'AY', 'AZEK', 'AZPN', 'BABA', 'BAND', 'BANF', 'BANR', 'BCC',
        'BCPC', 'BCRX', 'BEAM', 'BECN', 'BERY', 'BGCP', 'BHLB', 'BHR', 'BILL', 'BKNG',
        'BKU', 'BLKB', 'BLX', 'BMBL', 'BMRN', 'BNED', 'BNTX', 'BOKF', 'BOOT', 'BORG',
        'BPMC', 'BPOP', 'BRC', 'BRKS', 'BRX', 'BSIG', 'BURL', 'BWXT', 'BYND', 'CABO',
        'CACI', 'CAKE', 'CALX', 'CANO', 'CAPR', 'CARA', 'CARG', 'CARS', 'CART', 'CASY',
        'CATO', 'CBRL', 'CBSH', 'CCCS', 'CCMP', 'CCXI', 'CDEV', 'CDK', 'CDNA', 'CDXS',
        'CEIX', 'CELH', 'CENT', 'CENTA', 'CEQP', 'CERN', 'CERT', 'CEVA', 'CG', 'CGBD',
        'CHDN', 'CHEF', 'CHGG', 'CHH', 'CHK', 'CHNG', 'CIEN', 'CIM', 'CION', 'CIVI',
        'CKH', 'CLBK', 'CLDT', 'CLFD', 'CLGX', 'CLLS', 'CLMT', 'CLNE', 'CLNC', 'CLPT',
        'CLSK', 'CLVT', 'CLXT', 'CMAX', 'CMC', 'CMCO', 'CMPR', 'CMPS', 'CMTG', 'CNA',
        'CNHI', 'CNK', 'CNMD', 'CNNE', 'CNO', 'CNOB', 'CNQ', 'CNS', 'CNSL', 'CNTE',
        'CNTY', 'CNX', 'CNXC', 'CNXN', 'COHR', 'COIN', 'COKE', 'COLB', 'COLD', 'COLL',
        'COLM', 'COMM', 'COMP', 'COOP', 'CORE', 'CORN', 'CORT', 'COTY', 'COUP', 'CPE',
        'CPK', 'CPRI', 'CPS', 'CPSI', 'CR', 'CRBG', 'CRC', 'CRDO', 'CRGY', 'CRH',
        'CRI', 'CRK', 'CRMT', 'CROX', 'CRS', 'CRSP', 'CRSR', 'CRUS', 'CRVL', 'CRWD',
        'CRWS', 'CSAN', 'CSL', 'CSOD', 'CSQ', 'CSR', 'CSTM', 'CSV', 'CSWC', 'CSWI',
        'CTB', 'CTBI', 'CTKB', 'CTLP', 'CTOS', 'CTT', 'CTXS', 'CUBE', 'CUE', 'CUEN',
        'CUZ', 'CVBF', 'CVI', 'CVLT', 'CVNA', 'CVR', 'CVRX', 'CVT', 'CVU', 'CW',
        'CWCO', 'CWST', 'CWT', 'CX', 'CXM', 'CXP', 'CXW', 'CYBN', 'CYBR', 'CYCN',
        'CYH', 'CYRX', 'CYTK', 'CZNC', 'CZR', 'DADA', 'DAKT', 'DAN', 'DAVA', 'DAWN',
        'DBVT', 'DBX', 'DCBO', 'DCI', 'DCPH', 'DCT', 'DCOM', 'DDOG', 'DDS', 'DDT',
        'DE', 'DENN', 'DESP', 'DFH', 'DFIN', 'DGII', 'DGLY', 'DHC', 'DHT', 'DHX',
        'DIN', 'DINO', 'DIOD', 'DIS', 'DISH', 'DJT', 'DK', 'DKL', 'DKNG', 'DKS',
        'DLHC', 'DLO', 'DLPH', 'DLX', 'DM', 'DMK', 'DMRC', 'DNLI', 'DNOW', 'DNP'
    ]

def get_popular_growth_stocks():
    """Popular growth and momentum stocks"""
    return [
        'AI', 'AFRM', 'APLD', 'APP', 'ARRY', 'ARVL', 'ASAN', 'AVAV', 'AXON', 'BIRD',
        'BLBD', 'BLND', 'BMBL', 'BNGO', 'BROS', 'BRZE', 'BTI', 'BYND', 'CELH', 'CFLT',
        'CHPT', 'CIFR', 'CLS', 'CLVR', 'CNXA', 'COIN', 'COUR', 'CPNG', 'CRBU', 'CRDO',
        'CRNC', 'CRSR', 'CRWD', 'CVAC', 'CVNA', 'CXT', 'CYN', 'DASH', 'DBX', 'DCBO',
        'DDOG', 'DKNG', 'DKNG', 'DLTR', 'DNA', 'DNMR', 'DOCN', 'DOCS', 'DOCU', 'DOMO',
        'DOOO', 'DOOR', 'DT', 'DUOL', 'DVAX', 'DWAC', 'DXY', 'EDIT', 'EDR', 'ELF',
        'ENOV', 'ENPH', 'ENTG', 'ENV', 'ENVX', 'EOSE', 'EPAM', 'ESMT', 'ESTC', 'ETSY',
        'EVBG', 'EVGO', 'EVLV', 'EVRG', 'EXAS', 'EXLS', 'EXPI', 'EXTR', 'FCEL', 'FDMT',
        'FDS', 'FIGS', 'FINV', 'FISV', 'FIVN', 'FIVE', 'FIXX', 'FLEX', 'FLNC', 'FLNT',
        'FLWS', 'FLY', 'FMTX', 'FND', 'FNKO', 'FOUR', 'FRGE', 'FRHC', 'FRPT', 'FRSH',
        'FSLY', 'FSLR', 'FTCH', 'FTCI', 'FTDR', 'FTRE', 'FUBO', 'FUTU', 'FVRR', 'FWRD',
        'GATO', 'GBCI', 'GBTC', 'GCT', 'GDDY', 'GDS', 'GEN', 'GENI', 'GERN', 'GFL',
        'GFS', 'GGAL', 'GH', 'GIII', 'GKOS', 'GLAD', 'GLBE', 'GLNG', 'GLOB', 'GLPI',
        'GLUE', 'GME', 'GMTX', 'GNRC', 'GNSS', 'GO', 'GOCO', 'GOEV', 'GOGO', 'GOLF',
        'GOOS', 'GPCR', 'GPRE', 'GPRO', 'GRAB', 'GREE', 'GRFS', 'GRMN', 'GRND', 'GROV',
        'GROW', 'GRPN', 'GRUB', 'GRVY', 'GRWG', 'GS', 'GSAT', 'GSHD', 'GTBIF', 'GTEC',
        'GTES', 'GTH', 'GTLB', 'GTN', 'GTX', 'GTYH', 'GURE', 'GVA', 'GWRE', 'GXO',
        'H', 'HAE', 'HAIN', 'HAYW', 'HBAN', 'HBI', 'HCAT', 'HCM', 'HCSG', 'HD',
        'HEAR', 'HEES', 'HEI', 'HELE', 'HFWA', 'HGTY', 'HHC', 'HIFS', 'HIIT', 'HIMS',
        'HIPO', 'HIVE', 'HKIB', 'HL', 'HLIO', 'HLNE', 'HLT', 'HLTH', 'HLVX', 'HMHC',
        'HMNF', 'HMPT', 'HMST', 'HNI', 'HNRG', 'HOFT', 'HOFV', 'HOLI', 'HOLX', 'HOMB',
        'HOOD', 'HOPE', 'HOUS', 'HOWL', 'HPK', 'HQI', 'HQY', 'HR', 'HRB', 'HRC',
        'HRI', 'HRL', 'HRMY', 'HROW', 'HRT', 'HRTX', 'HRZN', 'HSBC', 'HSDT', 'HSIC'
    ]

def get_etf_holdings():
    """Major ETFs for completeness"""
    return [
        'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'IVV', 'VEA', 'VWO', 'AGG',
        'GLD', 'EFA', 'VNQ', 'BND', 'VIG', 'VUG', 'IJH', 'IJR', 'IEMG', 'LQD',
        'VTV', 'VB', 'VO', 'VGT', 'XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLY',
        'XLP', 'XLU', 'XLB', 'XLRE', 'ARKK', 'ARKG', 'ARKW', 'ARKQ', 'ARKF', 'ARKX',
        'ICLN', 'TAN', 'FAN', 'PBW', 'QCLN', 'LIT', 'REMX', 'COPX', 'PICK', 'PAVE',
        'JETS', 'SKYY', 'HACK', 'FINX', 'ROBO', 'BOTZ', 'CLOU', 'WCLD', 'IGPT', 'CIBR'
    ]

def get_all_tickers():
    """Get comprehensive list of all tickers"""
    all_tickers = set()

    # Add all ticker sources
    all_tickers.update(get_sp500_tickers())
    all_tickers.update(get_nasdaq100_tickers())
    all_tickers.update(get_russell_1000_additional())
    all_tickers.update(get_popular_growth_stocks())

    # Don't include ETFs in the screener universe
    # all_tickers.update(get_etf_holdings())

    # Convert to sorted list and clean
    ticker_list = sorted(list(all_tickers))

    # Remove any empty strings
    ticker_list = [t for t in ticker_list if t and t.strip()]

    return ticker_list

if __name__ == "__main__":
    tickers = get_all_tickers()
    print(f"Total unique tickers: {len(tickers)}")
    print(f"Sample: {tickers[:20]}")

    # Save to file
    with open('comprehensive_tickers.txt', 'w') as f:
        for ticker in tickers:
            f.write(f"{ticker}\n")

    print(f"\nSaved {len(tickers)} tickers to comprehensive_tickers.txt")