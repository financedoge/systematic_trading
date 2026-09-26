"""Offline SVG decision diagrams generated from the executable definition."""
import html
import json


def label(lines, x, y, size=13):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="#172b43">' + ''.join(
        f'<tspan x="{x}" dy="{0 if i == 0 else 19}">{html.escape(str(line))}</tspan>' for i, line in enumerate(lines)) + '</text>'


def decision_diagrams(definition):
    overlays = {o.kind: o.parameters for o in definition.overlays}
    steps = [
        ("Published audited prices, supported FX, fixed strategy definition", "Verify hashes, adjustment basis, identity and completed sessions."),
        ("Data complete through the previous session?", "No: retain the last valid publication and report the missing input."),
        ("First trading session of the month?", "No: retain held quantities, mark NAV; calculate indicative targets separately."),
        ("Inverse-volatility risk parity", "63-session volatility; 45% base cap; 2% cash reserve."),
    ]
    if "asset_pool_filter" in overlays:
        p = overlays["asset_pool_filter"]
        steps += [(f"Select top {p['topN']} using price and volume rank", f"63/126/252d trend + 21/126d volume. Fewer than {p['minSelected']} pass: neutral base allocation.")]
    if "decision_tree" in overlays:
        p = overlays["decision_tree"]
        steps += [("Select the model permitted at the decision date", "Before 2023: causal annual fit; from 2023: deployed frozen tree below."),
                  ("Forecast each ETF and rank the predicted excess return", f"Tilt {p['tilt']}; active cap {p['maxActiveWeight']}; preserve invested weight.")]
    if "relative_momentum" in overlays:
        p = overlays["relative_momentum"]
        steps += [("Relative momentum and risk regime", f"45% × 20d + 55% × 60d momentum; tilt {p['calmTilt']}/{p['riskTilt']}; cap {p['maxActiveWeight']}.")]
    if "adaptive_trend" in overlays:
        p = overlays["adaptive_trend"]
        steps += [("Adaptive trend exposure", "63/126/252d trend, 21d rebound/up-volume, 21/252d volatility shock."),
                  (f"Select exposure scale: {p['defensiveScale']} / {p['weakScale']} / {p['neutralScale']} / {p['reboundScale']}", "Shock, weak, neutral or recovery/strong trend; redistribute residual as specified.")]
    if "etf_activity" in overlays:
        p = json.loads(overlays["etf_activity"]["spec"])
        steps += [("Relative ETF dollar-activity shares", f"Adjusted close × source volume / prior {p['normalization_bars']}d mean; normalize across ETFs."),
                  (f"EMA({p['smoothing_span']}) → second difference, lag {p['difference_lag']}", f"z = acceleration / prior {p['noise_bars']}-session derivative noise; Hurst filter disabled."),
                  (f"z > {p['threshold']} AND slope, 20d return, signed volume > 0?", f"Yes: +1. Otherwise z < -{p['threshold']}: -1. Otherwise: 0."),
                  (f"Apply {p['relative_tilt']:.0%} tilt to already selected assets", f"Project to ±{p['active_cap']:.0%} active bounds; preserve gross exposure and cash; no new selections."),
                  ("45% ceiling on increases", "An inherited base weight above 45% may be retained but cannot increase.")]
    steps += [("Freeze targets; simulate next-session open fills", "Whole adjusted CNH units; sells before buys; 5 bps fee; cash constrained."),
              ("Daily portfolio value, held weights and benchmark comparison", "Risk parity · URTH · matched SOTA. Tracking never authorizes broker orders.")]
    height = len(steps)*100+30
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" role="img" aria-label="Complete strategy decision flow">',
             '<defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#487a99"/></marker></defs>']
    for i, lines in enumerate(steps):
        y = i*100+10
        if i:
            parts.append(f'<path d="M500 {y-25} V{y}" stroke="#487a99" stroke-width="2" marker-end="url(#flow-arrow)"/>')
        parts.append(f'<rect x="45" y="{y}" width="910" height="75" rx="10" fill="{("#edf7f3" if i > 8 else "#f0f5fa")}" stroke="#9bb6c9"/>')
        parts.append(label((f"{i+1}. {lines[0]}", lines[1]), 66, y+28, 15))
    parts.append('</svg>')
    result = [dict(title="Complete strategy decision flow", svg=''.join(parts))]
    if "decision_tree" in overlays:
        model = json.loads(overlays["decision_tree"]["model"])
        nodes, edges = [], []
        def visit(node, depth, left, right):
            x, y = (left+right)/2, 38+depth*108
            lines = ([node["feature"], f"≤ {node['threshold']:.6g}", f"fallback {node['value']:.4%}"]
                     if node.get("feature") is not None else ["Leaf forecast", f"{node['value']:.4%}", f"n={node['samples']}"])
            width = max(134, len(lines[0]) * 6.5 + 14)
            nodes.append(f'<rect x="{x-width/2}" y="{y}" width="{width}" height="74" rx="6" fill="#f0f5fa" stroke="#9bb6c9"/>')
            nodes.append(label(lines, x-width/2+6, y+19, 11))
            for side, lo, hi in [("left", left, x), ("right", x, right)]:
                if node.get(side):
                    cx, cy = visit(node[side], depth+1, lo, hi)
                    edges.append(f'<path d="M{x} {y+74} L{cx} {cy}" stroke="#65859b" fill="none"/>')
                    edges.append(label(["≤" if side == "left" else ">"], (x+cx)/2, (y+74+cy)/2, 12))
            return x, y
        visit(model["root"], 0, 0, 1200)
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 480" role="img" aria-label="Frozen regression tree branches">'+''.join(edges+nodes)+'</svg>'
        result.append(dict(title="Deployed frozen regression tree — all branches and leaf forecasts", svg=svg,
                           note="Missing/non-finite feature values use the node mean shown as fallback. Before 2023 the causal annual tree for that date is used instead."))
    return result
