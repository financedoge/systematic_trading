"""Reproducible source inventory, price-basis audit and governed per-symbol exports."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import io
import json
from pathlib import Path
import shutil
import zipfile

from fetch_governance_history import BASE, ROOTS, ETFS, write
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.price_governance import (POLICY, PriceSource, consolidate, finite,
    names_agree, yahoo_source, governed_sessions)

SUPPLEMENT=BASE/'governance-etfs-20260926-v1'
EXTRA_ETFS='AOR BWX BWZ CBON CORN CPER DBA DBB DFE ECNS EPI EWT FEZ FXI HYXU IBND IGOV IWM MDY PPLT SHY SLV TIP UNG USO WEAT'.split()
ETFS=sorted(set(ETFS+EXTRA_ETFS))
CUTOFF='2026-09-25'

def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def collect_sources(fresh,output,only=None):
    universe=read(fresh/'universe.json')
    if SUPPLEMENT.exists():
        for symbol,item in read(SUPPLEMENT/'universe.json').items():
            universe.setdefault(symbol,item)
    if only:
        universe={s:v for s,v in universe.items() if s in only}
    identity_inputs={}
    for root_name in ROOTS:
        for path in sorted((BASE/root_name/'holdings').glob('*.json')):
            raw=path.read_bytes()
            identity_inputs[str(path)]=digest(raw)
            snapshot=json.loads(raw)
            for row in snapshot['rows']:
                if row['yahoo'] not in universe:
                    continue
                periods=universe[row['yahoo']].setdefault('name_periods',{})
                period=periods.setdefault(row['name'],dict(first_seen=snapshot['as_of'],last_seen=snapshot['as_of']))
                period['first_seen']=min(period['first_seen'],snapshot['as_of'])
                period['last_seen']=max(period['last_seen'],snapshot['as_of'])
    write(output/'identity_inputs_manifest.json',identity_inputs)
    write(output/'universe.json',universe)
    sources=[]
    for root_name in ROOTS:
        root=BASE/root_name
        for path in sorted((root/'bars_metadata').glob('*.json')):
            if path.stem not in universe:
                continue
            m=read(path)
            raw=root/'bars_raw'/path.name
            if m['status']=='ok' and raw.exists() and m.get('observations',0):
                sources.append(dict(symbol=path.stem,path=str(raw),kind='yahoo',name=m.get('name',''),
                    raw_sha256=digest(raw.read_bytes()),source_id=f'sector-research/{root_name}/bars/{path.stem}',
                    vintage=m['retrieved_at'],action_start='2011-01-03' if root_name.startswith('ivv') else '2018-10-01',
                    action_end='2026-09-24',priority=60 if root_name.startswith('ivv') else 50,already_archived=True))
    sector=BASE/'sector-hhi-20260926-v1'
    prov=read(sector/'provenance.json')
    for symbol,m in prov.items():
        if symbol not in universe:
            continue
        path=sector/'raw'/f'{symbol}.json'
        sources.append(dict(symbol=symbol,path=str(path),kind='yahoo',name='',raw_sha256=digest(path.read_bytes()),
            source_id=f'sector-research/{sector.name}/bars/{symbol}',vintage=m['retrieved_at'],action_start='2018-06-19',
            action_end='2026-09-24',priority=50,already_archived=True))
    original=BASE/'ivv-public-archive-subset-20260926-v1'
    indexed={(x['provider'],x['symbol']):x for x in read(original/'archive_index.json')}
    archives=BASE/'public-equity-archives-20260926'
    yahoo_names={}
    for provider in ('yahoo2020','stooq2017'):
        archive=archives/(provider+'.zip')
        parent_hash=digest(archive.read_bytes())
        folder=output/'source_files'/provider
        folder.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            if provider=='yahoo2020':
                yahoo_names={r['Symbol']:r['Security Name'] for r in csv.DictReader(io.StringIO(z.read('symbols_valid_meta.csv').decode()))}
            names=set(z.namelist())
            for symbol in universe:
                original_item=indexed.get((provider,symbol))
                if original_item:
                    path=original/original_item['path']
                    name=original_item['name']
                    source_id=f'sector-research/{original.name}/bars/{provider}/{symbol}'
                    raw_hash=original_item['raw_sha256']
                else:
                    member=(f'etfs/{symbol}.csv' if symbol in ETFS else f'stocks/{symbol}.csv') if provider=='yahoo2020' else f'Data/Stocks/{symbol.lower()}.us.txt'
                    if member not in names:
                        continue
                    raw=z.read(member)
                    path=folder/(symbol+'.csv')
                    path.write_bytes(raw)
                    raw_hash=digest(raw)
                    name=yahoo_names.get(symbol,'')
                    source_id=f'governance-source/{output.name}/{provider}/{symbol}'
                sources.append(dict(symbol=symbol,path=str(path),kind=provider,name=name,raw_sha256=raw_hash,
                    source_id=source_id,vintage='2020-04-02' if provider=='yahoo2020' else '2017-11-16',
                    priority=30 if provider=='yahoo2020' else 10,already_archived=bool(original_item),
                    dated_holdings_identity=bool(original_item and provider=='stooq2017'),
                    archive_sha256=parent_hash,identity_evidence='Publisher name for Yahoo; Stooq name is provisional pending numerical overlap'))
    for symbol in universe:
        meta_path=fresh/'metadata'/f'{symbol}.json'
        if not meta_path.exists():
            continue
        m=read(meta_path)
        if m['status']!='ok':
            continue
        path=fresh/'raw'/f'{symbol}.json'
        sources.append(dict(symbol=symbol,path=str(path),kind='yahoo',name=m.get('name',''),raw_sha256=m['raw_sha256'],
            source_id=f'governance-source/{fresh.name}/bars/{symbol}',vintage=m['retrieved_at'],action_start=m['requested_start'],
            action_end=m['retrieved_at'][:10],priority=100,already_archived=False))
    if SUPPLEMENT.exists():
        for path in sorted((SUPPLEMENT/'raw').glob('*.json')):
            if path.stem not in universe:
                continue
            m=read(SUPPLEMENT/'metadata'/path.name)
            if m['status']=='ok':
                sources.append(dict(symbol=path.stem,path=str(path),kind='yahoo',name=m.get('name',''),raw_sha256=m['raw_sha256'],
                    source_id=f'governance-source/{SUPPLEMENT.name}/bars/{path.stem}',vintage=m['retrieved_at'],action_start=m['requested_start'],
                    action_end=m['retrieved_at'][:10],priority=100,already_archived=False))
        for path in sorted((SUPPLEMENT/'golden').glob('*.json')):
            if path.stem not in universe:
                continue
            name=next((s['name'] for s in sources if s['symbol']==path.stem and s['priority']==100),path.stem)
            sources.append(dict(symbol=path.stem,path=str(path),kind='legacy_unknown',name=name,raw_sha256=digest(path.read_bytes()),
                source_id=f'governance-source/{SUPPLEMENT.name}/golden/{path.stem}',vintage='2026-09-26',priority=0,already_archived=False))
    # Frozen strategy prices have already had OHLC adjusted. Keep their distinct
    # convention and compare to the new ETF histories without calling them raw.
    snapshot=Path('D:/systematic_trading_data/lean/research/flow-concentration-20260926-v3/snapshot/bars.json')
    snap=read(snapshot)
    for symbol,rows in snap.items():
        if symbol not in universe:
            continue
        path=output/'source_files'/f'legacy-etf-{symbol}.json'
        write(path,rows)
        sources.append(dict(symbol=symbol,path=str(path),kind='legacy_adjusted',name=next((s['name'] for s in sources if s['symbol']==symbol and s['priority']==100),symbol),
            raw_sha256=digest(path.read_bytes()),source_id=f'governance-source/{output.name}/legacy-etf/{symbol}',
            vintage='2026-09-26',priority=20,already_archived=False,parent_sha256=digest(snapshot.read_bytes())))
    write(output/'source_index.json',sources)
    return universe,sources


def load_source(item,universe):
    path=Path(item['path'])
    raw=path.read_bytes()
    if digest(raw)!=item['raw_sha256']:
        raise ValueError('Source changed: '+str(path))
    common=dict(key=item['source_id'],symbol=item['symbol'],raw_hash=item['raw_sha256'],vintage=item['vintage'],priority=item['priority'])
    if item['kind']=='yahoo':
        s=yahoo_source(json.loads(raw),action_start=item['action_start'],**common)
        s.action_end=item['action_end']
    else:
        rows={}
        values=json.loads(raw) if item['kind'].startswith('legacy_') else csv.DictReader(io.StringIO(raw.decode('utf8')))
        duplicate=[]
        for r in values:
            if item['kind'].startswith('legacy_'):
                d=r['trade_date']
                row={f:finite(r[f]) for f in ('open','high','low','close','volume')}
                row['adjusted_close']=row['close']
            else:
                d=r['Date']
                row={f:finite(r.get(f.title())) for f in ('open','high','low','close','volume')}
                row['adjusted_close']=finite(r.get('Adj Close',r['Close']))
            row['source_point_key']=d
            if d in rows:
                duplicate.append(dict(date=d,issue='duplicate_csv_session'))
            rows[d]=row
        for d in {x['date'] for x in duplicate}:
            rows.pop(d,None)
        s=PriceSource(name=item['name'],provider=item['kind'],rows=rows,
                      basis='unknown' if item['kind']=='legacy_unknown' else 'split_adjusted' if item['kind']=='yahoo2020' else 'dividend_adjusted',issues=duplicate,**common)
    expected=universe.get(s.symbol,{})
    holdings=expected.get('holdings_names',[])
    name_match=any(names_agree(s.name,n) for n in holdings)
    s.metadata['identity_eligible']=bool((s.symbol in ETFS or name_match or not holdings)
        and (s.metadata.get('instrumentType','EQUITY')=='EQUITY' or s.symbol in ETFS))
    # Stooq has no name field of its own. It cannot independently establish the
    # identity of a historical series, even when a later directory supplies one.
    if s.provider=='stooq2017':
        s.metadata['provisional_identity']=True
        s.metadata['dated_holdings_identity']=item.get('dated_holdings_identity',False)
    return s


_build_context = None


def initialize_build_worker(lookup,universe,sessions,output):
    global _build_context
    _build_context=(lookup,universe,sessions,output)


def build_symbol(symbol):
    lookup,universe,sessions,output=_build_context
    loaded=[load_source(item,universe) for item in lookup.get(symbol,[])]
    # A name-less/provisional Stooq series needs an independently named
    # overlapping source; its numerical comparison will gate joining.
    for s in loaded:
        if s.metadata.get('provisional_identity') and not s.metadata.get('dated_holdings_identity') and not any(x.provider!='stooq2017' and x.metadata['identity_eligible'] for x in loaded):
            s.metadata['identity_eligible']=False
    bars,audit,actions=consolidate(symbol,loaded,sessions,CUTOFF)
    audit.update(holdings_names=universe[symbol]['holdings_names'],roles=universe[symbol]['roles'],
        historical_name_periods=universe[symbol].get('name_periods',{}),
        identity_exclusions=[dict(source_id=s.key,name=s.name,reason='provider identity does not match holdings or lacks independent identity evidence') for s in loaded if not s.metadata['identity_eligible']],
        requested_cutoff=CUTOFF)
    unresolved=[n for n in audit['holdings_names'] if not names_agree(n,audit.get('name',''))]
    audit['provisional_identity_key']=digest(encode(dict(symbol=symbol,provider_name=audit.get('name'))))
    audit['unresolved_historical_names']=unresolved
    if unresolved and bars:
        audit['status']='review'
    # Retain every candidate comparison, including rejected identities.
    acceptance={s['source_id']:s for s in audit['sources']}
    comparisons=[]
    for s in loaded:
        accepted=acceptance.get(s.key,{})
        for d,r in sorted(s.rows.items()):
            if d>CUTOFF:
                continue
            comparisons.append(dict(symbol=symbol,trade_date=d,source_id=s.key,source_hash=s.raw_hash,
                source_close=r['close'],source_adjusted_close=r['adjusted_close'] if s.basis!='unknown' else None,source_volume=r['volume'],
                rebased_adjusted_close=r['adjusted_close']*accepted['comparison_scale'] if r['adjusted_close'] and accepted.get('comparison_scale')
                and (not accepted.get('eligible_from') or d>=accepted['eligible_from']) else None,
                accepted=bool(accepted.get('accepted')) and (not accepted.get('eligible_from') or d>=accepted['eligible_from']),
                exclusion_reason='before_provider_listing_boundary_identity_unresolved' if accepted.get('eligible_from') and d<accepted['eligible_from'] else None,
                price_basis=s.basis))
    for sub,records in [('bars',bars),('actions',actions),('comparisons',comparisons)]:
        with (output/sub/(symbol+'.jsonl.gz')).open('wb') as binary:
            with gzip.GzipFile(fileobj=binary,mode='wb',filename='',mtime=0) as compressed:
                with io.TextIOWrapper(compressed,encoding='utf8',newline='\n') as f:
                    for row in records:
                        f.write(encode(row)+'\n')
    write(output/'audits'/(symbol+'.json'),audit)
    compact={k:v for k,v in audit.items() if k not in ('sources','overlaps','gaps','seams','identity_exclusions')}
    compact['source_count']=len(loaded)
    compact['rejected_sources']=len(audit['identity_exclusions'])+sum(not s['accepted'] for s in audit['sources'])
    return compact,len(comparisons),len(actions)


def build(fresh,output,only=None,workers=1):
    if (output/'manifest.json').exists():
        raise ValueError('Governed build is frozen. Use another output directory.')
    output.mkdir(parents=True,exist_ok=True)
    if only is None and not (fresh/'manifest.json').exists():
        raise ValueError('Wait for the complete frozen source collection')
    if only is None:
        for input_root in (fresh,SUPPLEMENT):
            for name,expected in read(input_root/'manifest.json').items():
                if digest((input_root/name).read_bytes())!=expected:
                    raise ValueError('Frozen provider input changed: '+name)
    if (output/'source_index.json').exists():
        universe,sources=read(output/'universe.json'),read(output/'source_index.json')
    else:
        universe,sources=collect_sources(fresh,output,only)
    sessions,calendar_metadata=governed_sessions('1950-01-01',CUTOFF)
    write(output/'calendar.json',dict(**calendar_metadata,sessions=sorted(sessions)))
    write(output/'policy.json',POLICY)
    for sub in ('bars','audits','actions','comparisons'):
        (output/sub).mkdir(exist_ok=True)
    lookup={}
    for item in sources:
        lookup.setdefault(item['symbol'],[]).append(item)
    catalog=[]
    counts=dict(symbols=0,rows=0,raw_rows=0,raw_volume_rows=0,joined_rows=0,source_observations=0,actions=0,statuses={})
    symbols=[symbol for symbol in sorted(universe) if not only or symbol in only]
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize_build_worker,
            initargs=(lookup,universe,sessions,output)) as pool:
        for i,(compact,comparison_count,action_count) in enumerate(pool.map(build_symbol,symbols,chunksize=2),1):
            catalog.append(compact)
            counts['symbols']+=1
            for key in ('rows','raw_rows','raw_volume_rows','joined_rows'):
                counts[key]+=compact.get(key,0)
            counts['source_observations']+=comparison_count
            counts['actions']+=action_count
            counts['statuses'][compact['status']]=counts['statuses'].get(compact['status'],0)+1
            if i%100==0 or only:
                print('BUILD',i,compact['symbol'],counts,flush=True)
    write(output/'catalog.json',catalog)
    write(output/'summary.json',counts)
    fields=['symbol','name','first','last','rows','raw_rows','raw_volume_rows','internal_gaps','conflict_dates','pre_listing_source_observations',
            'volume_conflict_pairs','joined_rows','tail_status','identity_status','status']
    for filename,items in [('coverage.csv',catalog),('unresolved.csv',[r for r in catalog if r['status']!='audited_with_limitations'
        or r.get('raw_rows',0)<r['rows'] or r.get('tail_status')!='current_to_cutoff'])]:
        with (output/filename).open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
            writer.writeheader()
            writer.writerows(items)
    shutil.copyfile(__file__,output/'build_source.py')
    import systematic_trading.research.price_governance as engine
    shutil.copyfile(engine.__file__,output/'price_governance.py')
    write(output/'input_manifest.json',{s['path']:s['raw_sha256'] for s in sources})
    write(output/'manifest.json',{p.relative_to(output).as_posix():digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()})
    print('FROZEN',counts,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fresh',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--only',nargs='*')
    p.add_argument('--workers',type=int,choices=range(1,9),default=1)
    a=p.parse_args()
    build(a.fresh,a.output,a.only,a.workers)
