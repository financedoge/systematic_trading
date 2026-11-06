"""Read-only broker source inspection for the frozen ten-name MDY pilot.

Captured bars are governance evidence, never direct strategy inputs.
"""
import argparse
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / 'research/p421-ten-qualification-20261106-v1'
OUT = ROOT / 'research/p421-ibkr-reconcile-20261106-v1'
SOURCE = ROOT / 'var/research/p421-ibkr-reconcile-20261106-v1'
ADVISORIES = {2104, 2106, 2107, 2108, 2158, 2174, 2176, 2188}


def completed_status(has_end, messages):
    return 'complete' if has_end and all(m['code'] in ADVISORIES for m in messages) else 'review'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_prior(name):
    if sha(PRIOR / name) != read(PRIOR / 'artifact-manifest.json')[name]:
        raise ValueError('Changed pilot evidence: ' + name)
    return read(PRIOR / name)


def acquire(symbols=None, all_hours_control=False):
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    request = verified_prior('historical-data-request.json')
    contracts = verified_prior('ib-contracts.json')['funds']
    if symbols is None:
        symbols = request['symbols']
    if not set(symbols) <= set(request['symbols']):
        raise ValueError('Outside frozen pilot')
    protocol = dict(prior_manifest_sha256=sha(PRIOR / 'artifact-manifest.json'),
                    window=[request['start'], request['end']], symbols=request['symbols'],
                    scope='Independent source reconciliation only; no publication or strategy inputs.',
                    comparisons='Exact session coverage, OHLC differences and ratios, adjacent adjusted returns, volume ratios. No new automatic qualification threshold.',
                    basis={'TRADES': 'Split-adjusted trade prices, not guaranteed historical raw prices.',
                           'ADJUSTED_LAST': 'Dividend/split-adjusted prices at current capture vintage.'},
                    volume='Keep broker units unchanged; verify shares/lots and trade/session scope before treating as raw volume.',
                    documentation=['https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars',
                                   'https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations'])
    if (OUT / 'protocol.json').exists() and read(OUT / 'protocol.json') != protocol:
        raise ValueError('Changed protocol')
    save(OUT / 'protocol.json', protocol)
    if all_hours_control:
        if symbols != ['CSL', 'WSO', 'XPO']:
            raise ValueError('Frozen session control uses CSL, WSO and XPO')
        save(OUT / 'session-control-protocol.json', dict(symbols=symbols, whatToShow='TRADES',
             useRTH=0, window=protocol['window'], purpose='Diagnose session coverage without changing qualification thresholds.'))

    class App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.accounts_seen = Event(), Event()
            self.accounts, self.messages, self.rows, self.events, self.ends = [], [], {}, {}, {}

        def nextValidId(self, orderId):  # noqa: N802
            self.ready.set()

        def managedAccounts(self, accountsList):  # noqa: N802
            self.accounts = [s.strip() for s in accountsList.split(',') if s.strip()]
            self.accounts_seen.set()

        def historicalData(self, reqId, bar):  # noqa: N802
            self.rows[reqId].append({k: str(getattr(bar, k)) for k in
                                    ('date', 'open', 'high', 'low', 'close', 'volume', 'wap', 'barCount')})

        def historicalDataEnd(self, reqId, start, end):  # noqa: N802
            self.ends[reqId] = dict(start=start, end=end)
            self.events[reqId].set()

        @compatible_ib_errors
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):  # noqa: N802
            self.messages.append(dict(request=reqId, code=errorCode, message=errorString))
            if reqId in self.events and errorCode not in ADVISORIES:
                self.events[reqId].set()

        def placeOrder(self, *args, **kwargs):  # noqa: N802
            raise RuntimeError('Read-only evidence client cannot place orders')

    profile = InteractiveBrokersAdapter(AppSettings()).profile_for(OrderEnvironment.PAPER)
    app, thread = App(), None
    session = dict(started_at=datetime.now(UTC).isoformat(), client_id=29383,
                   environment='paper', port=profile.port, order_calls=0, receipts=[])
    session_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
    try:
        app.connect(profile.host, profile.port, session['client_id'])
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        if not app.ready.wait(12):
            raise TimeoutError('Paper gateway handshake timed out')
        app.reqManagedAccts()
        if not app.accounts_seen.wait(12) or not app.accounts or any(not a.startswith('DU') for a in app.accounts):
            raise ValueError('Paper managed account verification failed')
        session.update(paper_accounts_verified=True, server_version=app.serverVersion())
        for symbol in symbols:
            for kind in (('TRADES',) if all_hours_control else ('TRADES', 'ADJUSTED_LAST')):
                label = symbol + '-' + kind + ('-ALL' if all_hours_control else '')
                path = SOURCE / (label + '.json.gz')
                receipt_path = OUT / 'receipts' / (label + '.json')
                if receipt_path.exists():
                    receipt = read(receipt_path)
                    if receipt['status'] == 'complete' and sha(path) == receipt['source_sha256']:
                        print(label, 'verified existing capture', flush=True)
                        continue
                    if sha(path) != receipt['source_sha256']:
                        raise ValueError('Changed capture: ' + label)
                    archived = SOURCE / 'attempts' / (session_id + '-' + path.name)
                    archived.parent.mkdir(parents=True, exist_ok=True)
                    archived.write_bytes(path.read_bytes())
                    save(OUT / 'attempts' / (session_id + '-' + label + '.json'),
                         dict(receipt, source_path=str(archived)))
                req_id = len(app.rows) + 93001
                app.rows[req_id], app.events[req_id] = [], Event()
                contract = Contract()
                for k in ('conId', 'symbol', 'secType', 'currency', 'exchange', 'primaryExchange'):
                    setattr(contract, k, contracts[symbol]['details']['contract'][k])
                spec = dict(endDateTime='20250301 00:00:00 UTC' if kind == 'TRADES' else '',
                            durationStr='2 Y' if kind == 'TRADES' else '3 Y',
                            barSizeSetting='1 day', whatToShow=kind, useRTH=0 if all_hours_control else 1,
                            formatDate=1, keepUpToDate=False)
                started = datetime.now(UTC).isoformat()
                app.reqHistoricalData(req_id, contract, **spec, chartOptions=[])
                done = app.events[req_id].wait(45)
                if not done:
                    app.cancelHistoricalData(req_id)
                messages = [m for m in app.messages if m['request'] == req_id]
                status = completed_status(req_id in app.ends, messages)
                source = dict(symbol=symbol, conId=contract.conId, request=spec, rows=app.rows[req_id],
                              started_at=started, completed_at=datetime.now(UTC).isoformat(),
                              end_callback=app.ends.get(req_id), messages=messages, status=status)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(gzip.compress(json.dumps(source, sort_keys=True).encode(), mtime=0))
                receipt = {k: v for k, v in source.items() if k != 'rows'}
                receipt.update(source_path=str(path), source_sha256=sha(path), row_count=len(source['rows']))
                save(receipt_path, receipt)
                session['receipts'].append(label)
                print(label, status, len(source['rows']), messages, flush=True)
                if status != 'complete':
                    raise RuntimeError('Historical request incomplete; inspect saved receipt')
                time.sleep(2)
    except Exception as exc:
        session['error'] = str(exc)
        raise
    finally:
        app.disconnect()
        if thread is not None:
            thread.join(timeout=2)
        session.update(completed_at=datetime.now(UTC).isoformat(), messages=app.messages)
        save(SOURCE / ('session-' + session_id + '-private.json'), dict(session, managed_accounts=app.accounts))
        save(OUT / ('session-' + session_id + '.json'), session)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='+')
    parser.add_argument('--all-hours-control', action='store_true')
    args = parser.parse_args()
    acquire(args.symbols, args.all_hours_control)
