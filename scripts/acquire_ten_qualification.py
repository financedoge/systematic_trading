"""Capture SEC identity evidence and public Nasdaq capability receipts for ten holdings."""
import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from systematic_trading.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/p421-ten-qualification-20261106-v1'
CACHE = ROOT/'var/research/p421-ten-qualification-20261106-v1'
PRIOR = ROOT/'research/p421-mdy-inventory-20261105-v1'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def save(p, data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(key,url):
    data_path=CACHE/(key+'.gz')
    receipt_path=CACHE/(key+'.receipt.json')
    if data_path.exists() and receipt_path.exists():
        raw=gzip.decompress(data_path.read_bytes())
        receipt=read(receipt_path)
        if sha(raw)!=receipt['sha256'] or receipt['url']!=url:
            raise ValueError('Changed source '+key)
        return raw,receipt
    for attempt in range(3):
        try:
            response=requests.get(url,headers={'User-Agent':AppSettings().sec_user_agent},timeout=(12,35))
            response.raise_for_status()
            raw=response.content
            break
        except requests.RequestException:
            if attempt==2:raise
            time.sleep(attempt+1)
    receipt=dict(url=url,sha256=sha(raw),bytes=len(raw),retrieved_at=datetime.now(timezone.utc).isoformat())
    data_path.parent.mkdir(parents=True,exist_ok=True)
    data_path.write_bytes(gzip.compress(raw,mtime=0))
    save(receipt_path,receipt)
    return raw,receipt


def array_records(data):
    n=len(data.get('accessionNumber',[]))
    return [{k:v[i] for k,v in data.items() if isinstance(v,list) and len(v)==n} for i in range(n)]


def acquire():
    manifest=read(PRIOR/'artifact-manifest.json')
    for name in ('inventory.json','acceptance.json'):
        if sha((PRIOR/name).read_bytes())!=manifest[name]:
            raise ValueError('Changed inventory '+name)
    symbols=read(PRIOR/'acceptance.json')['next_pilot_symbols']
    OUT.mkdir(parents=True,exist_ok=True)
    raw,registry_receipt=capture('sec-tickers','https://www.sec.gov/files/company_tickers.json')
    registry={r['ticker']:r for r in json.loads(raw).values()}
    save(OUT/'protocol.json',dict(symbols=symbols,window=['2024-02-27','2025-02-28'],
          decision='2025-03-03',prior_manifest_sha256=sha((PRIOR/'artifact-manifest.json').read_bytes()),
          scope='Qualification and reconciliation only. Source checks cannot replace full-window independent price/volume verification or dated security continuity.',
          registry=registry_receipt))
    failures=[]
    for symbol in symbols:
        cik=registry[symbol]['cik_str']
        try:
            raw,submeta=capture('submissions-'+symbol,f'https://data.sec.gov/submissions/CIK{cik:010d}.json')
            sub=json.loads(raw)
            records=array_records(sub['filings']['recent'])
            for archive in sub['filings']['files']:
                if archive['filingFrom']<='2025-02-27' and archive['filingTo']>='2022-01-01':
                    data,_=capture('submissions-'+symbol+'-'+archive['name'],'https://data.sec.gov/submissions/'+archive['name'])
                    records.extend(array_records(json.loads(data)))
            chosen={}
            for cutoff in ('2024-02-27','2025-02-27'):
                eligible=[r for r in records if r['form'] in ('10-K','10-Q') and r['filingDate']<=cutoff]
                if not eligible:raise ValueError('No periodic identity filing '+symbol)
                chosen[cutoff]=max(eligible,key=lambda r:r['filingDate'])
            covers=[]
            for r in {v['accessionNumber']:v for v in chosen.values()}.values():
                acc=r['accessionNumber']
                raw,meta=capture(acc,f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace("-","")}/{r["primaryDocument"]}')
                soup=BeautifulSoup(raw,'html.parser')
                fields={}
                for e in soup.find_all(lambda e:e.has_attr('name') and e['name'].startswith('dei:')):
                    name=e['name'].split(':')[-1]
                    if name in ['EntityRegistrantName','EntityCentralIndexKey','TradingSymbol','Security12bTitle','SecurityExchangeName','DocumentPeriodEndDate','DocumentType']:
                        fields.setdefault(name,[])
                        val=e.get_text(' ',strip=True)
                        if val not in fields[name]:fields[name].append(val)
                tables=[t.get_text(' ',strip=True) for t in soup.find_all('table') if 'Trading Symbol' in t.get_text(' ',strip=True)][:2]
                covers.append(dict(accession=acc,filing_date=r['filingDate'],report_date=r['reportDate'],source=meta,
                                   fields=fields,listing_tables=tables))
            save(OUT/'issuers'/(symbol+'.json'),dict(symbol=symbol,cik=cik,submissions=submeta,
                requested_cutoffs={k:v['accessionNumber'] for k,v in chosen.items()},filings=covers))
            print(symbol,len(covers),'filings',flush=True)
        except Exception as e:
            failures.append(dict(symbol=symbol,error_type=type(e).__name__,error=str(e)))
            print(symbol,type(e).__name__,flush=True)
    probes=[]
    for symbol,start,end in [('CSL','2024-02-27','2025-02-28'),('MANH','2024-02-27','2025-02-28'),('CSL','2026-11-02','2026-11-04')]:
        url=f'https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass=stocks&fromdate={start}&todate={end}&limit=300'
        try:
            raw,receipt=capture('nasdaq-'+symbol+'-'+start,url)
            payload=json.loads(raw)
            probes.append(dict(symbol=symbol,start=start,end=end,receipt=receipt,total_records=(payload.get('data') or {}).get('totalRecords')))
        except Exception as e:probes.append(dict(symbol=symbol,error_type=type(e).__name__,error=str(e)))
    save(OUT/'acquisition.json',dict(failures=failures,nasdaq=probes))
    print('finished',len(failures),'issuer failures',flush=True)


if __name__=='__main__':
    acquire()
