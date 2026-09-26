"""Read pinned governance artifacts without substituting unsupported price bases."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256
from systematic_trading.research.constituent_signals import WINDOW, cohort_features
from systematic_trading.research.sector_hhi import causal_ema


class GovernedInputs:
    def __init__(self, root: Path, batch: str):
        self.root = root
        if sha256(root / 'manifest.json') != batch:
            raise ValueError('Governed batch manifest mismatch')
        self.manifest = json.loads((root / 'manifest.json').read_text(encoding='utf8'))
        self.used = {}

    def checked(self, relative):
        path = self.root / relative
        if relative not in self.manifest or sha256(path) != self.manifest[relative]:
            raise ValueError('Changed or unmanifested governed input: ' + relative)
        self.used[relative] = self.manifest[relative]
        return path

    def audit(self, symbol):
        return json.loads(self.checked(f'audits/{symbol}.json').read_text(encoding='utf8'))

    def rows(self, symbol, start, end):
        with gzip.open(self.checked(f'bars/{symbol}.jsonl.gz'), 'rt', encoding='utf8') as stream:
            rows = [r for line in stream if start <= (r := json.loads(line))['trade_date'] <= end]
        dates = [r['trade_date'] for r in rows]
        if dates != sorted(set(dates)):
            raise ValueError('Duplicate or unsorted governed dates: ' + symbol)
        return rows


def etf_bar(row):
    """Keep the prior strategy's adjusted-price/split-adjusted-volume convention."""
    fields = {key: row['adjusted_' + key] for key in ('open', 'high', 'low', 'close')}
    if any(v is None or not np.isfinite(v) or v <= 0 for v in fields.values()):
        raise ValueError('Unsupported adjusted ETF bar')
    volume = row['source_volume']
    if volume is None or not np.isfinite(volume) or volume <= 0:
        raise ValueError('Unsupported ETF source volume')
    return dict(trade_date=row['trade_date'], **{k: str(v) for k, v in fields.items()}, volume=int(volume))


def diagnostic_features(close, volume, adjusted, sectors, weights, accepted):
    """Backward-only same-cohort HHI stencils, with genuine raw dollar activity."""
    out = cohort_features(close, volume, adjusted, sectors, weights, accepted)
    valid = (np.isfinite(close) & (close > 0) & np.isfinite(volume) & (volume >= 0)
             & np.isfinite(adjusted) & (adjusted > 0)).all(axis=0) & accepted
    if out['values'] is None:
        return out, valid
    for label, activity in [('dollar', close[:, valid] * volume[:, valid]), ('shares', volume[:, valid])]:
        totals = np.column_stack([activity[:, sectors[valid] == i].sum(axis=1) for i in range(11)])
        total = totals.sum(axis=1)
        if np.any(total <= 0):
            raise ValueError('No observed sector activity')
        hhi = ((totals / total[:, None]) ** 2).sum(axis=1)
        smooth = causal_ema(hhi, 10)
        out['values'].update({label+'_hhi': float(hhi[-1]), label+'_d1': float(hhi[-1]-hhi[-2]),
            label+'_d2': float(hhi[-1]-2*hhi[-2]+hhi[-3]), label+'_ema': float(smooth[-1]),
            label+'_ema_d1': float((smooth[-1]-smooth[-11])/10),
            label+'_ema_d2': float((smooth[-1]-2*smooth[-11]+smooth[-21])/100)})
    return out, valid


def fixed_cohort_return(initial, final, weights, selected):
    """No forward survivor reweighting: missing any selected endpoint invalidates the label."""
    if not selected.any():
        return None
    a, b, w = initial[selected], final[selected], weights[selected]
    if not (np.isfinite(a).all() and np.isfinite(b).all() and (a > 0).all() and (b > 0).all()):
        return None
    return float(np.average(b/a-1, weights=w))


def complete_windows(values):
    valid = np.isfinite(values) & (values > 0)
    counts = np.vstack([np.zeros((1, values.shape[1]), dtype=int), valid.cumsum(axis=0)])
    out = np.zeros_like(valid)
    out[WINDOW-1:] = counts[WINDOW:] - counts[:-WINDOW] == WINDOW
    return out
