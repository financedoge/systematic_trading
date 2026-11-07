"""Separate dated identifier corroboration from source-vintage availability."""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
import gzip
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from audit_wrds_holdings_coverage import within
from capture_holdings_identity import STUDY, PROTOCOL_HASH, checked, protocol, prior
from probe_alpaca_sip_source import ROOT, save, sha

AUDIT_HASH = '2ffaca48149964d84c018cf529a0d2a9ca20c30712ebd43572e17f50d13ee34d'
COUNTRIES={'US','BM','KY','VG'}


def valid_isin(value):
    if not isinstance(value,str) or len(value)!=12 or not value[:2].isalpha() or not value[-1].isdigit():
        return False
    if not value.isascii() or not value.isalnum() or value!=value.upper():
        return False
    digits=''.join(str(int(c,36)) for c in value)
    total=0
    for i,c in enumerate(reversed(digits)):
        n=int(c)*(2 if i%2 else 1)
        total+=n//10+n%10
    return total%10==0


def valid_cusip(value):
    if not isinstance(value,str) or len(value)!=9 or not value[-1].isdigit():
        return False
    if not value.isascii() or not value.isalnum() or value!=value.upper():
        return False
    total=0
    for i,c in enumerate(value[:8]):
        n=int(c,36)*(1+i%2)
        total+=n//10+n%10
    return (10-total%10)%10==int(value[-1])


def embedded_cusip(isin):
    if not valid_isin(isin):
        raise ValueError('Invalid ISIN checksum or shape')
    if isin[:2] not in COUNTRIES:
        return None
    value=isin[2:11]
    if not valid_cusip(value):
        raise ValueError('Invalid embedded CUSIP checksum')
    return value


def dated_record(rows,permno,symbol,cusip,day):
    matches=[r for r in rows if r['permno']==permno and r['ticker']==symbol
             and r['tradingsymbol']==symbol and r['cusip9']==cusip
             and within(r['secinfostartdt'],r['secinfoenddt'],day)]
    return matches[0] if len(matches)==1 else None


def receipt_groups(rows):
    if len({json.dumps(r,sort_keys=True) for r in rows})!=len(rows):
        raise ValueError('Exact repeated holding record')
    groups=defaultdict(list)
    for r in rows:
        if not r.get('eff_dt') or date.fromisoformat(r['eff_dt'])<date.fromisoformat(r['report_dt']):
            raise ValueError('Missing or preceding receipt date')
        groups[r['eff_dt']].append(r)
    return groups


