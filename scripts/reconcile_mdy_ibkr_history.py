"""Compare captured broker observations to pinned publications for governance only."""
import gzip
import json
import math
from datetime import datetime
from statistics import median

from acquire_mdy_ibkr_history import OUT, ROOT, read, save, sha, verified_prior
from qualify_p421_quarter import CUTOFF, window_days
from systematic_trading.research.governed_inputs import GovernedInputs
from pathlib import Path


def indexed_bars(rows, days):
    selected = {}
    for row in rows:
        day = datetime.strptime(row['date'], '%Y%m%d').date().isoformat()
        if day < days[0] or day > days[-1]:
            continue
        if day in selected:
            raise ValueError('Duplicate broker session: ' + day)
        prices = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
        volume = float(row['volume'])
        if any(not math.isfinite(v) or v <= 0 for v in prices + [volume]):
            raise ValueError('Unsupported broker observation: ' + day)
        o, h, low, c = prices
        if low > min(o, c) or h < max(o, c) or h < low:
            raise ValueError('Invalid broker OHLC: ' + day)
        selected[day] = row
    if set(selected) != set(days):
        raise ValueError('Broker session coverage mismatch')
    return selected


def compare(raw, adjusted, published, days):
    trades, adj = indexed_bars(raw, days), indexed_bars(adjusted, days)
    pub = {r['trade_date']: r for r in published}
    if len(pub) != len(published) or set(pub) != set(days):
        raise ValueError('Published session coverage mismatch')
    details, returns, ratios = [], [], []
    for i, day in enumerate(days):
        p, t, a = pub[day], trades[day], adj[day]
        if any(p[k] is None or not math.isfinite(p[k]) or p[k] <= 0 for k in
               ('raw_open', 'raw_high', 'raw_low', 'raw_close', 'raw_volume', 'adjusted_close')):
            raise ValueError('Unsupported governed observation: ' + day)
        delta = {k: float(t[k])-p['raw_'+k] for k in ('open', 'high', 'low', 'close')}
        ratio = float(t['volume']) / p['raw_volume']
        ratios.append(ratio)
        point = dict(date=day, price_difference_usd=delta, published_close=p['raw_close'],
                     broker_trade_close=float(t['close']), published_volume=p['raw_volume'],
                     broker_volume_as_returned=float(t['volume']), volume_ratio=ratio,
                     close_ratio=float(t['close'])/p['raw_close'],
                     adjusted_close_ratio=float(a['close'])/p['adjusted_close'],
                     trade_adjusted_volume_equal=t['volume']==a['volume'])
        if i:
            prev = days[i-1]
            error = 10000 * (math.log(float(a['close'])/float(adj[prev]['close']))
                             - math.log(p['adjusted_close']/pub[prev]['adjusted_close']))
            point['adjusted_log_return_difference_bp'] = error
            returns.append(abs(error))
        details.append(point)
    return dict(sessions=len(days),
                close_within_half_cent=sum(abs(r['price_difference_usd']['close']) <= .005 for r in details),
                max_abs_price_difference_usd={k:max(abs(r['price_difference_usd'][k]) for r in details)
                                              for k in ('open', 'high', 'low', 'close')},
                max_adjusted_return_difference_bp=max(returns),
                median_adjusted_return_difference_bp=median(returns),
                volume_ratio_min=min(ratios), volume_ratio_median=median(ratios), volume_ratio_max=max(ratios),
                volume_exact_matches=sum(r['broker_volume_as_returned']==r['published_volume'] for r in details),
                identical_volume_between_broker_types=all(r['trade_adjusted_volume_equal'] for r in details),
                raw_close_ratio_range=[min(r['close_ratio'] for r in details),max(r['close_ratio'] for r in details)],
                adjusted_close_ratio_range=[min(r['adjusted_close_ratio'] for r in details),max(r['adjusted_close_ratio'] for r in details)],
                details=details)


