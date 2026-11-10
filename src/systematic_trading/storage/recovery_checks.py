"""Compact recovery evidence; no broker or production restore operations."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

from psycopg import sql

from systematic_trading.storage.nas_sync import file_hash, write_json


def recovery_policy_hash(config):
    policy = {key: config.get(key) for key in ('scope', 'required_paths', 'input_manifests', 'exclude')}
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()


def validate_recovery_coverage(manifest, config, workspace):
    if manifest.get('excludes') != config.get('exclude'):
        raise ValueError('Recovery exclusions changed since capture')
    sources = [Path(p).resolve() for p in manifest['sources']]
    for name in [*config['required_paths'], *config.get('input_manifests', [])]:
        required = (workspace/name).resolve()
        if not any(required == p or required.is_relative_to(p) for p in sources):
            raise ValueError('Required recovery root was not captured: '+name)


def database_checks(connection):
    connection.execute("SET LOCAL timezone='UTC'")
    tables = connection.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT LIKE 'pg_%' "
                                "AND schemaname <> 'information_schema' ORDER BY 1,2").fetchall()
    counts = {schema + '.' + table: connection.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(
        sql.Identifier(schema), sql.Identifier(table))).fetchone()[0] for schema, table in tables}
    control = connection.execute('SELECT row_to_json(s)::text FROM portfolio.strategy_control_state s ORDER BY 1').fetchall()
    roles = [r[0] for r in connection.execute("SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%' ORDER BY 1")]
    return dict(table_counts=counts, controls=[json.loads(r[0]) for r in control], roles=roles)


def capture_code(workspace, capture):
    """Git supplies the base; preserve only the small uncommitted source delta."""
    allowed = ['src', 'scripts', 'tests', 'config', 'docs', 'AGENTS.md', 'README.md', 'log.md', 'pyproject.toml']

    def git(*args):
        return subprocess.run(['git', *args], cwd=workspace, check=True, capture_output=True,
                              timeout=60).stdout

    commit = git('rev-parse', 'HEAD').decode().strip()
    patch = capture / 'working-tree.patch'
    patch.write_bytes(git('diff', '--binary', 'HEAD', '--', *allowed))
    saved = {}
    for name in git('ls-files', '--others', '--exclude-standard', '-z', '--', *allowed).decode().split('\0'):
        if not name:
            continue
        path = Path(name)
        if path.suffix.lower() not in {'.py', '.ps1', '.md', '.json', '.toml', '.js', '.html', '.css'}:
            continue
        if any(word in name.lower() for word in ('secret', 'credential', 'private', 'token', '_key')):
            continue
        source = workspace / path
        if source.is_symlink() or source.stat().st_size > 10 * 1024**2:
            raise ValueError('Review uncommitted recovery source: ' + name)
        target = capture / 'uncommitted-source' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        saved[name] = file_hash(target)
    write_json(capture / 'code-recovery.json', dict(git_commit=commit, patch_sha256=file_hash(patch),
        uncommitted_files=saved, instructions='Clone the Git repository, checkout git_commit, apply working-tree.patch, '
        'then copy uncommitted-source over the checkout. Reprovision secrets separately.'))
