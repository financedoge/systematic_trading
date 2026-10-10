from datetime import date, timedelta
import json
from types import SimpleNamespace

import pytest

from systematic_trading.market_data.governance_store import GovernanceStore


@pytest.mark.parametrize("corrupt", [False, True])
def test_bounded_transport_still_verifies_every_chunk(corrupt):
    received, sizes = [], []
    def execute(sql):
        rows = [json.loads(line) for line in sql.splitlines()[1:]]
        assert len(rows) <= 1000, "Long ETF histories must fit bounded HTTP requests"
        sizes.append(len(rows))
        received.extend(rows)
    def query(sql):
        assert " FINAL " in sql
        result = [dict(trade_date=r["trade_date"], hash=r["payload_hash"]) for r in received]
        if corrupt:
            result[1001]["hash"] = "incorrect-middle-chunk-hash"
        return result
    store = GovernanceStore(SimpleNamespace(workspace="test", client=SimpleNamespace(execute=execute), query=query))
    records = [dict(trade_date=str(date(2010,1,1)+timedelta(days=i)), value=i) for i in range(2501)]
    if corrupt:
        with pytest.raises(ValueError, match="readback mismatch"):
            store.insert_verified("governed_daily", "test-batch", "XLB", records)
    else:
        assert store.insert_verified("governed_daily", "test-batch", "XLB", records) == len(records)
    assert sizes == [1000,1000,501]
