"""Inventory, validate and receipt superseded tracked workspaces; no deletion here."""
import argparse
from hashlib import file_digest, sha256
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psycopg import sql
from psycopg.types.json import Jsonb
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.portfolio.strategy_allocation import control_state
from systematic_trading.research.strategy_lifecycle import membership
from systematic_trading.runtime_io import atomic_json, exclusive_lock
from systematic_trading.storage.artifact_retention import (
    REVISION, canonical, fingerprint, inventory, record_retirement, validate_manifest,
    CLOSED_STUDIES,DISPOSABLE_STUDY_FOLDERS,
)
from systematic_trading.storage.postgres import PostgresStore

PATH_REVISION = re.compile(r"tracked_strategies[\\/]+([0-9a-f]{64})")


def publish_retirement_receipt(settings,path):
    record=json.loads(path.read_text(encoding='utf8'))
    if record['status']!='retired':raise ValueError('Only successful retirements enter the serving registry')
    compact={k:v for k,v in record.items() if k!='inventory'}
    compact['inventory']={k:v for k,v in record['inventory'].items() if k not in ('receipts','compact_findings')}
    compact['receipt_path']=str(path.resolve())
    with path.open('rb') as stream:compact['receipt_sha256']=file_digest(stream,'sha256').hexdigest()
    identifier=fingerprint([record['path'],record['manifest_sha256']])
    with PostgresStore.from_settings(settings)._connect() as connection:
        previous=connection.execute("SELECT receipt_id FROM native_analytics.retirements WHERE payload->>'path'=%s "
            "AND payload->>'manifest_sha256'=%s LIMIT 1",(record['path'],record['manifest_sha256'])).fetchone()
        if previous:return False
        connection.execute('INSERT INTO native_analytics.retirements(receipt_id,payload) VALUES (%s,%s)',
            (identifier,Jsonb(compact)))
    return True


def protection(settings):
    store = PostgresStore.from_settings(settings)
    analytics = AnalyticsStore.from_settings(settings)
    member = membership(settings, store)
    control = control_state(store)
    publications = [dict(version=p['version'],at=p['published_at']) for p in analytics.publications('tracked-strategies/calculations')]
    if len(publications) < 2:
        raise ValueError("Need two verified complete publications before pruning")
    revisions = {row['version'] for row in publications[:2]}
    operational = set()
    with store._connect() as connection:
        columns = connection.execute("SELECT table_schema,table_name,column_name FROM information_schema.columns "
            "WHERE data_type IN ('json','jsonb') AND table_schema IN ('core','events','execution','portfolio')").fetchall()
        for c in columns:
            query = sql.SQL("SELECT DISTINCT (regexp_matches({column}::text,%s,'g'))[1] AS revision FROM {schema}.{table} "
                            "WHERE {column}::text LIKE %s").format(
                column=sql.Identifier(c['column_name']), schema=sql.Identifier(c['table_schema']), table=sql.Identifier(c['table_name']))
            operational.update(row['revision'] for row in connection.execute(query, (PATH_REVISION.pattern, '%tracked_strategies%')))
    revisions.update(operational)
    for version in publications[:2]:
        docs = analytics.pinned_rows('documents','tracked-strategies/calculations',version['version'])
        for d in docs:
            value = json.loads(d['payload'])
            if isinstance(value, dict) and value.get('lifecycle') == 'archived':
                continue
            revisions.update(PATH_REVISION.findall(canonical(value)))
    state_path = settings.data_dir / 'run/strategy-compute.json'
    compute = json.loads(state_path.read_text(encoding='utf8')) if state_path.exists() else {}
    if compute.get('revision'):
        revisions.add(compute['revision'])
    # Active studies may carry code/input paths in their frozen protocols.
    for study in ('cash-relative-momentum-20261017-v1', 'class-volatility-screen-20261016-v1', 'etf-expansion-20261014-v1'):
        for p in (ROOT / 'research' / study).glob('*.json'):
            revisions.update(PATH_REVISION.findall(p.read_text(encoding='utf8')))
    guard = dict(membership_revision=member['revision'], monitored=member['monitored'],
                 control_revision=control['revision'], sota=control['sota_key'],
                 active=control['active'], pending=control.get('pending'),
                 publications=[r['version'] for r in publications[:2]],
                 compute_revision=compute.get('revision'), operational_pins=sorted(operational),
                 protected_revisions=sorted(revisions))
    return guard, publications


