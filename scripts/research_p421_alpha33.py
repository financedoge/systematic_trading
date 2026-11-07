"""Bounded constituent Alpha33 pilot; immutable stages, no execution authority."""
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path

from audit_holdings_identity import embedded_cusip, valid_cusip, valid_isin
from research_cash_relative_retest import digest, read, write

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/p421-alpha33-pilot-20261107-v1'
WORK = ROOT/'var/research'/OUT.name
QUARTER = ROOT/'research/p421-quarter-20261104-v1'
START, END = '2025-03-03', '2025-05-30'


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError('Changed input: '+str(path))
    return path


def positions():
    manifest = read(QUARTER/'artifact-manifest.json')
    p = checked(QUARTER/'positions.jsonl.gz', manifest['positions.jsonl.gz'])
    with gzip.open(p, 'rt', encoding='utf8') as stream:
        return [json.loads(line) for line in stream]


def holding_cusip(row):
    direct = row.get('cusip')
    if valid_cusip(direct) and direct != '000000000':
        return direct
    isin = row.get('identifiers', {}).get('isin')
    # Filed identifiers may be serialized as an array of attribute dictionaries.
    if isinstance(isin, dict):
        isin = isin.get('value')
    if valid_isin(isin):
        return embedded_cusip(isin)
    return None


def freeze():
    if (OUT/'protocol.json').exists():
        raise FileExistsError('Protocol already frozen')
    pins = read(ROOT/'research/p421-coverage-20261104-v1/pins.json')
    q = read(QUARTER/'qualification.json')
    manifest = read(QUARTER/'artifact-manifest.json')
    for name, expected in manifest.items():
        checked(QUARTER/name, expected)
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    write(OUT/'protocol.json', dict(
        id=OUT.name, frozen_at=datetime.now(UTC).isoformat(), evaluation=[START, END],
        signal_start='2025-02-28', holdings_date='2024-12-31',
        price_pin=pins['price'], full_candidate_pool=pins['funds'],
        public_funds=sorted(q['funds']), holdings_manifest_sha256=digest(QUARTER/'artifact-manifest.json'),
        hypothesis='Does cross-sectional stock Alpha33 aggregated by publicly disclosed ETF holdings improve a matched ETF-level Alpha33 portfolio?',
        formula='rank(open/close - 1); average percentile rank, ascending, ties average; higher is selected',
        rank_universe='One observation per unique, dated CRSP PERMNO represented in the 16 public portfolios; valid audited open/close that day only. No duplicated stock votes across funds.',
        aggregation='Filed equity-value weighted mean of observed constituent percentile ranks. Keep all positive EC/EP positions in value and position-count coverage denominators; missing data excluded from numerator only. No forward survivor requirement.',
        coverage=dict(min_equity_value=.95, min_equity_names=.70),
        identity='Valid filed CUSIP9 or checksum-validated US/BM/KY/VG ISIN embedding; exactly one dated CIZ identity on holdings date and signal date. Existing provider ticker must match dated CIZ ticker/tradingsymbol (dot/dash punctuation only); ambiguous or missing stays unsupported.',
        price_audit='Separate field/date-qualified projection of the pinned continuous history. Both raw open and raw close must agree with independently retained CRSP trade prices within the inherited 0.5% relative price tolerance. Require positive finite prices, trade close flag TR, matching dated CUSIP and consistent adjusted/raw open-close factor within 1e-6 relative. All failures missing. No volume used in stock signal. Original full-series audits unchanged.',
        models=['constituent33', 'etf33', 'momentum126', 'unranked'],
        construction='Same daily supported and liquid ETF subset for all four models. Existing top-six, 63-return sample inverse-volatility, 98% budget, 45% cap, alphabetical ties, fewer than six valid scores or all ranked scores equal => cash. Unranked holds all eligible with the same inverse-volatility rule. 126-session momentum has no sign gate. No training/fitting or parameter optimization.',
        policies=['monthly', 'daily', '0.40'], primary_policy='monthly',
        timing='Completed close signal, next-open execution; monthly first session. Target threshold strict L1 >0.40 versus last adopted target including cash plus monthly reset. Daily is fixed-interval control. Extra-delay case executes one more session later. Use prior execution close for whole adjusted-unit sizing.',
        costs_bps=[5, 10, 20], delays=[0, 1], primary=dict(cost_bps=5, delay=0),
        controls=['initial covered-pool equal-weight buy-and-hold', 'full supported risky-pool equal-weight buy-and-hold', 'BIL', 'URTH', 'cash', 'frozen empirical FR25 original-14 decisions repriced on this batch'],
        chronology=['2025-03', '2025-04', '2025-05'],
        weakest='Lowest net cumulative contribution / opening portfolio NAV among risky ETFs held by the predeclared constituent33/monthly 5bp delay0 policy; report full window and each month. Contribution criterion reflects allocation changes; also show individual buy-and-hold returns. Chart adjusted prices, audited raw volume, theoretical/adopted/held weights, exact fills, no-protection state and FIFO trade outcomes.',
        selection='None. This is a fixed-policy feasibility/development experiment. No OOS optimization, sign flipping, coverage relaxation, policy rescue or promotion. Monthly remains primary regardless of daily/event returns.',
        limitations=['Only one public holdings quarter; portfolios deliberately frozen, not contemporaneous actual holdings after December 2024.',
            'Full 52-candidate scope screened, but holdings-signal allocation only where public dated holdings and daily coverage qualify; not a full-pool superiority claim.',
            'Current-vintage revised prices and CRSP identities; original historical dissemination is unknown. Public SEC filing availability is evidenced separately. Reused history is not pristine out of sample.',
            'Three months cannot establish Sharpe stability or an investment edge. Annualized metrics are descriptive only; inspect monthly results and winner dependence.',
            'Synthetic whole adjusted units, zero cash interest, no taxes/spread/impact; stated per-notional costs and delay sensitivity only. No stops or protective exits.'],
        reuse_reviews=[dict(asset='prices-adjusted-v1', sha256='95820f8d59b4b1a0dde448f7d99f1956d29a1a2fe1cd91144b4a28516ab6b17c', decision='Reuse governed ETF histories and separately qualify consumed stock fields; no existing asset mutation'),
            dict(asset='activity-raw-v1', sha256='29c24b0ad948a89d39d1c280a05f4da684b15a412f609d9744dee8b48862b4e8', decision='Reuse ETF liquidity and inspection context only; no constituent volume input'),
            dict(search='holdings / identity', matches=[], decision='New isolated research-only dated holdings/identity projection; not registered for recurring monitoring or execution')],
        limits=dict(identity_rows=20000, daily_rows=200000),
        code_at_freeze={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in [Path(__file__), ROOT/'scripts/audit_holdings_identity.py', ROOT/'scripts/setup_wrds_access.py']}
    ))
    print('Protocol frozen', digest(OUT/'protocol.json'), 'funds', len(q['funds']), flush=True)


def protocol():
    p = read(OUT/'protocol.json')
    checked(QUARTER/'artifact-manifest.json', p['holdings_manifest_sha256'])
    for name, h in p['code_at_freeze'].items():
        checked(ROOT/name, h)
    return p


if __name__ == '__main__':
    freeze()
