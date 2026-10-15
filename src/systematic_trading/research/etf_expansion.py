"""Audited pool preparation and causal admission masks for finite comparisons.

Current-cohort historical diagnostics are explicitly retrospective. This module
does not manufacture historical security-master availability or trade authority.
"""
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from systematic_trading.research.candidate_pool import audited_bar
from systematic_trading.research.etf_admission import admission_hold


def load_published_pool(reader, candidates, *, through, start='2012-01-05'):
    """Only a pinned GovernedInputs reader can supply study observations."""
    from systematic_trading.live.trading_calendar import is_us_trading_day
    records, exclusions = {}, {}
    for fund in candidates:
        symbol = fund['symbol']
        try:
            if hold := admission_hold(symbol, fund.get('admission_hold')):
                raise ValueError(hold)
            audit = reader.audit(symbol)
            if audit['status'] != 'audited_with_limitations':
                raise ValueError('Audit status: ' + audit['status'])
            if fund.get('requires_recorder',True) and audit.get('research_recorder',{}).get('isin') != fund['isin']:
                raise ValueError('Current issuer identity not published by the research recorder')
            rows = reader.rows(symbol,start,through)
            if not rows or rows[-1]['trade_date'] != through:
                raise ValueError('Audited history does not reach the frozen cutoff')
            records[symbol] = rows
        except (OSError,ValueError,KeyError) as exc:
            exclusions[symbol] = str(exc)
    if not records:
        raise ValueError('No admitted published histories')
    common_start = max(rows[0]['trade_date'] for rows in records.values())
    first,last = date.fromisoformat(common_start),date.fromisoformat(through)
    calendar = [str(first+timedelta(days=n)) for n in range((last-first).days+1)
                if is_us_trading_day(first+timedelta(days=n))]
    for symbol,rows in list(records.items()):
        rows = [r for r in rows if r['trade_date'] >= common_start]
        if [r['trade_date'] for r in rows] != calendar:
            exclusions[symbol] = 'Incomplete common US session calendar; no filling'
            del records[symbol]
        else:
            try:
                # Older observations outside the predeclared common window are
                # not inputs. Missing observations within it remain exclusions.
                for row in rows:
                    audited_bar(row)
                    audited_bar(row,raw=True)
                records[symbol] = rows
            except ValueError as exc:
                exclusions[symbol] = str(exc)
                del records[symbol]
    if not records:
        raise ValueError('No complete common calendars')
    return dict(records=records,
        bars={s:[audited_bar(r) for r in rows] for s,rows in records.items()},
        raw_bars={s:[audited_bar(r,raw=True) for r in rows] for s,rows in records.items()},
        common_start=common_start,through=through,calendar=calendar,exclusions=exclusions,
        provenance=dict(batch=reader.batch,files=dict(reader.used),
            price_basis='dividend_split_adjusted',volume_basis='audited_raw_volume',
            activity_basis='raw_close_times_raw_volume_with_adjusted_direction',
            historical_membership='Retrospective current cohort; not a historical security-master reconstruction',
            historical_availability='Audited revised price vintages do not certify historical publication availability',
            accounting_currency='USD',promotion_eligible=False))


def admission_for_day(records, candidates, day):
    """252-session warmup, prior-63-session liquidity, one duplicate representative.

    Model features/ranks still use the declared full pool; this is a selection
    eligibility gate. No new class-normalized ranking is bundled into this test.
    """
    metadata = {r['symbol']:r for r in candidates}
    observations, eligible, reasons = {}, {}, {}
    for symbol,rows in records.items():
        prior = [r for r in rows if r['trade_date'] < str(day)]
        if len(prior) < 253:
            reasons[symbol] = 'Insufficient consecutive warmup'
            continue
        activity = [Decimal(str(r['raw_close'])) * Decimal(str(r['raw_volume'])) for r in prior[-63:]]
        if any(not v.is_finite() or v <= 0 for v in activity):
            raise ValueError('Unsupported raw liquidity: ' + symbol)
        observed = dict(median_dollar_volume=str(median(activity)),minimum_dollar_volume=str(min(activity)),
            known_through=prior[-1]['trade_date'],sessions=len(activity))
        observations[symbol] = observed
        if median(activity) < 5_000_000 or min(activity) < 500_000:
            reasons[symbol] = 'Below frozen prior-session dollar-liquidity thresholds'
            continue
        group = metadata[symbol]['duplicate_review_group']
        eligible.setdefault(group,[]).append(symbol)
    selected = []
    for group,symbols in sorted(eligible.items()):
        ranked = sorted(symbols,key=lambda s:(-Decimal(observations[s]['median_dollar_volume']),metadata[s]['candidate_id']))
        selected.append(ranked[0])
        for symbol in ranked[1:]:
            reasons[symbol] = 'Duplicate representative: ' + ranked[0]
    return dict(admitted=sorted(selected),excluded=reasons,observations=observations,
        known_fees='Historical fee evidence unavailable; exact liquidity ties use permanent candidate ID',
        historical_spreads='Unavailable; dollar-volume screen does not establish historical spreads or paper readiness')
