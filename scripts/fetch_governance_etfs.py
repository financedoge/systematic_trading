"""Freeze all existing Market Bars ETF histories and collect missing source ledgers."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fetch_governance_history import fetch,write,inventory
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore,digest
from systematic_trading.market_data.golden import _sql_string


def main():
    root=Path('D:/systematic_trading_data/research/governance-etfs-20260926-v1')
    if (root/'manifest.json').exists():
        return
    for sub in ('raw','metadata','golden'):
        (root/sub).mkdir(parents=True,exist_ok=True)
    store=AnalyticsStore.from_settings(AppSettings())
    symbols=[r['symbol'] for r in store.query('SELECT DISTINCT symbol FROM market_data.daily_bars FINAL ORDER BY symbol')]
    write(root/'universe.json',{s:dict(symbol=s,holdings_names=[],roles=['ETF','existing Market Bars']) for s in symbols})
    existing=inventory()
    missing=[s for s in symbols if s not in existing]
    with ThreadPoolExecutor(max_workers=4) as pool:
        print('Supplemental downloads',list(pool.map(lambda s:fetch(root,s),missing)),flush=True)
    for symbol in symbols:
        rows=store.query('SELECT * FROM market_data.daily_bars FINAL WHERE symbol='+_sql_string(symbol)+' ORDER BY trade_date')
        write(root/'golden'/(symbol+'.json'),rows)
    write(root/'manifest.json',{p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()})
    print('Frozen ETF supplement',len(symbols),len(missing),flush=True)


if __name__=='__main__':
    main()