def plan(settings, destination):
    guard, publications = protection(settings)
    allowed = (settings.data_dir / 'tracked_strategies').resolve()
    complete = {p['version'] for p in publications}
    protected = [str(allowed / r) for r in guard['protected_revisions']]
    candidates = []
    cutoff = (datetime.now(UTC) - timedelta(days=7)).timestamp()
    for directory in sorted(allowed.iterdir()):
        if not directory.is_dir() or not REVISION.fullmatch(directory.name) or str(directory) in protected:
            continue
        if directory.name not in complete and directory.stat().st_mtime >= cutoff:
            continue
        summary = inventory(allowed, directory)
        candidates.append(dict(path=str(directory), reason='Superseded complete calculation' if directory.name in complete
                               else 'Unused calculation attempt older than seven days', inventory=summary))
    manifest = dict(schema_version=1, created_at=datetime.now(UTC).isoformat(), allowed_root=str(allowed),
                    guard=guard, protected_paths=protected, candidates=candidates)
    manifest['manifest_sha256'] = fingerprint(manifest)
    atomic_json(destination, manifest)
    print(canonical(dict(manifest=str(destination.resolve()), candidates=len(candidates), protected=len(protected),
                         logical_gib=round(sum(c['inventory']['logical_bytes'] for c in candidates)/1024**3, 3),
                         exclusive_content_gib=round(sum(c['inventory']['exclusive_content_bytes'] for c in candidates)/1024**3, 3))))


def closed_protection(settings):
    guard,_=protection(settings)
    root=(settings.data_dir/'research').resolve()
    protected=[]
    evidence={}
    references=[]
    for path in (ROOT/'config').glob('*.json'):
        content=path.read_text(encoding='utf8');references.append(content)
        evidence[str(path.resolve())]=fingerprint(content)
    analytics=AnalyticsStore.from_settings(settings)
    for revision in guard['protected_revisions']:
        publication=analytics.publication('tracked-strategies/calculations',revision)
        if publication:references.append(canonical(publication))
    for name in ('cash-relative-momentum-20261017-v1','class-volatility-screen-20261016-v1','etf-expansion-20261014-v1'):
        protected.append(str(root/name))
        for path in (ROOT/'research'/name).glob('*.json'):
            evidence[str(path.resolve())]=fingerprint(path.read_text(encoding='utf8'))
            references.append(path.read_text(encoding='utf8'))
            for study in CLOSED_STUDIES:
                if study in path.read_text(encoding='utf8'):
                    protected.append(str(root/study))
    for study in CLOSED_STUDIES:
        if any(study in value for value in references):protected.append(str(root/study))
    # Execution and portfolio JSON references pin a whole selected study. Old
    # research registry rows deliberately do not, per the operator's waiver.
    with PostgresStore.from_settings(settings)._connect() as c:
        columns=c.execute("SELECT table_schema,table_name,column_name FROM information_schema.columns "
            "WHERE data_type IN ('json','jsonb') AND table_schema IN ('core','events','execution','portfolio')").fetchall()
        pattern='('+'|'.join(sorted(CLOSED_STUDIES))+')'
        for col in columns:
            query=sql.SQL("SELECT DISTINCT (regexp_matches({column}::text,%s,'g'))[1] AS study FROM {schema}.{table} "
                "WHERE {column}::text LIKE %s").format(column=sql.Identifier(col['column_name']),
                schema=sql.Identifier(col['table_schema']),table=sql.Identifier(col['table_name']))
            protected.extend(str(root/r['study']) for r in c.execute(query,(pattern,'%research%')))
    guard['active_study_protocols']=evidence
    guard['protected_studies']=sorted(set(protected))
    findings_by_study={}
    for study in sorted(CLOSED_STUDIES):
        study_root=root/study
        if str(study_root) in protected:continue
        findings=[p for p in study_root.glob('*.json') if p.name in
            {'report.json','analysis.json','statistics.json','summary.json','grid_summary.json','acceptance.json'}]
        if not (study_root/'protocol.json').is_file() or not findings:continue
        findings_by_study[study]={str(p.resolve()):sha256(p.read_bytes()).hexdigest()
            for p in [study_root/'protocol.json',*findings]}
    guard['retained_study_findings']=findings_by_study
    return guard,root,sorted(set(protected))


