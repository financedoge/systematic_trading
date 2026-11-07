"""Inspect retained holdings coverage and reconcile one filed snapshot, without admission."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import gzip
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from capture_wrds_holdings_coverage import STUDY, PROTOCOL_HASH
from probe_alpaca_sip_source import ROOT, save, sha

AUDIT_HASH = '52d472efa511a9b366f3a0d5bd0841f9065ac21febe2608f6fdebc57b8fe46f7'


def within(start, end, day):
    try:
        return date.fromisoformat(str(start)) <= date.fromisoformat(str(day)) <= date.fromisoformat(str(end))
    except ValueError:
        return False


def candidates(names, maps, symbol, day):
    active = [n for n in names if n['ticker'] == symbol and n['et_flag'] == 'F'
              and within(n['chgdt'], n['chgenddt'], day)]
    if len(active) != 1:
        return []
    n = active[0]
    mapped = [m for m in maps if m['crsp_fundno'] == n['crsp_fundno'] and within(m['begdt'],m['enddt'],day)]
    if len(mapped) != 1 or mapped[0]['crsp_portno'] != n['crsp_portno']:
        return []
    return [int(mapped[0]['crsp_portno'])]


def sec_identifier(node):
    raw = node.findtext('{*}cusip', '').strip()
    keys = set()
    if len(raw) == 9 and raw != '000000000':
        keys.add(raw[:8])
    for isin in node.findall('{*}identifiers/{*}isin'):
        value = isin.get('value', '')
        if value.startswith('US') and len(value) == 12:
            keys.add(value[2:10])
    if len(keys) > 1:
        raise ValueError('Conflicting filed CUSIP and US ISIN')
    return next(iter(keys), None)


def audit():
    def checked(path, h):
        raw = path.read_bytes()
        if sha(raw) != h:
            raise ValueError('Changed source: '+str(path))
        return raw

    p = json.loads(checked(STUDY/'protocol.json', PROTOCOL_HASH))
    plan = json.loads(checked(STUDY/'audit-plan.json', AUDIT_HASH))
    for path,h in plan['input_hashes'].items():
        checked(ROOT/path,h)
    capture = json.loads((STUDY/'capture.json').read_text())
    root = Path(capture['archive'])
    m = json.loads(checked(root/'manifest.json',capture['manifest_sha256']))
    if m['status'] != 'captured_pending_qualification' or m['protocol_sha256'] != PROTOCOL_HASH:
        raise ValueError('Wrong or incomplete holdings capture')
    for filename,h in m['files'].items():
        checked(root/filename,h)
    data = {}
    for q in m['queries']:
        raw = gzip.decompress(checked(root/q['path'],q['sha256']))
        if sha(raw) != q['response_sha256']:
            raise ValueError('Changed source response')
        d = json.loads(raw)
        if len(d['rows']) != q['row_count']:
            raise ValueError('Source count mismatch')
        data[q['name']] = [dict(zip(d['columns'],r,strict=True)) for r in d['rows']]
    names,maps,coverage,holdings = (data[n] for n in ('fund-names','portfolio-map','holdings-coverage','mdy-december-holdings'))
    by_fund = {}
    for symbol in p['funds']:
        possible = {n['crsp_portno'] for n in names if n['ticker']==symbol}
        rows = [r for r in coverage if r['crsp_portno'] in possible]
        matched = [r for r in rows if candidates(names,maps,symbol,r['report_dt']) == [int(r['crsp_portno'])]]
        days = sorted({r['report_dt'] for r in matched})
        by_fund[symbol] = dict(candidate_rows=len(rows),dated_mapping_rows=len(matched),
            excluded_mapping_rows=len(rows)-len(matched),report_dates=len(days),
            first_report=days[0] if days else None,last_report=days[-1] if days else None,
            identity_status='dated_vendor_candidate_only_not_independent_fund_certification')
    lags = [(date.fromisoformat(r['eff_dt'])-date.fromisoformat(r['report_dt'])).days
            for r in coverage if r['eff_dt'] is not None]
    sec_dir = ROOT/'research/p421-quarter-20261104-v1'
    manifest = json.loads((sec_dir/'artifact-manifest.json').read_text())
    xml_path = sec_dir/'filings/0001752724-25-043691.xml.gz'
    xml = ET.fromstring(gzip.decompress(checked(xml_path,manifest[xml_path.relative_to(sec_dir).as_posix()])))
    meta_path = sec_dir/'filings/0001752724-25-043691.json'
    meta = json.loads(checked(meta_path,manifest[meta_path.relative_to(sec_dir).as_posix()]))
    day = p['detail_case']['report_dt']
    ports = candidates(names,maps,'MDY',day)
    if len(ports)!=1 or xml.findtext('.//{*}repPdDate')!=day or meta['as_of']!=day:
        raise ValueError('Snapshot identity/date mismatch')
    if any(int(r['crsp_portno'])!=ports[0] or r['report_dt']!=day for r in holdings):
        raise ValueError('Unplanned detailed holdings')
    sec_rows = xml.findall('.//{*}invstOrSec')
    sg,cg = defaultdict(list),defaultdict(list)
    no_identifier = []
    for i,node in enumerate(sec_rows):
        key = sec_identifier(node)
        if key is None:
            no_identifier.append(dict(line=i+1,name=node.findtext('{*}name')))
        else:
            sg[key].append((i+1,node))
    for r in holdings:
        if isinstance(r['cusip'],str) and len(r['cusip'])==8 and r['cusip']!='00000000':
            cg[r['cusip']].append(r)
    pairs = []
    matched_crsp = set()
    for key, filed in sg.items():
        if len(filed)!=1 or len(cg[key])!=1:
            continue
        line,node = filed[0]
        source = cg[key][0]
        if node.findtext('{*}curCd')!='USD' or node.findtext('{*}units')!='NS':
            continue
        shares, value = Decimal(node.findtext('{*}balance')),Decimal(node.findtext('{*}valUSD'))
        if source['nbr_shares'] is None or source['market_val'] is None:
            continue
        pairs.append(dict(cusip8=key,sec_line=line,sec_name=node.findtext('{*}name'),
            share_difference=str(Decimal(str(source['nbr_shares']))-shares),
            value_difference=str(Decimal(str(source['market_val']))-value),
            sec_shares=str(shares),sec_value=str(value),crsp=source))
        matched_crsp.add(key)
    detail = dict(by_fund=by_fund,coverage=coverage,mdy_pairs=pairs,
        sec_without_cusip_bridge=no_identifier,
        unmatched_crsp=[r for r in holdings if r['cusip'] not in matched_crsp])
    detail_path = root/'coverage-and-snapshot-comparison.json'
    save(detail_path,detail)
    differences = [abs(Decimal(r['value_difference'])) for r in pairs]
    result = dict(status='bounded_coverage_and_snapshot_check_complete',protocol_sha256=PROTOCOL_HASH,
        audit_plan_sha256=AUDIT_HASH,source_archive=str(root),source_manifest_sha256=capture['manifest_sha256'],
        requested_funds=len(p['funds']),discovered_funds=len({n['ticker'] for n in names}),
        fund_name_rows=len(names),portfolio_mapping_rows=len(maps),coverage_rows=len(coverage),
        distinct_portfolio_report_dates=len({(r['crsp_portno'],r['report_dt']) for r in coverage}),
        first_report=min(r['report_dt'] for r in coverage),last_report=max(r['report_dt'] for r in coverage),
        receipt_lag_days=dict(min=min(lags),median=statistics.median(lags),max=max(lags)),
        missing_receipt_dates=sum(r['eff_dt'] is None for r in coverage),receipt_before_report=sum(v<0 for v in lags),
        groups_with_tied_ranks=sum(r['rows']!=r['distinct_ranks'] for r in coverage),
        rank_note='Ties in rank are not proof of duplicate holding records.',by_fund=by_fund,
        mdy=dict(report_date=day,crsp_rows=len(holdings),sec_rows=len(sec_rows),
            identifier_matched_pairs=len(pairs),exact_share_pairs=sum(Decimal(r['share_difference'])==0 for r in pairs),
            exact_value_pairs=sum(v==0 for v in differences),max_absolute_value_difference=str(max(differences)) if differences else None,
            sec_without_identifier_bridge=len(no_identifier),crsp_unmatched_rows=len(detail['unmatched_crsp']),
            crsp_receipt_dates=sorted({r['eff_dt'] for r in holdings}),sec_filed_date=meta['filed'],
            sec_accepted_new_york=meta['accepted_new_york'],weights_normalized=False),
        details=dict(path=str(detail_path),sha256=sha(detail_path.read_bytes())),
        active_catalog_publications=0,strategy_eligible_snapshots=0,strategy_replays=0,
        historical_available_at=None,
        limitations=['Fund tickers discover dated vendor candidates, not independently certified identities.',
            'Effective date is vendor receipt, not proven end-user dissemination or unmodified vintage availability.',
            'One snapshot comparison does not qualify the full history; tied ranks require record-level inspection.',
            'No renormalization, silent bridge for non-US ISINs, source splice, or portfolio calculation.'],
        runner_sha256=sha(Path(__file__).read_bytes()))
    save(STUDY/'assessment.json',result)
    print(json.dumps({k:result[k] for k in ('requested_funds','discovered_funds','coverage_rows',
        'distinct_portfolio_report_dates','first_report','last_report','receipt_lag_days','mdy')}),flush=True)


if __name__ == '__main__':
    audit()
