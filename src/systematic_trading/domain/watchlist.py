from __future__ import annotations

from pydantic import BaseModel

from systematic_trading.domain.market import Instrument
from systematic_trading.domain.research import ThesisMemo


class WatchlistEntry(BaseModel):
    instrument: Instrument
    thesis: ThesisMemo | None = None