def closed_plan(settings,destination):
    guard,root,protected=closed_protection(settings)
    candidates=[]
    for study in sorted(CLOSED_STUDIES):
        if str(root/study) in protected:continue
        # Keep the declared recipe and at least one retained result before
        # considering any generated leaf of a completed study.
        if study not in guard['retained_study_findings']:continue
        for name in sorted(DISPOSABLE_STUDY_FOLDERS):
            directory=root/study/name
            if not directory.is_dir():continue
            summary=inventory(root,directory)
            # Preserve compact final findings that live inside a run directory,
            # alongside the retained top-level protocol/runners/reports.
            compact=[]
            for path in directory.rglob('*.json'):
                if path.name not in {'analysis.json','summary.json','grid_summary.json','acceptance.json','statistics.json','gate.json','replay_validation.json'}:
                    continue
                if path.stat().st_size>5*1024**2:raise ValueError('Review large study summary before retirement: '+str(path))
                raw=path.read_text(encoding='utf8')
                compact.append(dict(path=str(path.relative_to(directory)),payload=json.loads(raw)))
            summary['compact_findings']=compact
            candidates.append(dict(path=str(directory),reason='Completed exploratory study; findings and rerun recipe retained; exact replay waived',inventory=summary))
    manifest=dict(schema_version=1,scope='closed_studies',created_at=datetime.now(UTC).isoformat(),allowed_root=str(root),
        guard=guard,protected_paths=sorted(set(protected)),candidates=candidates)
    manifest['manifest_sha256']=fingerprint(manifest);atomic_json(destination,manifest)
    print(canonical(dict(manifest=str(destination),candidates=len(candidates),protected=sorted(set(protected)),
        exclusive_content_gib=sum(r['inventory']['exclusive_content_bytes'] for r in candidates)/1024**3)))


def operational_references(settings,pattern,marker):
    found=set()
    with PostgresStore.from_settings(settings)._connect() as c:
        columns=c.execute("SELECT table_schema,table_name,column_name FROM information_schema.columns "
            "WHERE data_type IN ('json','jsonb') AND table_schema IN ('core','events','execution','portfolio')").fetchall()
        for col in columns:
            query=sql.SQL("SELECT DISTINCT (regexp_matches({column}::text,%s,'g'))[1] AS ref FROM {schema}.{table} "
                "WHERE {column}::text LIKE %s").format(column=sql.Identifier(col['column_name']),
                schema=sql.Identifier(col['table_schema']),table=sql.Identifier(col['table_name']))
            found.update(r['ref'] for r in c.execute(query,(pattern,'%'+marker+'%')))
    return found


def ancillary_protection(settings,scope):
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.lean.contracts import sha256
    guard,publications=protection(settings)
    analytics=AnalyticsStore.from_settings(settings)
    root=(settings.data_dir/('governance' if scope=='governance' else 'tracked_models')).resolve()
    texts=[];evidence={}
    for folder in [ROOT/'config',*[ROOT/'research'/name for name in
            ('cash-relative-momentum-20261017-v1','class-volatility-screen-20261016-v1','etf-expansion-20261014-v1')]]:
        for path in folder.glob('*.json'):
            text=path.read_text(encoding='utf8');texts.append(text);evidence[str(path)]=fingerprint(text)
    for p in publications[:2]:
        texts.append(canonical(analytics.publication('tracked-strategies/calculations',p['version'])))
        texts.extend(r['payload'] for r in analytics.pinned_rows('documents','tracked-strategies/calculations',p['version'])
            if r.get('media_type')=='application/json')
    # Execution-pinned older calculations can retain their own model or data
    # vintages even when the current calculation has moved to a newer revision.
    for revision in guard['protected_revisions']:
        publication=analytics.publication('tracked-strategies/calculations',revision)
        if publication:
            texts.append(canonical(publication))
    for source_id in ('strategy-serving','strategy-promotion'):
        publication=analytics.latest(source_id)
        if publication:
            texts.append(canonical(publication))
            texts.extend(r['payload'] for r in analytics.pinned_rows('documents',source_id,publication['version'])
                if r.get('media_type')=='application/json')
    if scope=='models':
        pattern=r'tracked_models[\\/]+([a-f0-9]{64})'
        pins=operational_references(settings,pattern,'tracked_models')
        for value in texts:pins.update(re.findall(pattern,value))
        protected={str(root/p) for p in pins}
        guard['protected_models']=sorted(pins)
    else:
        export_path=settings.data_dir/'maintenance/windows-cutover/native-export.json'
        final_export=settings.data_dir/'maintenance/windows-cutover/native-export-final.json'
        protected_export=settings.data_dir/'maintenance/windows-cutover/native-export-final-v2.json'
        if protected_export.exists():final_export=protected_export
        if final_export.exists():export_path=final_export
        export=json.loads(export_path.read_text(encoding='utf8'))
        catalogs={p['version']:p for p in analytics.publications('governance/catalog')}
        batches=set(export['catalogs'])
        batches.update(operational_references(settings,r'([a-f0-9]{64})','batch') & catalogs.keys())
        direct=operational_references(settings,r'governance[\\/]+((?:listed|research)-\d{4}-\d{2}-\d{2}-[a-f0-9]{12})','governance')
        for value in texts:
            batches.update(set(re.findall(r'[a-f0-9]{64}',value)) & catalogs.keys())
            direct.update(re.findall(r'governance[\\/]+((?:listed|research)-\d{4}-\d{2}-\d{2}-[a-f0-9]{12})',value))
        protected={str(root/name) for name in direct}
        for batch in batches:
            if batch not in catalogs:continue
            reader=GovernedInputs(Path(json.loads(catalogs[batch]['provenance'])['root']),batch)
            while reader:
                protected.add(str(reader.root.resolve()));reader=reader.parent
        guard.update(export_plan_sha256=export['sha256'],export_plan_path=str(export_path.resolve()),protected_governance_batches=sorted(batches & catalogs.keys()),
            protected_governance_manifests={p:sha256(Path(p)/'manifest.json') for p in sorted(protected)})
    guard['active_protocols_and_config']=evidence
    return guard,root,sorted(protected)


