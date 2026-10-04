"""Audit and publication boundary for same-vintage broad dollar histories."""
import csv
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO
import math
from zoneinfo import ZoneInfo


def audit_snapshot(text,metadata):
    vintage=date.fromisoformat(metadata['vintage_date'])
    known=date.fromisoformat(metadata['known_through'])
    decision=date.fromisoformat(metadata['decision_date'])
    if not date(2019,2,4)<=vintage<known<decision:
        raise ValueError('USD snapshot must postdate methodology launch and precede the signal close')
    column='DTWEXBGS_'+str(vintage).replace('-','')
    reader=csv.DictReader(StringIO(text))
    if reader.fieldnames!=['observation_date',column]:
        raise ValueError('Wrong USD identity/vintage')
    rows=[]
    for r in reader:
        day=date.fromisoformat(r['observation_date'])
        if day>vintage:raise ValueError('Future USD observation')
        value=Decimal(r[column]) if r[column] not in ('','.','ND') else None
        if value is not None and (not value.is_finite() or not 40<value<250):
            raise ValueError('Invalid broad USD index level')
        rows.append(dict(date=str(day),value=str(value) if value is not None else None))
    dates=[r['date'] for r in rows]
    if not dates or dates!=sorted(set(dates)):
        raise ValueError('Duplicate or out-of-order USD observations')
    valid=[r for r in rows if r['value'] is not None]
    if len(valid)<64:raise ValueError('Insufficient USD history')
    last=valid[-1]
    if (known-date.fromisoformat(last['date'])).days>14:
        raise ValueError('Stale USD release')
    window=valid[-64:]
    if (date.fromisoformat(last['date'])-date.fromisoformat(window[0]['date'])).days>105:
        raise ValueError('Excessive missing USD observations')
    changes=[float(Decimal(b['value'])/Decimal(a['value'])-1) for a,b in zip(window,window[1:])]
    if any(not math.isfinite(v) or abs(v)>.05 for v in changes):
        raise ValueError('Unexplained daily USD change exceeds audit threshold')
    # Ratios use a single ALFRED snapshot, including its historical revisions and
    # index base. Never join levels across dates with different index vintages.
    features={f'USD{lag}':float(Decimal(last['value'])/Decimal(valid[-1-lag]['value'])-1) for lag in (21,63)}
    return dict(series='DTWEXBGS',vintage_date=str(vintage),known_through=str(known),decision_date=str(decision),
        available_at=datetime.combine(vintage,time(23,59,59),ZoneInfo('America/New_York')).isoformat(),
        available_at_basis='conservative end of ALFRED vintage day; used only on a later signal-close date',
        observation_date=last['date'],observations=rows,features=features,
        missing_observation_dates=[r['date'] for r in rows if r['value'] is None],
        feature_basis='21/63 valid published index observations within one vintage; missing values retained, not filled',
        limitations=['ALFRED vintage dates are daily archive evidence, not independently certified intraday dissemination timestamps.',
                     'An index level history can change across vintages; each feature uses one intact vintage.',
                     'Valid-observation horizons can span missing source observations; calendar span is bounded and reported.'])
