"""Summarize the frozen governance batch without changing any source or price."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from systematic_trading.market_data.analytics_store import digest, encode

STRATEGY_ETFS='SPY DBC EWH EWJ EWY GLD HYG IEF LQD MCHI TLT VGK'.split()


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def main(root,output):
    output.mkdir(parents=True,exist_ok=True)
    catalog=read(root/'catalog.json')
    available=[r for r in catalog if r['rows']]
    stats=dict(batch=digest((root/'manifest.json').read_bytes()),**read(root/'summary.json'),
        with_history=len(available),without_history=len(catalog)-len(available),
        earliest=min(r['first'] for r in available),latest=max(r['last'] for r in available),
        without_internal_gaps=sum(not r['internal_gaps'] for r in available),
        complete_raw_internal=sum(r['raw_internal_coverage_complete'] for r in available),
        with_raw_support=sum(r['raw_rows']>0 for r in available),
        current_endpoint=sum(r['tail_status']=='current_to_cutoff' for r in available),
        stale_or_delisted=sum(r['tail_status']!='current_to_cutoff' for r in available),
        with_joined_segments=sum(r['joined_rows']>0 for r in available),
        with_price_disagreements=sum(r['conflict_dates']>0 for r in available),
        with_identity_review=sum(bool(r.get('unresolved_historical_names')) for r in available),
        with_pre_listing_quarantine=sum(r.get('pre_listing_source_observations',0)>0 for r in catalog),
        pre_listing_source_observations=sum(r.get('pre_listing_source_observations',0) for r in catalog))
    metrics=Counter()
    examples={}
    for path in (root/'audits').glob('*.json'):
        audit=read(path)
        for s in audit['sources']:
            metrics['invalid_source_observations']+=len(s.get('invalid_dates',[]))
            metrics['non_session_source_observations']+=len(s.get('non_session_dates',[]))
            metrics['duplicate_source_sessions']+=len(s.get('duplicate_issues',[]))
            metrics['distribution_or_split_check_failures']+=len(s.get('factor_failures',[]))
        for r in audit['overlaps']:
            metrics['overlap_pairs']+=1
            metrics['accepted_overlap_pairs' if r['accepted'] else 'rejected_overlap_pairs']+=1
            metrics['unexplained_raw_price_basis_pairs']+=r.get('raw_basis_agreement') is False
            metrics['unexplained_raw_volume_basis_pairs']+=r.get('raw_volume_basis_agreement') is False
        if audit['symbol'] in ['AAPL','NVDA','GE','ACT','CELG','HYXU','NET','TXG','WMS','DAL',*STRATEGY_ETFS]:
            examples[audit['symbol']]=audit
    stats['audit_counts']=dict(metrics)
    stats['source_counts']=dict(Counter(s['kind'] for s in read(root/'source_index.json')))
    discrepancies={}
    for symbol in STRATEGY_ETFS:
        current={}
        with gzip.open(root/'bars'/(symbol+'.jsonl.gz'),'rt',encoding='utf8') as f:
            for line in f:
                row=json.loads(line);current[row['trade_date']]=row['adjusted_close']
        legacy=next(s for s in read(root/'source_index.json') if s['symbol']==symbol and s['kind']=='legacy_adjusted')
        old={r['trade_date']:float(r['close']) for r in read(Path(legacy['path']))}
        dates=sorted(set(old)&set(current))
        errors=[]
        for prev,day in zip(dates,dates[1:]):
            new_return=current[day]/current[prev]-1
            old_return=old[day]/old[prev]-1
            if abs(old_return-new_return)>1e-5:
                errors.append(dict(date=day,previous_date=prev,old_return=old_return,governed_return=new_return,
                                   difference=old_return-new_return))
        discrepancies[symbol]=sorted(errors,key=lambda x:-abs(x['difference']))[:5]
    stats['legacy_snapshot_return_discrepancies']=discrepancies
    (output/'summary.json').write_text(encode(stats),encoding='utf8')
    (output/'examples.json').write_text(encode(examples),encoding='utf8')
    lines=['# Governed price audit results','',
        f"Batch: `{stats['batch']}`.",'',
        f"{len(catalog):,} symbols inventoried; {len(available):,} have governed histories and {stats['without_history']:,} remain unavailable or identity-blocked.",
        f"{stats['rows']:,} governed observations, {stats['raw_rows']:,} supported raw-price reconstructions and {stats['raw_volume_rows']:,} supported raw-volume reconstructions.",
        f"Observed coverage spans {stats['earliest']} to {stats['latest']}. {stats['without_internal_gaps']:,} series have no internal session gaps; {stats['complete_raw_internal']:,} have complete reconstructed-raw coverage over their observed span.",
        f"{stats['source_observations']:,} original source observations are available for comparison. {stats['with_joined_segments']:,} symbols use accepted earlier segments ({stats['joined_rows']:,} selected rows).",'',
        'Internal completeness is not listing-history certification. Source disagreements do not establish which provider is correct. Unsupported raw values stay null. Historical availability remains unknown.', '',
        f"{stats['pre_listing_source_observations']:,} original source observations across {stats['with_pre_listing_quarantine']:,} symbols precede the identity/start boundary and are quarantined from the joined history. The boundary is the preferred provider listing date, or conservatively its first valid observation when listing metadata is absent. Modern overlap does not validate a previous issuer using the same ticker.", '',
        '## Current strategy ETFs','',
        '| ETF | First | Last | Sessions | Raw price supported | Raw volume supported | Gaps | Status |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | --- |']
    lookup={r['symbol']:r for r in catalog}
    for symbol in STRATEGY_ETFS:
        r=lookup[symbol]
        lines.append(f"| {symbol} | {r.get('first','')} | {r.get('last','')} | {r['rows']:,} | {r['raw_rows']:,} | {r.get('raw_volume_rows',0):,} | {r.get('internal_gaps',0):,} | {r['status']} |")
    lines+=['','## Legacy ETF snapshot return discrepancies','',
        'These are measured differences against a consistent new vendor vintage, not independent exchange-tape certification. The May 26 boundary for SPY/HYG/LQD coincides with the saved source changing from `sqlite_price_bars` to `platform_market_data_store`. Earlier backtests need rerunning on governed inputs before promotion decisions.', '',
        '| ETF | Largest discrepancy date | Old daily return | Governed daily return | Difference (percentage points) |',
        '| --- | --- | ---: | ---: | ---: |']
    for symbol,errors in discrepancies.items():
        if errors:
            r=errors[0]
            lines.append(f"| {symbol} | {r['date']} | {100*r['old_return']:.4f}% | {100*r['governed_return']:.4f}% | {100*r['difference']:.4f} |")
    lines+=['','## Remaining work','',
        f"- {stats['stale_or_delisted']:,} observed histories end before the requested cutoff; distinguish delisting from missing provider coverage.",
        f"- {stats['with_identity_review']:,} available symbols have unresolved historical issuer-name mappings.",
        f"- {stats['with_price_disagreements']:,} available symbols have archived price disagreements requiring interpretation.",
        '- Resolve action and raw-basis failures with issuer/exchange evidence before lifting reconstruction restrictions.',
        '- Build dated security identifiers and verified rename mappings before using this catalog to map historical ETF holdings.',
        '- Preserve vintage limitations in research; do not treat retrieval dates as historical publication times.', '',
        'The complete per-symbol coverage and unresolved queue are in the frozen batch’s `coverage.csv`, `unresolved.csv` and audit JSON files.']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (output/'manifest.json').write_text(encode({p.name:digest(p.read_bytes()) for p in output.iterdir() if p.is_file() and p.name!='manifest.json'}),encoding='utf8')
    print(encode(stats),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.root,a.output)