def ancillary_plan(settings,destination,scope):
    from systematic_trading.lean.contracts import sha256
    guard,root,protected=ancillary_protection(settings,scope)
    known={p['version'] for p in AnalyticsStore.from_settings(settings).publications('governance/catalog')} if scope=='governance' else None
    candidates=[]
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or str(directory) in protected:continue
        if scope=='governance':
            if not re.fullmatch(r'(listed|research)-\d{4}-\d{2}-\d{2}-[a-f0-9]{12}',directory.name):continue
            if not (directory/'manifest.json').exists() or sha256(directory/'manifest.json') not in known:continue
        elif not REVISION.fullmatch(directory.name) or not (directory/'complete.json').exists():continue
        summary=inventory(root,directory,receipt_payload=scope!='governance')
        candidates.append(dict(path=str(directory),reason='Superseded unreferenced '+scope+' projection; canonical active dependencies retained',inventory=summary))
        print(canonical(dict(inventoried=directory.name,files=summary['file_count'])),flush=True)
    manifest=dict(schema_version=1,scope=scope,created_at=datetime.now(UTC).isoformat(),allowed_root=str(root),guard=guard,
        protected_paths=protected,candidates=candidates)
    manifest['manifest_sha256']=fingerprint(manifest);atomic_json(destination,manifest)
    print(canonical(dict(manifest=str(destination),candidates=len(candidates),protected=len(protected),
        logical_gib=sum(r['inventory']['logical_bytes'] for r in candidates)/1024**3,
        exclusive_content_gib=sum(r['inventory']['exclusive_content_bytes'] for r in candidates)/1024**3)),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'verify', 'intent', 'record'])
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--target')
    parser.add_argument('--scope',choices=['tracked','closed_studies','governance','models'],default='tracked')
    args = parser.parse_args()
    settings = AppSettings()
    if args.action == 'plan':
        with exclusive_lock(settings.data_dir / 'run/research-retention.lock'):
            if args.scope in ('governance','models'):ancillary_plan(settings,args.manifest,args.scope)
            else:(closed_plan if args.scope=='closed_studies' else plan)(settings, args.manifest)
        return
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    if manifest.get('manifest_sha256') != fingerprint({k:v for k,v in manifest.items() if k != 'manifest_sha256'}):
        raise ValueError('Retirement manifest changed')
    if args.action == 'verify':
        if manifest.get('scope') in ('governance','models'):
            guard,root,_=ancillary_protection(settings,manifest['scope'])
            if manifest['scope']=='governance':
                completed=Path(guard['export_plan_path']).with_suffix('.completed.json')
                if not completed.exists() or json.loads(completed.read_text())['plan_sha256']!=guard['export_plan_sha256']:
                    raise ValueError('Verified native data export must finish before governance retirement')
            validate_manifest(manifest,guard,root)
        elif manifest.get('scope')=='closed_studies':
            guard,_,_=closed_protection(settings)
            # Retained findings are derived from sealed files; compare the file
            # inventory independently of those copied compact summaries.
            stripped=json.loads(json.dumps(manifest))
            for candidate in stripped['candidates']:candidate['inventory'].pop('compact_findings',None)
            stripped['manifest_sha256']=fingerprint({k:v for k,v in stripped.items() if k!='manifest_sha256'})
            validate_manifest(stripped,guard,settings.data_dir/'research')
        else:
            guard, _ = protection(settings)
            validate_manifest(manifest, guard, settings.data_dir / 'tracked_strategies')
        print(canonical(dict(verified=True, manifest_sha256=manifest['manifest_sha256'])))
    else:
        matches = [r for r in manifest['candidates'] if r['path'] == args.target]
        if len(matches) != 1:
            raise ValueError('Target is not uniquely selected by manifest')
        receipt=record_retirement(settings.data_dir, manifest, matches[0], status='retired' if args.action == 'record' else 'intent')
        if args.action=='record':publish_retirement_receipt(settings,receipt)


if __name__ == '__main__':
    main()
