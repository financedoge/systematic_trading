from __future__ import annotations

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument


SPY_REPLACEMENT_SYMBOL = "SPY"


def _us_stock(symbol: str, name: str, exchange: Exchange, sector: str) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=name,
        asset_class=AssetClass.STOCK,
        exchange=exchange,
        quote_currency=Currency.USD,
        country="US",
        sector=sector,
    )


US_STOCK_REPLACEMENT_UNIVERSE: dict[str, Instrument] = {
    "AAPL": _us_stock("AAPL", "Apple Inc.", Exchange.NASDAQ, "Information Technology"),
    "MSFT": _us_stock("MSFT", "Microsoft Corporation", Exchange.NASDAQ, "Information Technology"),
    "GOOGL": _us_stock("GOOGL", "Alphabet Inc. Class A", Exchange.NASDAQ, "Communication Services"),
    "AMZN": _us_stock("AMZN", "Amazon.com, Inc.", Exchange.NASDAQ, "Consumer Discretionary"),
    "META": _us_stock("META", "Meta Platforms, Inc.", Exchange.NASDAQ, "Communication Services"),
    "NVDA": _us_stock("NVDA", "NVIDIA Corporation", Exchange.NASDAQ, "Information Technology"),
    "AVGO": _us_stock("AVGO", "Broadcom Inc.", Exchange.NASDAQ, "Information Technology"),
    "AMD": _us_stock("AMD", "Advanced Micro Devices, Inc.", Exchange.NASDAQ, "Information Technology"),
    "MU": _us_stock("MU", "Micron Technology, Inc.", Exchange.NASDAQ, "Information Technology"),
    "ORCL": _us_stock("ORCL", "Oracle Corporation", Exchange.NYSE, "Information Technology"),
    "INTC": _us_stock("INTC", "Intel Corporation", Exchange.NASDAQ, "Information Technology"),
    "CSCO": _us_stock("CSCO", "Cisco Systems, Inc.", Exchange.NASDAQ, "Information Technology"),
    "CRM": _us_stock("CRM", "Salesforce, Inc.", Exchange.NYSE, "Information Technology"),
    "JPM": _us_stock("JPM", "JPMorgan Chase & Co.", Exchange.NYSE, "Financials"),
    "BAC": _us_stock("BAC", "Bank of America Corporation", Exchange.NYSE, "Financials"),
    "C": _us_stock("C", "Citigroup Inc.", Exchange.NYSE, "Financials"),
    "WFC": _us_stock("WFC", "Wells Fargo & Company", Exchange.NYSE, "Financials"),
    "GS": _us_stock("GS", "The Goldman Sachs Group, Inc.", Exchange.NYSE, "Financials"),
    "MS": _us_stock("MS", "Morgan Stanley", Exchange.NYSE, "Financials"),
    "XOM": _us_stock("XOM", "Exxon Mobil Corporation", Exchange.NYSE, "Energy"),
    "CVX": _us_stock("CVX", "Chevron Corporation", Exchange.NYSE, "Energy"),
    "COP": _us_stock("COP", "ConocoPhillips", Exchange.NYSE, "Energy"),
    "SLB": _us_stock("SLB", "SLB", Exchange.NYSE, "Energy"),
    "BA": _us_stock("BA", "The Boeing Company", Exchange.NYSE, "Industrials"),
    "RTX": _us_stock("RTX", "RTX Corporation", Exchange.NYSE, "Industrials"),
    "LMT": _us_stock("LMT", "Lockheed Martin Corporation", Exchange.NYSE, "Industrials"),
    "NOC": _us_stock("NOC", "Northrop Grumman Corporation", Exchange.NYSE, "Industrials"),
    "GE": _us_stock("GE", "GE Aerospace", Exchange.NYSE, "Industrials"),
    "CAT": _us_stock("CAT", "Caterpillar Inc.", Exchange.NYSE, "Industrials"),
    "DE": _us_stock("DE", "Deere & Company", Exchange.NYSE, "Industrials"),
    "UNH": _us_stock("UNH", "UnitedHealth Group Incorporated", Exchange.NYSE, "Health Care"),
    "MRK": _us_stock("MRK", "Merck & Co., Inc.", Exchange.NYSE, "Health Care"),
    "PFE": _us_stock("PFE", "Pfizer Inc.", Exchange.NYSE, "Health Care"),
    "ABBV": _us_stock("ABBV", "AbbVie Inc.", Exchange.NYSE, "Health Care"),
    "CVS": _us_stock("CVS", "CVS Health Corporation", Exchange.NYSE, "Health Care"),
    "HUM": _us_stock("HUM", "Humana Inc.", Exchange.NYSE, "Health Care"),
    "DIS": _us_stock("DIS", "The Walt Disney Company", Exchange.NYSE, "Communication Services"),
    "NKE": _us_stock("NKE", "NIKE, Inc.", Exchange.NYSE, "Consumer Discretionary"),
    "SBUX": _us_stock("SBUX", "Starbucks Corporation", Exchange.NASDAQ, "Consumer Discretionary"),
    "TGT": _us_stock("TGT", "Target Corporation", Exchange.NYSE, "Consumer Staples"),
    "HD": _us_stock("HD", "The Home Depot, Inc.", Exchange.NYSE, "Consumer Discretionary"),
    "LOW": _us_stock("LOW", "Lowe's Companies, Inc.", Exchange.NYSE, "Consumer Discretionary"),
    "GM": _us_stock("GM", "General Motors Company", Exchange.NYSE, "Consumer Discretionary"),
    "F": _us_stock("F", "Ford Motor Company", Exchange.NYSE, "Consumer Discretionary"),
    "TSLA": _us_stock("TSLA", "Tesla, Inc.", Exchange.NASDAQ, "Consumer Discretionary"),
}


def default_us_stock_symbols() -> list[str]:
    return sorted(US_STOCK_REPLACEMENT_UNIVERSE)
