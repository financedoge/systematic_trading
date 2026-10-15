"""Immutable, account-bound admission for US-listed, whole-share USD ETFs.

The registry establishes a routing capability, never an allocation or approval.
Legacy twelve-member allocations can migrate without changing their recipes.
"""
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import digest, encode


SCHEMA = 'paper-us-etf-contracts-v1'
VENUES = {'ARCA', 'NASDAQ', 'ISLAND', 'NYSE', 'BATS'}
CAPABILITIES = {'financial_rank_selection', 'audited_etf_activity', 'rolling_model',
                'usd_ridge', 'economic_ridge', 'final_weight_cap', 'relative_momentum',
                'adaptive_trend', 'sleeve_capped_momentum', 'etf_activity',
                'technical_tree_allocator', 'decision_tree', 'asset_pool_filter',
                'time_series_momentum', 'trend_quality_filter', 'commodity_guard',
                'basket_risk_control', 'country_factor'}


def _validate_entry(symbol, entry):
    from systematic_trading.research.ib_admission import validate_contract
    fund, evidence = entry['fund'], entry['identity']
    if fund['symbol'] != symbol or entry['instrument']['symbol'] != symbol:
        raise ValueError('Registry symbol mismatch: ' + symbol)
    checked = validate_contract(fund, [evidence['details']])
    if evidence['status'] != 'identity_verified' or checked['lookup'] != evidence['lookup']:
        raise ValueError('Unverified identity: ' + symbol)
    details, contract = evidence['details'], evidence['details']['contract']
    if (contract['currency'] != 'USD' or contract['primaryExchange'] not in VENUES
            or entry['instrument']['quote_currency'] != 'USD'
            or entry['instrument']['asset_class'] != 'etf'):
        raise ValueError('Unsupported execution market: ' + symbol)
    for field in ('minSize', 'sizeIncrement'):
        increment = Decimal(details[field])
        if (not increment.is_finite() or not 0 < increment <= 1
                or field == 'sizeIncrement' and Decimal(1) % increment):
            raise ValueError('Unsupported whole-share rule: ' + symbol)
    tick = Decimal(details['minTick'])
    if not tick.is_finite() or tick <= 0 or Decimal('.01') % tick:
        raise ValueError('Unsupported price increment: ' + symbol)
    if not {'LMT', 'MKT'} <= set(details['orderTypes'].split(',')):
        raise ValueError('Required order types unavailable: ' + symbol)
    if (details.get('timeZoneId') not in {'US/Eastern','America/New_York','EST5EDT'}
            or details.get('stockType') != 'ETF'):
        raise ValueError('Unverified US ETF market hours/type: ' + symbol)
    if entry['calendar'] != 'XNYS' or entry['lot_size'] != 1:
        raise ValueError('Unsupported calendar/lot: ' + symbol)
    if not entry['price_inputs'].get('batch') or not entry['price_inputs'].get('files'):
        raise ValueError('Audited price evidence required: ' + symbol)
    permission = entry['permission']
    captured = datetime.fromisoformat(permission['captured_at'])
    if not datetime.now(UTC) - timedelta(days=30) <= captured <= datetime.now(UTC):
        raise ValueError('Paper preview is stale or future-dated: ' + symbol)
    if permission.get('kind') != 'ib_paper_what_if' or permission.get('what_if') is not True:
        raise ValueError('Paper broker preview evidence required: ' + symbol)
    if permission.get('con_id') != contract['conId'] or permission.get('errors'):
        raise ValueError('Broker preview rejected or identity changed: ' + symbol)
    state = permission['state']
    if state.get('status') not in {'PreSubmitted', 'Submitted'} or state.get('warningText'):
        raise ValueError('Broker preview requires review: ' + symbol)
    for field in ('initMarginAfter', 'maintMarginAfter'):
        value = Decimal(state[field])
        if not value.is_finite() or abs(value) >= Decimal('1e100'):
            raise ValueError('Incomplete broker preview: ' + symbol)


