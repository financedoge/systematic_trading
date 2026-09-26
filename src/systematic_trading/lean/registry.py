import json
from pathlib import Path

from psycopg.types.json import Jsonb

from systematic_trading.lean.contracts import sha256, verify_bundle


def register_run(store, output: Path) -> str:
    """Append verified research evidence; never create trading proposals or events."""
    receipt = json.loads((output / 'run.json').read_text(encoding='utf-8'))
    if receipt['status'] != 'succeeded' or receipt.get('promotion_eligible') is not False:
        raise ValueError('Only completed, research-only runs can be registered')
    bundle = Path(receipt['bundle'])
    verify_bundle(bundle)
    if sha256(bundle / 'manifest.json') != receipt['manifest_sha256']:
        raise ValueError('Input manifest changed')
    required = {'parity.json', 'reference.json', 'economic.json', 'config.json', 'lean.log', 'resources.json'}
    if not required <= receipt['artifacts'].keys():
        raise ValueError('Missing required run evidence')
    inventory = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p != output / 'run.json'}
    if inventory != set(receipt['artifacts']):
        raise ValueError('Run artifact inventory changed')
    for name, digest in receipt['artifacts'].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output.resolve()) or not path.is_file() or sha256(path) != digest:
            raise ValueError(f'Output artifact changed: {name}')
    parity = json.loads((output / 'parity.json').read_text(encoding='utf-8'))
    if not parity['passed']:
        raise ValueError('Parity must pass before registration')
    digest = sha256(output / 'run.json')
    with store._connect() as connection:
        connection.execute('''INSERT INTO ops.lean_research_runs
            (run_id, manifest_sha256, receipt_sha256, artifact_path, payload)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (run_id) DO NOTHING''', (receipt['run_id'], receipt['manifest_sha256'], digest,
                                       str(output.resolve()), Jsonb({'receipt': receipt, 'parity': parity})))
        existing = connection.execute('SELECT receipt_sha256 FROM ops.lean_research_runs WHERE run_id=%s', (receipt['run_id'],)).fetchone()
        if existing['receipt_sha256'] != digest:
            raise ValueError('Run ID already records different immutable evidence')
    return receipt['run_id']
