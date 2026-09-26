"""Resume only the idempotent research archive importer after transient local HTTP errors."""
import runpy
from pathlib import Path
import time
from urllib.error import URLError

from systematic_trading.market_data.golden import ClickHouseMarketDataClient

original=ClickHouseMarketDataClient.execute


def execute(self, sql):
    # Every write in this importer has a stable version/key and FINAL hash readback.
    # Do not install this retry policy on trading or other database clients.
    self.timeout_seconds=20
    for attempt in range(4):
        try:
            return original(self,sql)
        except (URLError,TimeoutError,ConnectionError):
            if attempt==3:
                raise
            print('Transient archive connection failure; retrying verified idempotent batch',attempt+1,flush=True)
            time.sleep(1+attempt)


if __name__=='__main__':
    ClickHouseMarketDataClient.execute=execute
    runpy.run_path(str(Path(__file__).with_name('import_public_equity_archive.py')),run_name='__main__')
