"""Evaluate the frozen ten-stock qualification pilot using governed prices and source evidence."""
import gzip
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

from acquire_ten_qualification import OUT, CACHE, PRIOR, ROOT, read, save, sha
from systematic_trading.research.governed_inputs import GovernedInputs
from diagnose_mdy_price_audits import comparison
from qualify_p421_quarter import complete_window, window_days, CUTOFF

REQUIRED_GATES = ('complete_supported_window','historical_identity_anchors','current_isin_match',
                  'filing_valuation_match','independent_daily_price_volume','dated_security_continuity',
                  'resolved_prior_source_review')

def identity_matches(symbol, isin, issuer, broker):
    filings=issuer['filings']
    historical=bool(filings) and all(
        symbol in f['fields'].get('TradingSymbol',[]) and bool(f['fields'].get('Security12bTitle'))
        and {int(v) for v in f['fields'].get('EntityCentralIndexKey',[])}=={issuer['cik']} for f in filings)
    current=(broker['status']=='identity_verified' and broker['lookup']==dict(secIdType='ISIN',secId=isin)
             and broker['details']['contract']['symbol']==symbol)
    return dict(historical_filing_anchors=historical,current_isin_contract=current)


def qualified(gates):
    return all(gates.get(key) is True for key in REQUIRED_GATES)


def run():
    protocol=read(OUT/'protocol.json')
    manifest=read(PRIOR/'artifact-manifest.json')
    if sha((PRIOR/'artifact-manifest.json').read_bytes())!=protocol['prior_manifest_sha256']:
        raise ValueError('Changed frozen inventory')
    if sha((PRIOR/'inventory.json').read_bytes())!=manifest['inventory.json']:
        raise ValueError('Changed inventory rows')
    inventory=read(PRIOR/'inventory.json')
    pins=read(ROOT/'research/p421-coverage-20261104-v1/pins.json')['price']
    g=GovernedInputs(Path(pins['root']),pins['batch'])
    if g.batch!=inventory['batch'] or g.parent.batch!=inventory['parent_batch']:
        raise ValueError('Price pin mismatch')
    pilot=ROOT/'research/p421-quarter-20261104-v1'
    xmlpath=pilot/'filings/0001752724-25-043691.xml.gz'
    if sha(xmlpath.read_bytes())!=read(pilot/'artifact-manifest.json')[xmlpath.relative_to(pilot).as_posix()]:
        raise ValueError('Changed MDY filing')
    filed=ElementTree.fromstring(gzip.decompress(xmlpath.read_bytes())).findall('.//{*}invstOrSec')
    by_symbol={p.find('{*}identifiers/{*}ticker').get('value'):p for p in filed}
    broker=read(OUT/'ib-contracts.json')
    probe=read(CACHE/'ibkr-probe.json')
    if 'rows' in probe and probe['rows']:
        raise ValueError('New broker observations require the independent-source reconciliation stage')
    save(OUT/'historical-data-request.json',dict(symbols=protocol['symbols'],start=protocol['window'][0],end=protocol['window'][1],
       required_sessions=253,fields=['open','high','low','close','share_volume','adjusted_close','corporate_actions'],
       session='Record regular-hours versus full-session coverage explicitly.',
       basis='Record split-only versus dividend/split price basis, action units, volume units, corrections and source vintage.',
       identities=[dict(symbol=s,isin=next(r for r in inventory['holdings'] if r['symbol']==s)['isin'][0],
                        broker_conid=broker['funds'][s]['details']['contract']['conId']) for s in protocol['symbols']]))
    days=window_days(CUTOFF)
    results=[]
    for symbol in protocol['symbols']:
        entry=next(r for r in inventory['holdings'] if r['symbol']==symbol)
        issuer=read(OUT/'issuers'/(symbol+'.json'))
        for filing in issuer['filings']:
            raw=gzip.decompress((CACHE/(filing['accession']+'.gz')).read_bytes())
            if sha(raw)!=filing['source']['sha256']:
                raise ValueError('Changed original SEC filing '+symbol)
        identity=identity_matches(symbol,entry['isin'][0],issuer,broker['funds'][symbol])
        current=g.audit(symbol)
        base=g.parent.audit(symbol)
        bars=g.rows(symbol,*protocol['window'])
        before=g.parent.rows(symbol,*protocol['window'])
        price_at_filing=next(r['raw_close'] for r in bars if r['trade_date']=='2024-12-31')
        position=by_symbol[symbol]
        value_per_share=float(Decimal(position.findtext('{*}valUSD'))/Decimal(position.findtext('{*}balance')))
        actions=[]
        with gzip.open(g.checked('actions/'+symbol+'.jsonl.gz'),'rt',encoding='utf8') as stream:
            for line in stream:
                r=json.loads(line)
                if (r['source_id']==current['primary_source'] and protocol['window'][0]<=r['date']<=protocol['window'][1]):
                    actions.append({k:r[k] for k in ('date','kind','amount','ratio') if k in r})
        price_pairs=[]
        for pair in base['overlaps']:
            dates=pair.get('conflicting_dates',[])
            if dates and pair['anchor']==base.get('primary_source'):
                price_pairs.append(dict(other_source=pair['candidate'],count=len(dates),first=min(dates),last=max(dates),
                                        intersects_window=bool(set(dates)&set(days))))
        gates=dict(complete_supported_window=complete_window(bars,days),
             historical_identity_anchors=identity['historical_filing_anchors'],current_isin_match=identity['current_isin_contract'],
             filing_valuation_match=abs(value_per_share-price_at_filing)<.005,
             independent_daily_price_volume=False,dated_security_continuity=False,resolved_prior_source_review=False)
        results.append(dict(symbol=symbol,equity_pct=entry['equity_pct'],cusip=entry['cusip'],isin=entry['isin'][0],
            broker_conid=broker['funds'][symbol]['details']['contract']['conId'],
            issuer_filing_dates=[f['filing_date'] for f in issuer['filings']],gates=gates,eligible_for_publication=qualified(gates),
            published_status=current['status'],cross_vintage=comparison(bars,before),filed_value_per_share=value_per_share,
            reconstructed_raw_close=price_at_filing,actions=actions,prior_price_pairs=price_pairs,
            volume_pairs=entry['volume_pairs'],source_review='Unresolved outside-window source differences retained. They do not establish an error inside this window.',
            internal_action_failures=[f for s in current['sources'] for f in s.get('factor_failures',[])]))
    save(OUT/'assessment.json',dict(selected_symbols=protocol['symbols'],equity_pct=sum(r['equity_pct'] for r in results),
        required_sessions=len(days),qualified_count=sum(r['eligible_for_publication'] for r in results),
        new_publications=0,results=results,broker_history_error=probe,
        source_probe_results=read(OUT/'acquisition.json')['nasdaq'],used=g.used,parent_used=g.parent.used,
        runner_sha256=sha(Path(__file__).read_bytes()),prior_inventory_sha256=sha((PRIOR/'inventory.json').read_bytes())))
    print('checked',len(results),'qualified',sum(r['eligible_for_publication'] for r in results))


if __name__=='__main__':
    run()
