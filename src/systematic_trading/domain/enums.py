from enum import StrEnum


class Currency(StrEnum):
    CNH = "CNH"
    USD = "USD"
    EUR = "EUR"
    HKD = "HKD"
    JPY = "JPY"
    KRW = "KRW"


class AssetClass(StrEnum):
    STOCK = "stock"
    ETF = "etf"


class Exchange(StrEnum):
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    LSE = "LSE"
    XETRA = "XETRA"
    EURONEXT = "EURONEXT"
    HKEX = "HKEX"
    TSE = "TSE"
    KRX = "KRX"
    OTHER = "OTHER"


class SignalAction(StrEnum):
    BUY = "buy"
    ADD = "add"
    HOLD = "hold"
    TRIM = "trim"
    EXIT = "exit"
    REBALANCE = "rebalance"


class ThesisStatus(StrEnum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    INVALIDATED = "invalidated"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    TWAP = "twap"
    VWAP = "vwap"
    MARKET_ON_OPEN = "market_on_open"
    LIMIT_ON_OPEN = "limit_on_open"


class OrderEnvironment(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class BrokerOrderStatus(StrEnum):
    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
