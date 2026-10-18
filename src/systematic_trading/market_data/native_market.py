"""Native serving histories; source precedence stays with the acquisition contract."""
from collections import defaultdict

from systematic_trading.market_data.analytics_store import timestamp
from systematic_trading.storage.parquet_lake import ParquetLake


class NativeMarketDataClient:
    def __init__(self, lake):
        self.lake = lake

    @classmethod
    def from_settings(cls, settings):
        return cls(ParquetLake.from_settings(settings))

    def ensure_daily_bars_table(self):
        self.lake.initialize()

    def ensure_fx_rates_table(self):
        self.lake.initialize()

    def _write(self, table, records):
        groups = defaultdict(list)
        count = 0
        for r in records:
            identity = r['symbol'] if table=='daily_bars' else r['base_currency']+'/'+r['quote_currency']
            groups['market/'+table+'/'+identity].append(r)
            count += 1
        date_key = 'trade_date' if table=='daily_bars' else 'rate_date'
        for key, rows in groups.items():
            with self.lake.catalog.writer(key) as c:
                current = self.lake.catalog.get(key,connection=c)
                manifest = self.lake.manifest(key,connection=c)
                existing = {r[date_key]:r for r in self.lake.select([manifest])}
                for r in rows:
                    old = existing.get(r[date_key])
                    if old and timestamp(old['ingested_at']) > timestamp(r['ingested_at']):
                        continue
                    existing[r[date_key]] = dict(r,observed_at=r[date_key],point_key=r[date_key])
                merged = [existing[d] for d in sorted(existing)]
                prepared = self.lake.prepare(merged)
                self.lake.catalog.commit(c,key,prepared['logical_sha256'],prepared,
                    expected_head=current['revision'] if current else None)
        return count

    def insert_daily_bar_rows(self, rows):
        return self._write('daily_bars',rows)

    def insert_fx_rate_rows(self, rows):
        return self._write('fx_rates',rows)

    def _read(self, key, start, end, limit):
        filters = []
        if start: filters.append(('observed_at','>=',str(start)))
        if end: filters.append(('observed_at','<=',str(end)+'T23:59:59.999999+00:00'))
        return self.lake.select([self.lake.manifest(key)],filters=filters,order=[('observed_at','ASC')],limit=limit)

    def query_daily_bars(self, *, symbol, start_date=None, end_date=None, limit=5000):
        return self._read('market/daily_bars/'+symbol.upper(),start_date,end_date,limit)

    def query_daily_bar_dates(self, *, symbol, start_date=None, end_date=None):
        return [r['trade_date'] for r in self.query_daily_bars(symbol=symbol,start_date=start_date,end_date=end_date,limit=100000)]

    def query_daily_bar_symbols(self):
        with self.lake.catalog.connect() as c:
            rows = c.execute("SELECT h.dataset_key,d.manifest FROM native_analytics.heads h JOIN native_analytics.datasets d "
                "USING(workspace,dataset_key,revision) WHERE workspace=%s AND starts_with(h.dataset_key,'market/daily_bars/') ORDER BY h.dataset_key",
                (self.lake.catalog.workspace,)).fetchall()
        result = []
        for row in rows:
            records = self.lake.select([row['manifest']],order=[('observed_at','ASC')])
            if records:
                result.append(dict(symbol=row['dataset_key'].removeprefix('market/daily_bars/'),
                    row_count=len(records),first_trade_date=records[0]['trade_date'],last_trade_date=records[-1]['trade_date']))
        return result

    def query_fx_rates(self, *, base_currency, quote_currency='CNH', start_date=None, end_date=None, limit=None):
        return self._read('market/fx_rates/'+base_currency.upper()+'/'+quote_currency.upper(),start_date,end_date,limit)

    def delete_daily_bar_dates(self, *, symbol, trade_dates):
        dates = set(trade_dates)
        if not dates: return 0
        key = 'market/daily_bars/'+symbol.upper()
        with self.lake.catalog.writer(key) as c:
            current = self.lake.catalog.get(key,connection=c)
            if not current: return 0
            rows = self.lake.select([self.lake.manifest(key,connection=c)])
            retained = [r for r in rows if r['trade_date'] not in dates]
            manifest = self.lake.prepare(retained)
            self.lake.catalog.commit(c,key,manifest['logical_sha256'],manifest,expected_head=current['revision'])
            return len(rows)-len(retained)
