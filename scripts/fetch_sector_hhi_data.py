"""Freeze raw Yahoo responses and normalized sector-ETF observations, outside trading stores."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, date, timedelta
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day

SECTORS = {'XLB':'Materials', 'XLC':'Communication services', 'XLE':'Energy', 'XLF':'Financials',
           'XLI':'Industrials', 'XLK':'Technology', 'XLP':'Consumer staples', 'XLRE':'Real estate',
           'XLU':'Utilities', 'XLV':'Health care', 'XLY':'Consumer discretionary'}


def fetch(symbol, root, start, end):
    query = urlencode(dict(period1=int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp()),
        period2=int((datetime.fromisoformat(end)+timedelta(days=1)).replace(tzinfo=UTC).timestamp()),
        interval='1d', events='div,splits'))
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}'
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0 systematic-trading-research/0.1'}), timeout=30) as response:
                raw = response.read()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)
    (root/'raw'/f'{symbol}.json').write_bytes(raw)
    result = json.loads(raw)['chart']['result'][0]
    quote = result['indicators']['quote'][0]
    adjusted = result['indicators']['adjclose'][0]['adjclose']
    rows, excluded = [], []
    for i, timestamp in enumerate(result['timestamp']):
        day = datetime.fromtimestamp(timestamp, UTC).date()
        values = [quote['close'][i], adjusted[i], quote['volume'][i]]
        if not start <= str(day) <= end:
            continue
        if not is_us_trading_day(day) or any(v is None or v <= 0 for v in values):
            excluded.append(dict(date=str(day), close=values[0], adj_close=values[1], volume=values[2]))
            continue
        rows.append(dict(date=str(day), close=values[0], adj_close=values[1], volume=values[2]))
    return symbol, rows, dict(url=url, retrieved_at=datetime.now(UTC).isoformat(),
        excluded=excluded, first=str(rows[0]['date']), last=str(rows[-1]['date']), observations=len(rows),
        splits=result.get('events', {}).get('splits', {}), dividends=result.get('events', {}).get('dividends', {}),
        currency=result['meta'].get('currency'), exchange_timezone=result['meta'].get('exchangeTimezoneName'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    root.mkdir(parents=True, exist_ok=False)
    (root/'raw').mkdir()
    protocol = dict(start='2019-01-02', fetch_start='2018-06-19', end='2026-09-24', sectors=SECTORS,
        horizons_sessions=[20,60,120], primary_hhi='sum((reported sector ETF volume / total sector ETF volume)**2)',
        sensitivity_hhi='sum((provider close * volume / sum(provider close * volume))**2)',
        raw_derivatives='lag 1, backward finite differences', smoothed_derivatives='EMA span 10, backward differences lag 10',
        forward_returns='adjusted_close[t+h]/adjusted_close[t]-1, USD, close-to-close, descriptive not executable fills',
        basket='equal initial weights across 11 ETFs, held for each horizon; average of ETF forward returns',
        common_scatter_sample='dates >= 2019-01-02 with all 120-session labels observed; identical sample across nine panels',
        main_target='SPY', supporting_targets=['equal_weight_sectors', *SECTORS],
        inference='overlapping labels; 240-session paired circular blocks, 1000 replicates; descriptive CIs without multiple-test correction',
        warning='ETF trading-volume proxies, not aggregate underlying-sector turnover or net flows. Historical data vintages and split-volume conventions are uncertified.')
    write_json(root/'protocol.json', protocol)
    data, provenance = {}, {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, rows, source in pool.map(lambda s: fetch(s,root,protocol['fetch_start'],protocol['end']), [*SECTORS,'SPY']):
            data[symbol], provenance[symbol] = rows, source
            print(symbol,len(rows),rows[0]['date'],rows[-1]['date'],flush=True)
    expected = []
    first,last = date.fromisoformat(protocol['fetch_start']),date.fromisoformat(protocol['end'])
    for i in range((last-first).days+1):
        d = first+timedelta(days=i)
        if is_us_trading_day(d): expected.append(str(d))
    for symbol, rows in data.items():
        if [r['date'] for r in rows] != expected:
            missing = sorted(set(expected)-{r['date'] for r in rows})
            raise ValueError(f'{symbol}: missing/duplicate/unordered sessions: {missing[:20]}')
    write_json(root/'data.json',data)
    write_json(root/'provenance.json',provenance)
    write_json(root/'manifest.json', {p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()})


if __name__ == '__main__':
    main()
