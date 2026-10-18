"""Pinned Windows LEAN replay, isolated independently from the Python oracle."""
import json
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid4

from systematic_trading.lean.contracts import sha256,verify_bundle,write_json
from systematic_trading.lean.windows_worker import run as isolated_run


def seal_run(output, receipt, *, contract):
    """Seal the USD sidecar before the run inventory, avoiding circular hashes."""
    def artifacts():
        return {p.relative_to(output).as_posix():sha256(p) for p in output.rglob('*')
                if p.is_file() and p != output/'run.json'}
    if contract == 'usd':
        payload = artifacts()
        payload.pop('artifact_manifest.json', None)
        write_json(output/'artifact_manifest.json', payload)
    receipt['artifacts'] = artifacts()
    write_json(output/'run.json', receipt)


def runtime(*,require_acceptance=True):
    root=Path(__file__).resolve().parents[3]
    config=json.loads((root/'config/native-runtime.json').read_text(encoding='utf8'))['lean']
    if require_acceptance:
        if not config.get('accepted'):raise ValueError('Native LEAN requires completed runtime acceptance')
        acceptance=Path(config['acceptance'])
        if sha256(acceptance)!=config['acceptance_sha256']:raise ValueError('Native LEAN acceptance receipt changed')
        if json.loads(acceptance.read_text())['runtime_manifest_sha256']!=config['manifest_sha256']:
            raise ValueError('Native LEAN acceptance belongs to a different build')
    manifest=Path(config['manifest'])
    if sha256(manifest)!=config['manifest_sha256']: raise ValueError('Native LEAN runtime manifest changed')
    provenance=json.loads(manifest.read_text(encoding='utf8'))
    for name,checksum in provenance['files'].items():
        if sha256(Path(name))!=checksum:raise ValueError('Native LEAN runtime file changed: '+name)
    return config,provenance


def run_native_bundle(*,bundle,output,image=None,timeout_seconds=900,cpus='2',memory='4g',contract='cnh',validation=False):
    from systematic_trading.lean.runner import lean_config,compare_outputs
    verify=verify_bundle
    algorithm='lean/algorithm.py'
    if contract=='usd':
        from systematic_trading.research.momentum_replay import verify_usd_bundle
        verify=verify_usd_bundle
        algorithm='research/momentum_lean.py'
    elif contract!='cnh':raise ValueError('Unsupported native replay contract')
    verified=verify(bundle)
    config,provenance=runtime(require_acceptance=not validation)
    if output.exists():raise FileExistsError('Run artifacts are immutable: '+str(output))
    bundle=bundle.resolve();output=output.resolve();output.mkdir(parents=True)
    engine=Path(config['engine_root']);python=Path(config['python_root']);dotnet=Path(config['dotnet_root']);data=Path(config['data_root'])
    oracle=output/'oracle';lean=output/'native';oracle.mkdir();lean.mkdir()
    memory_bytes=int(str(memory).lower().removesuffix('g'))*1024**3
    receipt=dict(run_id='st-native-lean-'+uuid4().hex[:12],status='running',bundle=str(bundle),
        manifest_sha256=sha256(bundle/'manifest.json'),promotion_eligible=False,
        engine=dict(runtime='windows-native-lean',source_commit=provenance['source_commit'],
            manifest_sha256=config['manifest_sha256'],patches=provenance['patches']),legacy_image_reference=image,
        resources=dict(cpus=str(cpus),memory=str(memory),numerical_threads=1,engines='sequential'))
    write_json(output/'run.json',receipt)
    native_config=lean_config()
    native_config.update({'algorithm-location':str(bundle/'source/systematic_trading'/algorithm),
        'data-folder':str(data),'results-destination-folder':str(lean),'object-store-root':str(lean/'storage'),
        'composer-dll-directory':str(engine),'python-additional-paths':[str(bundle/'source'),str(engine)]})
    write_json(output/'config.json',native_config)
    started=time.perf_counter()
    try:
        before=time.perf_counter()
        oracle_command=[sys.executable,'-B','-m','systematic_trading.lean.reference',str(bundle),str(oracle/'reference.json')]
        if contract=='usd':
            oracle_command=[sys.executable,'-B','-c',
                'import sys;from pathlib import Path;from systematic_trading.research.momentum_replay import run_usd_reference;'
                'from systematic_trading.lean.contracts import write_json;write_json(Path(sys.argv[2]),run_usd_reference(Path(sys.argv[1])))',
                str(bundle),str(oracle/'reference.json')]
        isolated_run(oracle_command,
            output=oracle,read_roots=[Path(sys.base_prefix),Path(sys.prefix),bundle],
            environment={'PYTHONPATH':str(bundle/'source')},memory_bytes=memory_bytes,cpus=float(cpus),timeout=timeout_seconds)
        receipt['reference_wall_seconds']=time.perf_counter()-before
        shutil.copyfile(oracle/'reference.json',output/'reference.json')
        # The config is immutable input to the engine and sits outside its
        # writable output grant, alongside the separate oracle result.
        configuration=output/'configuration';configuration.mkdir()
        write_json(configuration/'config.json',native_config)
        before=time.perf_counter()
        isolated_run([str(dotnet/'dotnet.exe'),str(engine/'QuantConnect.Lean.Launcher.dll'),'--config',str(configuration/'config.json')],
            output=lean,read_roots=[bundle,engine,data,python,dotnet,configuration],memory_bytes=memory_bytes,cpus=float(cpus),timeout=timeout_seconds,
            environment=dict(DOTNET_ROOT=str(dotnet),PYTHONHOME=str(python),PYTHONNET_PYDLL=str(python/'python311.dll'),
                PYTHONPATH=str(bundle/'source')+';'+str(engine),ST_LEAN_INPUT_ROOT=str(bundle),ST_LEAN_OUTPUT_ROOT=str(lean)))
        receipt['lean_wall_seconds']=time.perf_counter()-before
        for name in ('economic.json','resources.json'):shutil.copyfile(lean/name,output/name)
        shutil.copyfile(lean/'worker.log',output/'lean.log')
        shutil.copyfile(oracle/'worker.log',output/'reference.log')
        actual=json.loads((output/'economic.json').read_text(encoding='utf8'))
        reference=json.loads((output/'reference.json').read_text(encoding='utf8'))
        parity=compare_outputs(reference,actual,verified['spec']);write_json(output/'parity.json',parity)
        if not parity['passed']:raise ValueError('Native LEAN parity failed: '+str(parity['differences'][:5]))
        verify(bundle)
        receipt.update(status='succeeded',economic_sha256=parity['economic_sha256'])
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc),retryable=False)
        raise
    finally:
        receipt['elapsed_seconds']=time.perf_counter()-started
        seal_run(output, receipt, contract=contract)
    return receipt