def publish_registry(settings, entries, *, account, reason):
    """Publish a complete reviewed snapshot; omissions/revocations fail closed."""
    if not account.startswith('DU') or not reason.strip() or not entries:
        raise ValueError('Paper account, reason and entries are required')
    for symbol, entry in entries.items():
        _validate_entry(symbol, entry)
        if entry['permission']['account'] != account:
            raise ValueError('Permission belongs to a different paper account')
    contract_ids = [e['identity']['details']['contract']['conId'] for e in entries.values()]
    if len(set(contract_ids)) != len(contract_ids):
        raise ValueError('Duplicate broker identity in execution registry')
    root = settings.data_dir / 'execution_registry'
    root.mkdir(parents=True, exist_ok=True)
    pointer = root / 'current.json'
    parent = json.loads(pointer.read_text())['version'] if pointer.exists() else None
    now = datetime.now(UTC)
    expires = min(datetime.fromisoformat(e['permission']['captured_at']) for e in entries.values()) + timedelta(days=30)
    document = dict(schema=SCHEMA, environment='paper', account=account,
        captured_at=now.isoformat(), valid_until=expires.isoformat(),
        parent=parent, reason=reason, entries=entries,
        limitation='Broker what-if is a current credit/permission preview, not a fill or future permission guarantee. USD/CNH FX remains separately validated and is not historically audited.')
    data = encode(document)
    version = digest(data)
    target = root / (version + '.json')
    if not target.exists():
        target.write_text(data, encoding='utf8')
    if sha256(target) != version:
        raise ValueError('Existing immutable registry differs')
    temporary = root / ('current-' + version + '.tmp')
    temporary.write_text(encode(dict(version=version)), encoding='utf8')
    temporary.replace(pointer)
    return version


class ExecutionRegistry:
    def __init__(self, settings):
        root = settings.data_dir / 'execution_registry'
        self.version = json.loads((root / 'current.json').read_text(encoding='utf8'))['version']
        if not re.fullmatch('[0-9a-f]{64}', self.version):
            raise ValueError('Invalid execution registry version')
        path = root / (self.version + '.json')
        if sha256(path) != self.version:
            raise ValueError('Execution registry hash mismatch')
        self.document = json.loads(path.read_text(encoding='utf8'))
        if self.document['schema'] != SCHEMA or self.document['environment'] != 'paper':
            raise ValueError('Unsupported execution registry')
        if not self.document['account'].startswith('DU'):
            raise ValueError('Execution registry is not bound to a paper account')
        if datetime.fromisoformat(self.document['valid_until']) <= datetime.now(UTC):
            raise ValueError('Execution contract evidence expired; refresh broker previews')

    def resolve(self, instruments, *, account=None):
        if account is not None and self.document['account'] != account:
            raise ValueError('Execution admission belongs to a different account')
        resolved = {}
        for symbol, instrument in instruments.items():
            entry = self.document['entries'].get(symbol)
            if not entry or entry.get('state') != 'admitted':
                raise ValueError('No execution admission: ' + symbol)
            _validate_entry(symbol, entry)
            if entry['permission']['account'] != self.document['account']:
                raise ValueError('Registry permission account mismatch')
            if entry['instrument'] != instrument.model_dump(mode='json'):
                raise ValueError('Strategy/registry instrument disagreement: ' + symbol)
            resolved[symbol] = entry['identity']['details']['contract']
        return resolved

    def receipt(self, instruments):
        contracts = self.resolve(instruments)
        return dict(version=self.version, account=self.document['account'],
            contracts={s:c['conId'] for s,c in contracts.items()})


def registry_required(instruments):
    from systematic_trading.research.etf_universe import MULTI_ASSET_ETF_UNIVERSE
    return any(MULTI_ASSET_ETF_UNIVERSE.get(s) != i for s,i in instruments.items())


def proposal_registry(settings, instruments):
    pointer = settings.data_dir / 'execution_registry/current.json'
    if pointer.exists() or registry_required(instruments):
        return ExecutionRegistry(settings)
    return None
