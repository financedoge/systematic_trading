from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument


@dataclass(frozen=True)
class AllWeatherETFSpec:
    symbol: str
    name: str
    asset_class_group: str
    region_group: str
    sleeve: str
    all_weather_bucket: str
    segment: str

    @property
    def instrument(self) -> Instrument:
        return Instrument(
            symbol=self.symbol,
            name=self.name,
            asset_class=AssetClass.ETF,
            exchange=Exchange.NYSE,
            quote_currency=Currency.USD,
            country=self.region_group,
            sector=self.asset_class_group,
        )


ALL_WEATHER_ETF_SPECS: tuple[AllWeatherETFSpec, ...] = (
    AllWeatherETFSpec("SPY", "SPDR S&P 500 ETF Trust", "equity", "US", "equity_us", "growth", "US large cap"),
    AllWeatherETFSpec("MDY", "SPDR S&P MidCap 400 ETF Trust", "equity", "US", "equity_us", "growth", "US mid cap"),
    AllWeatherETFSpec("IWM", "iShares Russell 2000 ETF", "equity", "US", "equity_us", "growth", "US small cap"),
    AllWeatherETFSpec("VGK", "Vanguard FTSE Europe ETF", "equity", "Europe", "equity_europe", "growth", "Europe broad"),
    AllWeatherETFSpec("FEZ", "SPDR EURO STOXX 50 ETF", "equity", "Europe", "equity_europe", "growth", "Eurozone large cap"),
    AllWeatherETFSpec("DFE", "WisdomTree Europe SmallCap Dividend Fund", "equity", "Europe", "equity_europe", "growth", "Europe small cap"),
    AllWeatherETFSpec("MCHI", "iShares MSCI China ETF", "equity", "China", "equity_china", "growth", "China broad"),
    AllWeatherETFSpec("FXI", "iShares China Large-Cap ETF", "equity", "China", "equity_china", "growth", "China large cap"),
    AllWeatherETFSpec("ECNS", "iShares MSCI China Small-Cap ETF", "equity", "China", "equity_china", "growth", "China small cap"),
    AllWeatherETFSpec("EWJ", "iShares MSCI Japan ETF", "equity", "Asia ex-China", "equity_asia_ex_china", "growth", "Japan"),
    AllWeatherETFSpec("EWY", "iShares MSCI South Korea ETF", "equity", "Asia ex-China", "equity_asia_ex_china", "growth", "South Korea"),
    AllWeatherETFSpec("EWT", "iShares MSCI Taiwan ETF", "equity", "Asia ex-China", "equity_asia_ex_china", "growth", "Taiwan"),
    AllWeatherETFSpec("EPI", "WisdomTree India Earnings Fund", "equity", "Asia ex-China", "equity_asia_ex_china", "growth", "India"),
    AllWeatherETFSpec("SHY", "iShares 1-3 Year Treasury Bond ETF", "rates", "US", "rates_us_short_intermediate", "deflation", "US short rates"),
    AllWeatherETFSpec("IEF", "iShares 7-10 Year Treasury Bond ETF", "rates", "US", "rates_us_short_intermediate", "deflation", "US intermediate rates"),
    AllWeatherETFSpec("TLT", "iShares 20+ Year Treasury Bond ETF", "rates", "US", "rates_us_long", "deflation", "US long rates"),
    AllWeatherETFSpec("TIP", "iShares TIPS Bond ETF", "rates", "US", "rates_inflation_linked", "inflation", "US TIPS"),
    AllWeatherETFSpec("BWZ", "SPDR Bloomberg Short Term International Treasury Bond ETF", "rates", "Global ex-US", "rates_ex_us", "deflation", "Ex-US short rates"),
    AllWeatherETFSpec("BWX", "SPDR Bloomberg International Treasury Bond ETF", "rates", "Global ex-US", "rates_ex_us", "deflation", "Ex-US broad rates"),
    AllWeatherETFSpec("IGOV", "iShares International Treasury Bond ETF", "rates", "Global ex-US", "rates_ex_us", "deflation", "Developed ex-US rates"),
    AllWeatherETFSpec("CBON", "VanEck China Bond ETF", "rates", "China", "rates_china", "deflation", "China onshore bonds"),
    AllWeatherETFSpec("LQD", "iShares iBoxx $ Investment Grade Corporate Bond ETF", "credit", "US", "credit_us", "income", "US investment grade"),
    AllWeatherETFSpec("HYG", "iShares iBoxx $ High Yield Corporate Bond ETF", "credit", "US", "credit_us", "income", "US high yield"),
    AllWeatherETFSpec("IBND", "SPDR Bloomberg International Corporate Bond ETF", "credit", "Global ex-US", "credit_ex_us", "income", "Ex-US corporate credit"),
    AllWeatherETFSpec("HYXU", "iShares International High Yield Bond ETF", "credit", "Global ex-US", "credit_ex_us", "income", "Ex-US high yield"),
    AllWeatherETFSpec("USO", "United States Oil Fund", "commodity", "Energy", "commodity_energy", "inflation", "Crude oil"),
    AllWeatherETFSpec("UNG", "United States Natural Gas Fund", "commodity", "Energy", "commodity_energy", "inflation", "Natural gas"),
    AllWeatherETFSpec("DBB", "Invesco DB Base Metals Fund", "commodity", "Base metals", "commodity_base_metals", "inflation", "Base metals basket"),
    AllWeatherETFSpec("CPER", "United States Copper Index Fund", "commodity", "Base metals", "commodity_base_metals", "inflation", "Copper"),
    AllWeatherETFSpec("GLD", "SPDR Gold Shares", "commodity", "Precious metals", "commodity_precious_metals", "inflation", "Gold"),
    AllWeatherETFSpec("SLV", "iShares Silver Trust", "commodity", "Precious metals", "commodity_precious_metals", "inflation", "Silver"),
    AllWeatherETFSpec("PPLT", "abrdn Physical Platinum Shares ETF", "commodity", "Precious metals", "commodity_precious_metals", "inflation", "Platinum"),
    AllWeatherETFSpec("DBA", "Invesco DB Agriculture Fund", "commodity", "Agriculture", "commodity_agriculture", "inflation", "Agriculture basket"),
    AllWeatherETFSpec("CORN", "Teucrium Corn Fund", "commodity", "Agriculture", "commodity_agriculture", "inflation", "Corn"),
    AllWeatherETFSpec("WEAT", "Teucrium Wheat Fund", "commodity", "Agriculture", "commodity_agriculture", "inflation", "Wheat"),
)


ALL_WEATHER_ETF_UNIVERSE = {spec.symbol: spec.instrument for spec in ALL_WEATHER_ETF_SPECS}
ALL_WEATHER_SPEC_BY_SYMBOL = {spec.symbol: spec for spec in ALL_WEATHER_ETF_SPECS}


def grouped_counts(specs: Iterable[AllWeatherETFSpec] = ALL_WEATHER_ETF_SPECS) -> dict[str, dict[str, int]]:
    result = {
        "assetClass": {},
        "region": {},
        "sleeve": {},
        "allWeatherBucket": {},
    }
    for spec in specs:
        _increment(result["assetClass"], spec.asset_class_group)
        _increment(result["region"], spec.region_group)
        _increment(result["sleeve"], spec.sleeve)
        _increment(result["allWeatherBucket"], spec.all_weather_bucket)
    return result


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1
