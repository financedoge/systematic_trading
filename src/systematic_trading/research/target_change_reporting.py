"""Complete finite-research decision flow for selection and adoption variants."""
import html
import textwrap


def variant_decision_diagrams(definition, width, policy):
    layers={o.kind:o.parameters for o in definition.overlays}
    financial='financial_rank_selection' in layers
    count='selected by the annual causal calendar' if width=='WF' else str(width)
    steps=[
        ('Verify the frozen input and recipe manifests', 'Audited adjusted USD prices; explicit activity basis; original model cutoffs and macro source dates.'),
        ('Calculate the theoretical target each completed session', 'An exact macro snapshot is preferred; otherwise carry the previous completed monthly snapshot and record its age.'),
        ('Inverse-volatility base allocation', '63-session volatility, 45% base weight cap and 2% cash reserve; existing parent sizing is unchanged.'),
        ('Rank every candidate in the fixed parent universe',
         'FR25: 75% M1 rank plus 25% frozen financial forecast rank. M1 uses 21/63/126-session momentum and volume.' if financial
         else 'F3: 63/126/252-session momentum and volume ranks. The original model universe is preserved.'),
        (f'Keep at most X = {count} eligible ETFs',
         f'Positive {126 if financial else 252}-session momentum gate; deterministic ties. A wider X never forces allocation.'),
        ('Fewer than four eligible candidates?', 'Retain only qualifying IEF, TLT and GLD incoming weights; protect residual cash through every later layer.'),
        ('Apply the existing monthly rolling one-year XGBoost sizing', 'Use only the causally permitted model and current price features. No new daily refit or changed training universe.'),
        ('Apply relative momentum and adaptive trend exposure', 'Preserve the parent parameters, selected membership and any protected fallback cash budget.'),
        ('Apply the parent activity overlay', 'FR25 uses audited raw dollar activity and adjusted direction; F3 retains its disclosed legacy adjusted-price/source-volume proxy.'),
        ('Apply the existing monthly USD ridge', 'Current price features plus exact or carried monthly USD21/USD63 features. Keep the original snapshot timestamp.'),
    ]
    if 'final_weight_cap' in layers:
        steps.append(('Apply the final 45% ETF target cap','Any clipped excess remains in cash. Held weights may drift between adoption events.'))
    steps += [
        ('Measure target change, including residual cash', 'L1 distance = sum of absolute latest theoretical minus last logically adopted target weights. Actual held weights are excluded.'),
        (f'Adoption policy: {policy}', 'Initial and scheduled monthly adoptions always occur; extra events require distance strictly greater than n. No cooldown or partial rebalance.'),
        ('Update the adopted-target anchor once per event', 'Monthly/threshold collisions create one event. Update the anchor even if whole-unit sizing creates no trade; invalid inputs do not advance it.'),
        ('Freeze the event target; fill at the next session open', 'USD whole adjusted units, prior execution-session close sizing, sells before buys, cash constraints and fees on actual traded notional.'),
        ('Hold quantities between events and mark NAV daily', 'Delay stress adds one session with the same target. Retain unfilled end events. Trading housekeeping and broker authority are separate.'),
    ]
    boxes=[];y=12
    for i,(title,body) in enumerate(steps,1):
        lines=textwrap.wrap(body,112);height=max(78,48+19*len(lines))
        if boxes:boxes.append(f'<path d="M500 {y-14} V{y}" stroke="#487a99" stroke-width="2"/>')
        boxes.append(f'<rect x="35" y="{y}" width="930" height="{height}" rx="9" fill="#edf5f5" stroke="#8faeb9"/>')
        boxes.append(f'<text x="55" y="{y+26}" font-size="16" font-weight="600" fill="#172b43">{html.escape(str(i)+". "+title)}</text>')
        for j,line in enumerate(lines):boxes.append(f'<text x="55" y="{y+49+j*19}" font-size="14" fill="#172b43">{html.escape(line)}</text>')
        y+=height+18
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {y}" role="img" aria-label="Complete research strategy decision flow">'+''.join(boxes)+'</svg>'
    return [dict(title='Complete research variant decision flow',svg=svg,
        note='Executable parent signals, explicit X override, macro carry, adoption state and accounting. Finite research only.')]