def audit():
    p=protocol()
    plan=json.loads(checked(STUDY/'audit-plan.json',AUDIT_HASH))
    if set(plan['supported_embedded_cusip_countries'])!=COUNTRIES:
        raise ValueError('Changed jurisdiction scope')
    for name,h in plan['input_hashes'].items():
        checked(ROOT/name,h)
    old,old_rows=prior(p)
    cap=json.loads((STUDY/'capture.json').read_text())
    root=Path(cap['archive'])
    m=json.loads(checked(root/'manifest.json',cap['manifest_sha256']))
    if m['protocol_sha256']!=PROTOCOL_HASH or m['status']!='captured_pending_qualification':
        raise ValueError('Wrong or incomplete source capture')
    for name,h in m['files'].items():
        checked(root/name,h)
    data={}
    for q in m['queries']:
        raw=gzip.decompress(checked(root/q['path'],q['sha256']))
        if sha(raw)!=q['response_sha256']:
            raise ValueError('Changed source payload')
        d=json.loads(raw)
        if len(d['rows'])!=q['row_count']:
            raise ValueError('Changed source row count')
        data[q['name']]=[dict(zip(d['columns'],r,strict=True)) for r in d['rows']]
    sources=json.loads((STUDY/'public-sources.json').read_text())['sources']
    text={}
    for name,r in sources.items():
        if r['status']!='captured':
            raise ValueError('Required primary source not retained')
        raw=gzip.decompress(Path(r['path']).read_bytes())
        if sha(raw)!=r['sha256'] or r['url']!=p['public_sources'][name]:
            raise ValueError('Changed public source')
        text[name]=' '.join(' '.join(BeautifulSoup(raw,'html.parser').stripped_strings).split())
    required={'bermuda-numbering':['CUSIP numbers are derived from ISIN','first 2 letters and the last character'],
        'cayman-numbering':['embedded CUSIP or CINS','Cayman Islands','British Virgin Islands'],
        'cgs-identifiers':['positions 3-11 of a CGS ISIN'],
        'vnom-conversion':['Current CUSIP: 92763M105','New CUSIP: 927959106','November 13, 2023']}
    for name,terms in required.items():
        if any(term not in text[name] for term in terms):
            raise ValueError('Required primary-source definition not found')
    xmlpath=ROOT/'research/p421-quarter-20261104-v1/filings/0001752724-25-043691.xml.gz'
    sec=ET.fromstring(gzip.decompress(xmlpath.read_bytes())).findall('.//{*}invstOrSec')
    by_symbol=defaultdict(list)
    for node in sec:
        for ticker in node.findall('{*}identifiers/{*}ticker'):
            by_symbol[ticker.get('value')].append(node)
    results=[]
    details=[]
    history=data['security-history']
    for row in old['unmatched_crsp']:
        if row['permno'] is None:
            continue
        symbol=row['ticker']
        nodes=by_symbol[symbol]
        if len(nodes)!=1:
            raise ValueError('Unmatched filed ticker candidate is ambiguous')
        node=nodes[0]
        isins=[x.get('value') for x in node.findall('{*}identifiers/{*}isin')]
        if len(isins)!=1:
            raise ValueError('Missing or ambiguous filed ISIN')
        isin=isins[0]
        cusip=embedded_cusip(isin)
        result=dict(symbol=symbol,isin=isin,status='unresolved_foreign_bridge',
            original_holding_identifier_preserved=True)
        dated=dated_record(history,row['permno'],symbol,cusip,p['snapshot_date']) if cusip else None
        if cusip and dated:
            old_cusip=row['cusip']
            if symbol=='VNOM':
                old_record=dated_record(history,row['permno'],symbol,'92763M105','2023-11-12')
                new_record=dated_record(history,row['permno'],symbol,'927959106','2023-11-13')
                if old_cusip!='92763M10' or cusip!='927959106' or old_record is None or new_record is None:
                    raise ValueError('Conversion does not agree with both dated security states')
                reason='official_conversion_and_dated_permanent_identity'
            elif old_cusip==cusip[:8]:
                reason='documented_NNA_embedding_and_dated_CUSIP'
            else:
                reason=None
            if reason:
                if node.findtext('{*}curCd')!='USD' or node.findtext('{*}units')!='NS':
                    raise ValueError('Unsupported position units')
                sd=Decimal(str(row['nbr_shares']))-Decimal(node.findtext('{*}balance'))
                vd=Decimal(str(row['market_val']))-Decimal(node.findtext('{*}valUSD'))
                result.update(status='identifier_corroborated',basis=reason,
                    exact_shares=sd==0,exact_value=vd==0)
                details.append(dict(symbol=symbol,cusip9=cusip,holding=row,dated_identity=dated,
                    share_difference=str(sd),value_difference=str(vd)))
        elif cusip:
            result['status']='missing_or_ambiguous_dated_identity'
        results.append(result)
    mixed=data['mixed-receipt-holdings']
    case=p['mixed_receipt_case']
    if len(mixed)!=case['expected_rows'] or any(r['report_dt']!=case['report_date'] for r in mixed):
        raise ValueError('Changed mixed-receipt control')
    groups=receipt_groups(mixed)
    if len(groups)!=case['expected_groups']:
        raise ValueError('Changed receipt groups')
    prior_groups={r['eff_dt']:r for r in old_rows['holdings-coverage']
                  if r['crsp_portno']==mixed[0]['crsp_portno'] and r['report_dt']==case['report_date']}
    receipt_result=[]
    for day,rows in sorted(groups.items()):
        g=prior_groups[day]
        if len(rows)!=g['rows'] or len({r['security_rank'] for r in rows})!=g['distinct_ranks']:
            raise ValueError('Receipt group does not reproduce prior coverage counts')
        total=math.fsum(r['percent_tna'] for r in rows if r['percent_tna'] is not None)
        receipt_result.append(dict(receipt_date=day,rows=len(rows),reported_weight_sum=total,
            aggregate_weight_residual=total-g['percent_tna_sum']))
    ids=[r['cusip'] for r in mixed if r['cusip']]
    detail_path=root/'identity-and-receipt-comparison.json'
    save(detail_path,dict(identity_pairs=details,mixed_receipt_rows=mixed,identity_results=results))
    supported=[r for r in results if r['status']=='identifier_corroborated']
    earlier=json.loads((ROOT/p['source_assessment']).read_text())['mdy']['identifier_matched_pairs']
    output=dict(status='bounded_identity_and_receipt_check_complete',protocol_sha256=PROTOCOL_HASH,
        audit_plan_sha256=AUDIT_HASH,source_archive=str(root),source_manifest_sha256=cap['manifest_sha256'],
        public_source_receipt_sha256=sha((STUDY/'public-sources.json').read_bytes()),
        identity_results=results,newly_corroborated=len(supported),prior_corroborated=earlier,
        total_corroborated=earlier+len(supported),remaining_equity_bridges=19-len(supported),
        new_pairs_exact_shares_and_value=all(r['exact_shares'] and r['exact_value'] for r in supported),
        mixed_receipt=dict(symbol=case['symbol'],report_date=case['report_date'],groups=receipt_result,
            exact_duplicate_rows=0,repeated_nonmissing_cusips=sum(n-1 for n in Counter(ids).values() if n>1),
            missing_cusip_rows=len(mixed)-len(ids),
            later_receipt_rows=sum(g['rows'] for g in receipt_result[1:]),
            later_receipt_weight=math.fsum(g['reported_weight_sum'] for g in receipt_result[1:]),
            earliest_receipt_is_not_complete_snapshot=True),
        details=dict(path=str(detail_path),sha256=sha(detail_path.read_bytes())),
        source_values_rewritten=0,active_catalog_publications=0,strategy_replays=0,
        historical_available_at=None,
        limitations=['Dated identity corroboration does not certify historical vendor dissemination or original-vintage values.',
            'One mixed-receipt control does not qualify all 461 mixed snapshots.',
            'Unresolved foreign bridges, portfolio completeness and price/activity coverage remain separate gates.'],
        runner_sha256=sha(Path(__file__).read_bytes()))
    save(STUDY/'assessment.json',output)
    print(json.dumps({k:output[k] for k in ('newly_corroborated','total_corroborated',
        'remaining_equity_bridges','new_pairs_exact_shares_and_value','mixed_receipt')}),flush=True)


if __name__=='__main__':
    audit()
