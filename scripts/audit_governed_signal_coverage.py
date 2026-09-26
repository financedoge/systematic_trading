"""Attribute missing constituent coverage without relaxing any research rule."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze_underlying_sectors import compatible_name
from run_constituent_research import verify_manifest
from systematic_trading.lean.contracts import write_json
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.constituent_signals import WINDOW


def audit(root):
    verify_manifest(root,'input_manifest.json')
    read=lambda p:json.loads(p.read_text(encoding='utf8'))
    protocol=read(root/'protocol.json');source=Path(protocol['stock_root'])
    inputs=GovernedInputs(Path(protocol['governed_root']),protocol['batch'])
    snapshots=[read(p) for p in sorted((source/'holdings').glob('*.json'))]
    aliases=read(source/'symbol_aliases.json')['aliases']
    for snap in snapshots:
        for row in snap['rows']:
            row['yahoo']=aliases.get(row['ticker'],row['yahoo'])
    days=[d for d in read(inputs.checked('calendar.json'))['sessions'] if '2011-01-03'<=d<=protocol['end']]
    index={d:i for i,d in enumerate(days)}
    decisions=[d for i,d in enumerate(days) if i and d>=protocol['start'] and d[:7]!=days[i-1][:7]]
    samples={}
    for decision in decisions:
        known=days[index[decision]-1]
        snap=next((s for s in reversed(snapshots) if (date.fromisoformat(s['as_of'])+timedelta(days=45)).isoformat()<=known),None)
        if snap is not None:
            samples[decision]=dict(known=known,snapshot=snap,window=days[index[known]-WINDOW+1:index[known]+1],reasons={},excluded=[])
    lookup={}
    for decision,sample in samples.items():
        for row in sample['snapshot']['rows']:
            lookup.setdefault(row['yahoo'],[]).append((decision,row))
    for count,(symbol,requests) in enumerate(lookup.items()):
        meta=inputs.audit(symbol);rows={r['trade_date']:r for r in inputs.rows(symbol,days[0],days[-1])}
        for decision,holding in requests:
            sample=samples[decision];weight=holding['market_value'];reason='supported'
            duplicate=sum(r['yahoo']==symbol for r in sample['snapshot']['rows'])!=1
            if duplicate or not compatible_name(holding['name'],meta.get('name'),holding['ticker']):
                reason='identity_name_or_duplicate'
            else:
                window=[rows.get(d) for d in sample['window']]
                if not all(r and r['adjusted_close'] is not None and r['adjusted_close']>0 for r in window):
                    reason='adjusted_history_missing'
                elif not all(r['raw_close'] is not None and r['raw_close']>0 for r in window):
                    reason='raw_price_unsupported'
                elif not all(r['raw_volume'] is not None and np.isfinite(r['raw_volume']) and r['raw_volume']>=0 for r in window):
                    reason='raw_volume_unsupported'
            sample['reasons'][reason]=sample['reasons'].get(reason,0)+weight
            if reason!='supported':
                sample['excluded'].append(dict(symbol=symbol,reason=reason,market_value=weight))
        if count%150==0:
            print('COVERAGE AUDIT',count,len(lookup),flush=True)
    output=[]
    for d,sample in samples.items():
        total=sum(sample['reasons'].values())
        fractions={k:v/total for k,v in sample['reasons'].items()}
        output.append(dict(date=d,known_through=sample['known'],snapshot=sample['snapshot']['as_of'],
            snapshot_stale=(date.fromisoformat(sample['known'])-date.fromisoformat(sample['snapshot']['as_of'])).days>140,
            coverage_by_reason=fractions,excluded_names=Counter(r['reason'] for r in sample['excluded']),
            largest_exclusions=[dict(symbol=r['symbol'],reason=r['reason'],holding_fraction=r['market_value']/total) for r in sorted(sample['excluded'],key=lambda r:r['market_value'],reverse=True)[:12]]))
    write_json(root/'coverage_decomposition.json',output)
    for year in ('2016','2020','2023','2026'):
        row=next(r for r in output if r['date'].startswith(year))
        print(json.dumps(row),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    audit(parser.parse_args().root)
