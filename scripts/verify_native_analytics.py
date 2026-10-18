"""Compare retained publications and served strategies across the migration boundary."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.native_analytics import NativeAnalyticsStore
from systematic_trading.portfolio.strategy_allocation import control_state
from systematic_trading.research.strategy_lifecycle import membership
from systematic_trading.storage.factory import create_trading_store
from systematic_trading.storage.postgres import PostgresStore
from systematic_trading.web.api import strategy_detail, strategy_report


def verify(settings,manifest,output):
    plan=json.loads(manifest.read_text())
    completed=json.loads(manifest.with_suffix('.completed.json').read_text())
    if completed['plan_sha256']!=plan['sha256']:
        raise ValueError('Export completion does not match the selected plan')
    old=AnalyticsStore.from_settings(settings.model_copy(update={'market_data_store_backend':'clickhouse'}))
    new=NativeAnalyticsStore.from_settings(settings)
    selected={(p['source_id'],p['version']):p for p in plan['publications']}
    with new.catalog.connect() as connection:
        migrated={(r['source_id'],r['version']):r for r in connection.execute(
            'SELECT * FROM native_analytics.publications WHERE workspace=%s',(new.workspace,))}
        manifests=connection.execute('SELECT manifest,manifest_sha256 FROM native_analytics.datasets WHERE workspace=%s',
            (new.workspace,)).fetchall()
    for identity,expected in selected.items():
        actual=migrated[identity]
        for key in ('observation_count','document_count'):
            if int(actual[key])!=int(expected[key]):raise ValueError('Publication count mismatch: '+str(identity))
        if actual['provenance']!=expected['provenance']:raise ValueError('Publication provenance mismatch: '+str(identity))
    old_heads=old.publication_index('')
    new_heads=new.publication_index('')
    retained_sources={source for source,_ in selected}
    for source in retained_sources:
        if old_heads[source]['version']!=new_heads.get(source,{}).get('version'):
            raise ValueError('Retained publication head differs: '+source)
    files={}
    fragments={}
    for record in manifests:
        if digest(encode(record['manifest']))!=record['manifest_sha256']:raise ValueError('Native manifest changed')
        for fragment in record['manifest']['fragments']:
            previous=fragments.get(fragment['path'])
            if previous and previous!=fragment['sha256']:raise ValueError('Conflicting fragment hashes')
            fragments[fragment['path']]=fragment['sha256']
    for index,(path,checksum) in enumerate(fragments.items(),1):
        files[new.lake.verify_file(dict(path=path,sha256=checksum))]=checksum
        if index%5000==0:print(encode(dict(verified_fragments=index,total=len(fragments))),flush=True)
    # Exact source document bytes cover target/held weights, NAV, signals,
    # benchmark series and the complete rendered decision-flow reports.
    document_checks=[]
    for source in ('tracked-strategies/calculations','strategy-serving','governance/catalog','governance/fx-usd-cnh'):
        before,after=old.latest(source),new.latest(source)
        if (before or {}).get('version')!=(after or {}).get('version'):
            raise ValueError('Current publication differs: '+source)
        if not before:continue
        for table in ('documents','observations'):
            expected={r['point_key']:r['payload'] for r in old.pinned_rows(table,source,before['version'])}
            actual={r['point_key']:r['payload'] for r in new.pinned_rows(table,source,after['version'])}
            if expected!=actual:raise ValueError('Retained payload differs: '+source+'/'+table)
            document_checks.append(dict(source=source,table=table,rows=len(actual),sha256=digest(encode(actual))))
    store=PostgresStore.from_settings(settings)
    members=membership(settings,store)
    requests=[]
    for backend,analytics in [('clickhouse',old),('parquet',new)]:
        configured=settings.model_copy(update={'market_data_store_backend':backend})
        requests.append(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=configured,
            analytics=analytics,store=create_trading_store(configured)))))
    strategies=[]
    for key in members['monitored']:
        details=[strategy_detail(key,request) for request in requests]
        # Backend label and timestamp serialization intentionally differ; the
        # data version and every strategy value must remain identical.
        for detail in details:detail.pop('analytics',None)
        if encode(details[0])!=encode(details[1]):raise ValueError('Strategy API differs: '+key)
        reports=[strategy_report(key,request) for request in requests]
        # Compare stored report bytes above; shell freshness banners format the
        # same publication timestamp using each backend's serialization.
        if any(report.status_code!=200 for report in reports):raise ValueError('Strategy report unavailable: '+key)
        strategies.append(dict(key=key,detail_sha256=digest(encode(details[1])),report_rendered=True))
    receipt=dict(verified_at=datetime.now(UTC).isoformat(),plan_sha256=plan['sha256'],
        publications=len(selected),verified_fragment_files=len(files),verified_fragment_set_sha256=digest(encode(files)),
        documents=document_checks,strategies=strategies,control=control_state(store),
        limitation='Fresh calculation remains subject to audited-input availability; migration does not waive freshness gates.')
    output.write_text(encode(receipt),encoding='utf8')
    print(encode(dict(verified=True,publications=len(selected),strategies=len(strategies),receipt=str(output))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    verify(AppSettings(),args.manifest,args.output)