def load_source(symbol, kind, *, all_hours=False):
    receipt_path = OUT / 'receipts' / (symbol+'-'+kind+('-ALL' if all_hours else '')+'.json')
    receipt = read(receipt_path)
    path = Path(receipt['source_path'])
    if sha(path) != receipt['source_sha256'] or receipt['status'] != 'complete':
        raise ValueError('Changed or incomplete broker source')
    source = json.loads(gzip.decompress(path.read_bytes()))
    if (source['symbol'] != symbol or source['request']['whatToShow'] != kind
            or source['end_callback'] is None or source['request']['useRTH'] != (0 if all_hours else 1)):
        raise ValueError('Broker source metadata mismatch')
    expected = next(r for r in verified_prior('historical-data-request.json')['identities'] if r['symbol']==symbol)
    if source['conId'] != expected['broker_conid']:
        raise ValueError('Broker contract mismatch')
    return source['rows'], sha(receipt_path)


def session_controls(days, governed):
    results=[]
    for symbol in read(OUT / 'session-control-protocol.json')['symbols']:
        regular, h1=load_source(symbol,'TRADES')
        extended, h2=load_source(symbol,'TRADES',all_hours=True)
        regular,extended=indexed_bars(regular,days),indexed_bars(extended,days)
        pub={r['trade_date']:r for r in governed.rows(symbol,days[0],days[-1])}
        ratios=[float(extended[d]['volume'])/pub[d]['raw_volume'] for d in days]
        results.append(dict(symbol=symbol,sessions=len(days),receipt_hashes=dict(regular=h1,all_hours=h2),
            volume_equal=sum(regular[d]['volume']==extended[d]['volume'] for d in days),
            all_hours_volume_ratio_median=median(ratios),all_hours_volume_ratio_min=min(ratios),
            all_hours_volume_ratio_max=max(ratios),
            all_hours_volume_exact=sum(float(extended[d]['volume'])==pub[d]['raw_volume'] for d in days),
            all_hours_close_max_difference=max(abs(float(extended[d]['close'])-pub[d]['raw_close']) for d in days)))
    save(OUT / 'session-control.json',results)


def run():
    protocol = read(OUT / 'protocol.json')
    pins = read(ROOT / 'research/p421-coverage-20261104-v1/pins.json')['price']
    governed = GovernedInputs(Path(pins['root']), pins['batch'])
    days = window_days(CUTOFF)
    if [days[0],days[-1]] != protocol['window']:
        raise ValueError('Frozen window mismatch')
    results, receipt_hashes = [], {}
    for symbol in protocol['symbols']:
        trades, receipt_hashes[symbol+'-TRADES'] = load_source(symbol, 'TRADES')
        adjusted, receipt_hashes[symbol+'-ADJUSTED_LAST'] = load_source(symbol, 'ADJUSTED_LAST')
        result = compare(trades, adjusted, governed.rows(symbol, *protocol['window']), days)
        details = result.pop('details')
        save(OUT / 'differences' / (symbol+'.json'), details)
        result.update(symbol=symbol, published_status=governed.audit(symbol)['status'],
                      qualified_for_publication=False,
                      unresolved=['Volume units/filtering and raw-activity comparability',
                                  'Dated security/corporate-action continuity', 'Earlier source-review disposition'])
        results.append(result)
        print(symbol, json.dumps(result), flush=True)
    session_controls(days,governed)
    save(OUT / 'assessment.json', dict(protocol_sha256=sha(OUT / 'protocol.json'), batch=governed.batch,
         used=governed.used, receipt_hashes=receipt_hashes, results=results,
         completed_series=len(results)*2, stock_sessions=len(results)*len(days),
         new_publications=0, qualified_count=0, runner_sha256=sha(Path(__file__)),
         session_control_sha256=sha(OUT / 'session-control.json'),
         limitation='Broker source was captured in November 2026. Source agreement cannot establish historical publication availability. No global source review was cleared.'))


if __name__ == '__main__':
    run()
