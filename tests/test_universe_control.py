from datetime import date, timedelta
from decimal import Decimal
import math

from systematic_trading.domain.market import PriceBar
from systematic_trading.research.etf_universe import MULTI_ASSET_ETF_UNIVERSE, RESEARCH_SECTOR_ETFS
from systematic_trading.research import universe_control as study


def data():
    days=[str(date(2020,1,1)+timedelta(days=i)) for i in range(100)]
    typed={}
    for j,symbol in enumerate([*MULTI_ASSET_ETF_UNIVERSE,*RESEARCH_SECTOR_ETFS]):
        typed[symbol]=[]
        for i,day in enumerate(days):
            close=Decimal(str(100+i*.1+math.sin(i*.7)*(j+1)))
            typed[symbol].append(PriceBar(trade_date=day,open=close,high=close,low=close,close=close,volume=100+i))
    return dict(days=days,typed=typed,bars={s:None for s in typed},receipt=dict(original_symbols=sorted(MULTI_ASSET_ETF_UNIVERSE)))


def test_universe_decisions_ignore_current_future_prices_and_all_volumes(monkeypatch):
    inputs=data();monkeypatch.setattr(study,"_DATA",inputs)
    day=inputs["days"][80];before=study.decision(day)
    for symbol,rows in inputs["typed"].items():
        inputs["typed"][symbol]=[r.model_copy(update=dict(volume=99999999, **(
            dict(open=r.open*2,high=r.high*2,low=r.low*2,close=r.close*2) if i>=80 else {}))) for i,r in enumerate(rows)]
    assert study.decision(day)==before
    assert before[1]["RP14"]["known_through"]==inputs["days"][79]


def test_added_sector_prices_do_not_change_original_control_or_active_universe(monkeypatch):
    inputs=data();monkeypatch.setattr(study,"_DATA",inputs)
    day=inputs["days"][80];before=study.decision(day)[1]
    inputs["typed"]["XLE"]=[r.model_copy(update=dict(close=r.close+Decimal(i%7)*5)) for i,r in enumerate(inputs["typed"]["XLE"])]
    after=study.decision(day)[1]
    assert after["RP12"]==before["RP12"]
    assert after["RP14"]!=before["RP14"]
    assert not set(RESEARCH_SECTOR_ETFS)&set(MULTI_ASSET_ETF_UNIVERSE)
    assert len(after["RP12"]["targets"])==12 and len(after["RP14"]["targets"])==14
