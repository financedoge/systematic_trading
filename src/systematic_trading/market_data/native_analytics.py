"""Native analytical publications backed by PostgreSQL and immutable Parquet."""
from datetime import UTC, datetime
import json

from psycopg.types.json import Jsonb

from systematic_trading.market_data.analytics_store import digest, encode, timestamp
from systematic_trading.storage.parquet_lake import ParquetLake


class NativeAnalyticsStore:
    storage_name = 'postgres-parquet-duckdb'

    def __init__(self, lake):
        self.lake = lake
        self.catalog = lake.catalog
        self.workspace = self.catalog.workspace

    @classmethod
    def from_settings(cls, settings):
        return cls(ParquetLake.from_settings(settings))

    def initialize(self):
        self.lake.initialize()

    @staticmethod
    def _publication(row):
        if row and isinstance(row['published_at'], datetime):
            row = dict(row, published_at=row['published_at'].astimezone(UTC).isoformat())
        return row

    def publication(self, source_id, version=None, *, connection=None):
        def read(c):
            if version is None:
                return self._publication(c.execute('SELECT p.*,h.activated_at AS published_at '
                    'FROM native_analytics.publication_heads h JOIN native_analytics.publications p '
                    'USING(workspace,source_id,version) WHERE h.workspace=%s AND h.source_id=%s',
                    (self.workspace,source_id)).fetchone())
            where = 'workspace=%s AND source_id=%s'
            params = [self.workspace,source_id]
            if version is not None:
                where += ' AND version=%s'; params.append(version)
            return self._publication(c.execute('SELECT * FROM native_analytics.publications WHERE '+where+
                ' ORDER BY published_at DESC,version DESC LIMIT 1',params).fetchone())
        if connection is not None:
            return read(connection)
        with self.catalog.connect() as c:
            return read(c)

    def latest(self, source_id):
        return self.publication(source_id)

    def publications(self, source_id):
        with self.catalog.connect() as c:
            return [self._publication(r) for r in c.execute('SELECT * FROM native_analytics.publications '
                'WHERE workspace=%s AND source_id=%s ORDER BY published_at DESC,version DESC',(self.workspace,source_id))]

    def publication_index(self, prefix):
        with self.catalog.connect() as c:
            rows = c.execute('SELECT p.*,h.activated_at AS published_at FROM native_analytics.publication_heads h '
                'JOIN native_analytics.publications p USING(workspace,source_id,version) '
                'WHERE h.workspace=%s AND starts_with(h.source_id,%s) ORDER BY h.source_id',
                (self.workspace,prefix)).fetchall()
        return {r['source_id']:self._publication(r) for r in rows}

    def _manifest(self, publication, table):
        ref = publication['datasets'].get(table)
        manifest = self.lake.manifest(ref['key'], ref['revision']) if ref else None
        if ref and (manifest is None or digest(encode(manifest))!=ref['manifest_sha256']):
            raise ValueError('Missing or changed native publication manifest')
        return dict(manifest,selection=(publication['source_id'],publication['version'])) if manifest else None

    def _manifests(self, publications, table):
        publications=list(publications)
        identities=sorted({(p['datasets'][table]['key'],p['datasets'][table]['revision'])
            for p in publications if p['datasets'].get(table)})
        if not identities:return []
        with self.catalog.connect() as c:
            records=c.execute('SELECT dataset_key,revision,manifest,manifest_sha256 FROM native_analytics.datasets '
                'WHERE workspace=%s AND (dataset_key,revision) IN (SELECT unnest(%s::text[]),unnest(%s::text[]))',
                (self.workspace,[k for k,v in identities],[v for k,v in identities])).fetchall()
        indexed={(r['dataset_key'],r['revision']):r for r in records}
        result=[]
        for p in publications:
            ref=p['datasets'].get(table)
            if not ref:continue
            row=indexed.get((ref['key'],ref['revision']))
            if row is None or digest(encode(row['manifest']))!=row['manifest_sha256'] or row['manifest_sha256']!=ref['manifest_sha256']:
                raise ValueError('Missing or changed native publication manifest')
            result.append(dict(row['manifest'],selection=(p['source_id'],p['version'])))
        return result

    def pinned_rows(self, table, source_id, version, *, family=None, entity=None, key=None, limit=None, order=()):
        if table not in ('observations','documents'):
            raise ValueError('Unknown publication table')
        publication = self.publication(source_id,version)
        if publication is None:
            return []
        filters = [(name,'=',value) for name,value in [('family',family),('entity',entity),('point_key',key)] if value is not None]
        return self.lake.select([self._manifest(publication,table)],filters=filters,order=order,limit=limit)

    def document(self, source_id, key):
        publication = self.latest(source_id)
        if publication is None:
            return None
        rows = self.lake.select([self._manifest(publication,'documents')],filters=[('point_key','=',key)],limit=1)
        return (dict(payload=rows[0]['payload'],media_type=rows[0]['media_type']),publication) if rows else None

    @staticmethod
    def _ordered(rows, family, limit):
        # Stable point identity is the last tie break; latest snapshot creation
        # wins when several account captures share an observed date.
        rows.sort(key=lambda r:r['point_key'])
        if family == 'pnl_snapshot':
            rows.sort(key=lambda r:timestamp(json.loads(r['payload']).get('created_at')) or '',reverse=True)
        rows.sort(key=lambda r:timestamp(r.get('observed_at')) or '',reverse=True)
        return rows[:limit]

    def observations(self, source_id, *, family=None, limit=1000):
        publication = self.latest(source_id)
        if publication is None:
            return []
        filters = [('family','=',family)] if family is not None else []
        rows = self.lake.select([self._manifest(publication,'observations')],filters=filters,
            order=[('observed_at','DESC'),('point_key','ASC')],limit=None if family=='pnl_snapshot' else limit)
        return self._ordered(rows,family,limit)

    def current_observations(self, prefix, *, family=None, limit=1000000):
        publications = self.publication_index(prefix)
        filters = [('family','=',family)] if family is not None else []
        rows = self.lake.select(self._manifests(publications.values(),'observations'),filters=filters,
            order=[('observed_at','DESC'),('point_key','ASC')],limit=None if family=='pnl_snapshot' else limit)
        return self._ordered(rows,family,limit)

    def publish(self, source_id, version, observations, documents=(), *, provenance=None):
        return self._publish(source_id,version,observations,documents,provenance=encode(provenance or {}))

    def _publish(self, source_id, version, observations, documents=(), *, provenance, published_at=None, legacy_rows=False, expected_counts=None):
        self.initialize()
        with self.catalog.writer('publication/'+source_id) as c:
            if self.publication(source_id,version,connection=c):
                current=self.publication(source_id,connection=c)
                if not legacy_rows and (current or {}).get('version') != version:
                    self._advance(c,source_id,version,datetime.now(UTC))
                    return True
                return False
            now = published_at or datetime.now(UTC).isoformat()
            datasets, counts = {}, {}
            for table, records in [('observations',observations),('documents',documents)]:
                seen = set()
                def rows():
                    for record in records:
                        if record['point_key'] in seen:
                            raise ValueError('Duplicate native analytical point identity')
                        seen.add(record['point_key'])
                        if legacy_rows:
                            if record['workspace'] != self.workspace or record['source_id'] != source_id or record['version'] != version:
                                raise ValueError('Migration row is outside its declared publication')
                            yield record
                        else:
                            yield dict(workspace=self.workspace,source_id=source_id,version=version,ingested_at=now,**record)
                manifest = self.lake.prepare(rows())
                key = table+'/'+source_id+'/'+version
                physical_version = manifest['logical_sha256']
                self.catalog.commit(c,key,physical_version,manifest,advance=False)
                datasets[table] = dict(key=key,revision=physical_version,manifest_sha256=digest(encode(manifest)))
                counts[table] = manifest['row_count']
            if expected_counts is not None and counts != expected_counts:
                raise ValueError('Migrated publication row counts differ from the committed source receipt')
            c.execute('INSERT INTO native_analytics.publications '
                '(workspace,source_id,version,published_at,observation_count,document_count,provenance,datasets) '
                'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(self.workspace,source_id,version,now,
                    counts['observations'],counts['documents'],provenance,Jsonb(datasets)))
            self._advance(c,source_id,version,now)
        return True

    def _advance(self,c,source,version,at):
        c.execute('INSERT INTO native_analytics.publication_heads(workspace,source_id,version,activated_at) VALUES(%s,%s,%s,%s) '
            'ON CONFLICT(workspace,source_id) DO UPDATE SET version=excluded.version,activated_at=excluded.activated_at '
            'WHERE excluded.activated_at>=native_analytics.publication_heads.activated_at',(self.workspace,source,version,at))

    def publish_batch(self, sources):
        changed=False
        for source,version,observations,provenance in sources:
            changed=self.publish(source,version,observations,provenance=provenance) or changed
        return changed

    def publish_migration_batch(self,publications,observations,documents):
        """Pack many small source publications while preserving per-source pins."""
        from collections import Counter
        expected={(p['source_id'],p['version']):p for p in publications}
        self.initialize()
        with self.catalog.writer('migration/'+digest(encode(sorted(expected)))) as c:
            datasets={}
            for table,records in [('observations',observations),('documents',documents)]:
                counts=Counter()
                def rows():
                    previous=None
                    for row in records:
                        key=(row['source_id'],row['version'])
                        identity=(*key,row['point_key'])
                        if row['workspace']!=self.workspace or key not in expected:
                            raise ValueError('Unexpected migrated publication identity')
                        if previous is not None and identity<=previous:
                            raise ValueError('Duplicate or unordered migrated point identity')
                        previous=identity
                        counts[key]+=1
                        yield row
                manifest=self.lake.prepare(rows())
                for key,p in expected.items():
                    field='observation_count' if table=='observations' else 'document_count'
                    if counts[key]!=int(p[field]): raise ValueError('Migrated publication count mismatch: '+str(key))
                revision=manifest['logical_sha256'];key='packed/'+table+'/'+revision
                self.catalog.commit(c,key,revision,manifest,advance=False)
                datasets[table]=dict(key=key,revision=revision,manifest_sha256=digest(encode(manifest)))
            for p in publications:
                c.execute('INSERT INTO native_analytics.publications '
                    '(workspace,source_id,version,published_at,observation_count,document_count,provenance,datasets) '
                    'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(self.workspace,p['source_id'],p['version'],p['published_at'],
                        p['observation_count'],p['document_count'],p['provenance'],Jsonb(datasets)))
                self._advance(c,p['source_id'],p['version'],p['published_at'])

    def market_revision(self):
        with self.catalog.connect() as c:
            rows = c.execute("SELECT dataset_key,revision FROM native_analytics.heads WHERE workspace=%s "
                "AND starts_with(dataset_key,'market/') ORDER BY dataset_key",(self.workspace,)).fetchall()
        return digest(encode(rows))

    def research_query(self, kind, *, dataset=None, family=None, search='', entity='', start=None, end=None, after=None, limit=1000):
        publications = {}
        for prefix in ((dataset+'/',) if dataset else ('sector-research/','constituent-research/')):
            publications.update(self.publication_index(prefix))
        paths,where,params = self.lake.pinned_source(self._manifests(publications.values(),'observations'))
        if not paths:
            return []
        if family is not None: where.append('family=?'); params.append(family)
        if entity: where.append('entity=?'); params.append(entity)
        if search: where.append('contains(lower(entity),lower(?))'); params.append(search)
        if start: where.append('observed_at>=?'); params.append(str(start))
        if end: where.append('observed_at<=?'); params.append(str(end)+'T23:59:59.999999+00:00')
        if after: where.append('(source_id,point_key)>(?,?)'); params.extend(after)
        tail = ' FROM read_parquet(?)' + (' WHERE '+' AND '.join(where) if where else '')
        if kind == 'datasets':
            sql = "SELECT split_part(source_id,'/',1)||'/'||split_part(source_id,'/',2) AS dataset,family," \
                'count(*) AS row_count,count(DISTINCT entity) AS entity_count,min(observed_at) AS first_observation,' \
                'max(observed_at) AS last_observation,count(*) FILTER(WHERE available_at IS NULL) AS unknown_availability'
            return self.lake.query_files(sql+tail+' GROUP BY dataset,family ORDER BY dataset,family',params)
        if kind == 'entities':
            sql = 'SELECT entity,count(*) AS row_count,min(observed_at) AS first_observation,max(observed_at) AS last_observation'
            return self.lake.query_files(sql+tail+' GROUP BY entity ORDER BY entity LIMIT ?',params+[limit])
        if kind != 'rows':
            raise ValueError('Unknown research projection')
        records = self.lake.query_files('SELECT record'+tail+' ORDER BY source_id,point_key LIMIT ?',params+[limit])
        result = []
        for r in records:
            row = json.loads(r['record'])
            result.append({key:row.get(key) for key in ('source_id','version','point_key','entity','observed_at',
                'available_at','ingested_at','payload')})
            result[-1]['payload_sha256'] = digest(row['payload'])
        return result

    def governed_rows(self, table, batch, symbol, *, start=None, end=None, after=None, source_id=None, limit=25000):
        if table not in ('governed_daily','governance_comparisons'):
            raise ValueError('Unknown governed table')
        key = 'governed/'+table+'/'+batch+'/'+symbol
        manifest = self.lake.manifest(key)
        filters = []
        if start: filters.append(('observed_at','>=',str(start)))
        if end: filters.append(('observed_at','<=',str(end)+'T23:59:59.999999+00:00'))
        if after: filters.append(('observed_at','>',str(after)+'T23:59:59.999999+00:00'))
        if source_id is not None: filters.append(('source_id','=',source_id))
        return [dict(workspace=self.workspace,batch=batch,**row) for row in
            self.lake.select([manifest],filters=filters,order=[('observed_at','ASC'),('source_id','ASC')],limit=limit)]

    def governed_counts(self,table,batch):
        if table not in ('governed_daily','governance_comparisons'):raise ValueError('Unknown governed table')
        with self.catalog.connect() as c:
            return c.execute("SELECT coalesce(sum((manifest->>'row_count')::bigint),0)::bigint AS n,"
                "count(*) FILTER(WHERE (manifest->>'row_count')::bigint>0) AS symbols "
                'FROM native_analytics.heads h JOIN native_analytics.datasets d USING(workspace,dataset_key,revision) '
                'WHERE workspace=%s AND starts_with(dataset_key,%s)',(self.workspace,'governed/'+table+'/'+batch+'/')).fetchone()

    def publication_counts(self,prefix,version):
        with self.catalog.connect() as c:
            publications=c.execute('SELECT * FROM native_analytics.publications WHERE workspace=%s AND starts_with(source_id,%s) AND version=%s',
                (self.workspace,prefix,version)).fetchall()
        result={'publications':len(publications)}
        for table in ('observations','documents'):
            paths,conditions,values=self.lake.pinned_source(self._manifests(publications,table))
            result[table]=int(self.lake.query_files('SELECT count(*) n FROM read_parquet(?) WHERE '+' AND '.join(conditions),values)[0]['n']) if paths else 0
        return result

    @staticmethod
    def governed_record(table,row):
        # Batch identity belongs in the committed manifest key. Keeping it out
        # of physical rows lets unchanged histories share immutable fragments.
        record={key:row[key] for key in ('symbol','trade_date','payload','payload_hash')}
        record['point_key']=row['trade_date']
        if table=='governance_comparisons':
            record['source_id']=row['source_id']
            record['point_key']=encode([row['source_id'],row['trade_date']])
        record['observed_at']=row['trade_date']
        return record

    def insert_governed(self, table, batch, symbol, records):
        if table not in ('governed_daily','governance_comparisons'):
            raise ValueError('Unknown governed table')
        rows, seen = [], set()
        for r in records:
            point = encode([r.get('source_id'),r['trade_date']]) if table=='governance_comparisons' else r['trade_date']
            if point in seen:
                raise ValueError('Duplicate governed row identity')
            seen.add(point)
            payload = encode(r)
            rows.append(self.governed_record(table,dict(symbol=symbol,trade_date=r['trade_date'],
                source_id=r.get('source_id'),payload=payload,payload_hash=digest(payload))))
        rows.sort(key=lambda r:r['point_key'])
        key = 'governed/'+table+'/'+batch+'/'+symbol
        with self.catalog.writer(key) as c:
            previous = self.catalog.get(key,connection=c)
            manifest = self.lake.prepare(rows)
            revision = manifest['logical_sha256']
            if previous and previous['revision'] != revision:
                raise ValueError('Published governed symbol/batch is immutable')
            self.catalog.commit(c,key,revision,manifest,expected_head=previous['revision'] if previous else None)
        return len(rows)
