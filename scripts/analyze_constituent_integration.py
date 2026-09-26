"""Analyze earlier-stage stock information versus late overlays and price controls."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, verify_bundle, write_json
from systematic_trading.lean.registry import register_run
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.constituent_integration import choose_residual_model
from systematic_trading.storage.postgres import PostgresStore
from analyze_constituent_research import information_ratio
from analyze_flow_concentration_research import metrics, return_vector, block_audit
from run_constituent_research import verify_manifest

PAIRS = {
    'early_signed_vs_late': ('early_signed', 'late_signed'),
    'selection_signed_vs_late': ('selection_signed', 'late_signed'),
    'early_breadth_vs_late': ('early_breadth', 'late_breadth'),
    'selection_breadth_vs_late': ('selection_breadth', 'late_breadth'),
    'late_signed_vs_price': ('late_signed', 'late_price'),
    'early_signed_vs_price': ('early_signed', 'early_price'),
    'selection_signed_vs_price': ('selection_signed', 'selection_price'),
    'tree_joint_vs_price': ('tree_joint', 'tree_price'),
}


def audit_exposure(economic, baseline, quotes, features, spec):
    changes, entries, removals, max_delta, gross_difference = 0, 0, 0, 0., 0.
    tree_active = []
    decisions = []
    qualified_spy_absences = []
    for d, row in economic['decisions'].items():
        base_row = baseline['decisions'][d]
        base = {t['symbol']: float(t['target_weight']) for t in base_row['targets']}
        actual = {t['symbol']: float(t['target_weight']) for t in row['targets']}
        delta = max(abs(actual[s]-w) for s,w in base.items())
        changed = delta > 1e-8
        changes += changed
        entries += base['SPY'] < 1e-8 and actual['SPY'] > 1e-8
        removals += base['SPY'] > 1e-8 and actual['SPY'] < 1e-8
        max_delta = max(max_delta, delta)
        gross_difference = max(gross_difference, abs(sum(actual.values())-sum(base.values())))
        if spec and spec.get('stage') == 'selection' and base['SPY'] < 1e-8:
            feature = features.get(str(spec.get('holdings_lag_days', 45)), {}).get(row['known_through'])
            if feature and feature.get('scores') is not None and feature['value_coverage'] >= spec.get('min_value_coverage', .95) and feature['name_coverage'] >= spec.get('min_name_coverage', .70):
                qualified_spy_absences.append(dict(date=d, score=feature['scores'][spec['signal']],
                    resulting_spy_weight=actual['SPY']))
        if spec and spec.get('stage') == 'tree' and choose_residual_model(features, row['known_through'], spec.get('tree_inputs','joint')) is not None:
            tree_active.append(d)
        decisions.append(dict(date=d, changed=changed, base_spy=base['SPY'], spy=actual['SPY'],
            spy_delta=actual['SPY']-base['SPY'], max_asset_delta=delta, names=sum(w > 1e-8 for w in actual.values())))
    holdings, by_date, weights, gross = {}, {}, [], []
    for f in economic['fills']:
        by_date.setdefault(f['date'], []).append(f)
    for row in economic['nav']:
        d = row['date']
        for f in by_date.get(d, []):
            holdings[f['symbol']] = holdings.get(f['symbol'], 0)+f['quantity']
        values = {s:q*float(quotes[s][d]['close'])/float(row['nav']) for s,q in holdings.items()}
        weights.append(values.get('SPY', 0))
        gross.append(sum(values.values()))
    return dict(changed_decisions=int(changes), new_spy_selections=int(entries), removed_spy_selections=int(removals),
        max_active_weight=max_delta, max_target_gross_difference=gross_difference,
        average_spy_weight=float(np.mean(weights)), average_gross=float(np.mean(gross)),
        first_tree_decision=tree_active[0] if tree_active else None, tree_decisions=len(tree_active),
        qualified_spy_absences=qualified_spy_absences, decisions=decisions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    verify_manifest(root, 'input_manifest.json')
    protocol = json.loads((root/'protocol.json').read_text())
    progress = json.loads((root/'progress.json').read_text())
    if not progress['complete']:
        raise ValueError('Finish all predeclared trials before analysis')
    economies, references = {}, {}
    for n in progress['passed']:
        verify_bundle(root/'datasets'/n)
        receipt = json.loads((root/'runs'/n/'run.json').read_text())
        if receipt['status'] != 'succeeded' or receipt['economic_sha256'] != progress['passed'][n]:
            raise ValueError('Invalid completed run: '+n)
        if sha256(root/'runs'/n/'economic.json') != receipt['artifacts']['economic.json']:
            raise ValueError('Changed engine output: '+n)
        economies[n] = json.loads((root/'runs'/n/'economic.json').read_text())
    for n, original in dict(sota='sota', late_signed='signed_activity', late_breadth='breadth', late_price='price_control').items():
        prior = json.loads((Path(protocol['feature_origin'])/'runs'/original/'run.json').read_text())
        references[n] = progress['passed'][n] == prior['economic_sha256']
    if not all(references.values()):
        raise ValueError('Prior SOTA/late reference economics changed')
    days = np.array([r['date'] for r in economies['sota']['nav']])
    if any([r['date'] for r in e['nav']] != list(days) for e in economies.values()):
        raise ValueError('Unaligned return dates')
    vectors = {n: return_vector(e['nav']) for n,e in economies.items()}
    windows = dict(full=(protocol['start'], protocol['end']), pre2023=(protocol['start'], '2022-12-31'),
        reused_post2023=('2023-01-01', protocol['end']), tree_era2025=('2025-01-01', protocol['end']),
        **{str(y):(f'{y}-01-01', f'{y}-12-31') for y in range(2019, 2027)})
    summary, exposures = {}, {}
    features = json.loads((root/'features.json').read_text())
    quotes = json.loads((root/'datasets'/'sota'/'quotes.json').read_text())
    for n,e in economies.items():
        base = 'sota'+('__'+n.split('__')[1] if '__' in n else '')
        summary[n] = {}
        for label,(start,end) in windows.items():
            mask = (days >= start)&(days <= end)
            m, b = metrics(e,start,end), metrics(economies[base],start,end)
            summary[n][label] = dict(**m, **information_ratio((vectors[n]-vectors[base])[mask]),
                cagr_delta=m['cagr']-b['cagr'], sharpe_delta=m['sharpe']-b['sharpe'], comparator=base)
        exposures[n] = audit_exposure(e,economies[base],quotes,features,protocol['trials'][n.split('__')[0]])
        if exposures[n]['max_active_weight'] > .03000001 or exposures[n]['max_target_gross_difference'] > 1e-8:
            raise ValueError('Unmatched target risk budget: '+n)
    candidates = [n for n in protocol['trials'] if n != 'sota']
    uncertainty, comparisons = {}, {}
    for window in ('full','reused_post2023','tree_era2025'):
        start,end = windows[window]
        mask = (days >= start)&(days <= end)
        matrix = np.column_stack([vectors[n]-vectors['sota'] for n in candidates])[mask]
        uncertainty[window] = {str(block):block_audit(matrix,candidates,block=block) for block in (63,126)}
        pair_matrix = np.column_stack([vectors[a]-vectors[b] for a,b in PAIRS.values()])[mask]
        pair_audit = block_audit(pair_matrix,list(PAIRS),block=63)
        comparisons[window] = {key:dict(**information_ratio(pair_matrix[:,i]),
            cagr_delta=summary[a][window]['cagr']-summary[b][window]['cagr'],
            sharpe_delta=summary[a][window]['sharpe']-summary[b][window]['sharpe'],
            bootstrap=pair_audit['trials'][key]) for i,(key,(a,b)) in enumerate(PAIRS.items())}
    for name,value in [('summary',summary),('comparisons',comparisons),('uncertainty',uncertainty),
                       ('exposure_audit',exposures),('reference_parity',references)]:
        write_json(root/f'{name}.json',value)
    with (root/'daily_returns.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream)
        writer.writerow(['date',*vectors])
        writer.writerows([d,*[v[i] for v in vectors.values()]] for i,d in enumerate(days))
    lines = ['# Earlier integration of constituent information', '',
        'Exploratory follow-up selected after observing positive late-overlay sample IR. All periods were previously inspected; chronological fitting prevents future labels entering the tree but does not create an untouched holdout. Public ITOT stock proxies guide only SPY. No promotion.', '',
        '## Results after sufficient stock coverage begins', '',
        '2023-01-01–2026-09-24; net CNH returns; zero-hurdle Sharpe. IR measures daily active returns versus unchanged SOTA. Tree corrections are neutral until a dated model is available.', '',
        '| Variant | CAGR | Sharpe | IR | Δ CAGR pp | Changed decisions | New SPY entries |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for n in protocol['trials']:
        m=summary[n]['reused_post2023']; audit=exposures[n]
        ir='—' if m['information_ratio'] is None else f"{m['information_ratio']:+.3f}"
        lines.append(f"| {n} | {m['cagr']:.2%} | {m['sharpe']:.3f} | {ir} | {m['cagr_delta']*100:+.3f} | {audit['changed_decisions']} | {audit['new_spy_selections']} |")
    lines += ['', '## Direct comparisons', '', '| Comparison | Period | Δ CAGR pp | Active IR | 95% annual active-return interval, pp | Adjusted p within pair family |',
              '| --- | --- | ---: | ---: | --- | ---: |']
    for window in ('reused_post2023','tree_era2025'):
        for n,m in comparisons[window].items():
            b=m['bootstrap'];lo,hi=b['ci95']
            ir='—' if m['information_ratio'] is None else f"{m['information_ratio']:+.3f}"
            lines.append(f"| {n} | {window} | {m['cagr_delta']*100:+.3f} | {ir} | [{lo*100:+.3f}, {hi*100:+.3f}] | {b['max_t_family_adjusted_p']:.3f} |")
    lines += ['', '## Tree evaluation, 2025 onward', '', '| Variant | CAGR | Sharpe | IR vs SOTA | First usable model decision |', '| --- | ---: | ---: | ---: | --- |']
    for n in ('sota','tree_joint','tree_price'):
        m=summary[n]['tree_era2025']
        ir='—' if m['information_ratio'] is None else f"{m['information_ratio']:+.3f}"
        lines.append(f"| {n} | {m['cagr']:.2%} | {m['sharpe']:.3f} | {ir} | {exposures[n]['first_tree_decision'] or '—'} |")
    lines += ['', '## Matched robustness, full period', '', '| Scenario | SOTA CAGR / Sharpe | Selection signed CAGR / Sharpe | Selection price CAGR / Sharpe |', '| --- | --- | --- | --- |']
    for stress in protocol['stresses']:
        rows = [summary[n+'__'+stress]['full'] for n in ('sota','selection_signed','selection_price')]
        lines.append('| '+stress+' | '+' | '.join(f"{r['cagr']:.2%} / {r['sharpe']:.3f}" for r in rows)+' |')
    lines += ['', '## Contracts and limitations', '',
        '- SOTA and all three late references reproduce the preceding study economic hashes exactly. All native runs passed unchanged target/fill/cash tolerances.',
        '- Earlier allocation occurs after pool selection and before the existing tree. Selection adds +/-0.15 to SPY ranking (0.075 neighbor) and preserves long-momentum eligibility. Final candidates are exposure-matched and blended to at most 3pp active change per ETF, so a pool change can add a small SPY position and retain seven names.',
        '- Residual trees use monthly next-rebalance USD returns relative to the equal-weight twelve-ETF mean, minus the frozen SPY tree forecast. Both fits use the same 23/35 completed samples at 2025/2026 cutoffs, depth 2/minimum leaf 6, 25% shrinkage and +/-1pp forecast cap. Price-only uses mom63, mom126 and the base forecast; joint additionally uses breadth and signed activity. Model selection uses the prior completed session cutoff; January 1 fits first reach this monthly adapter in February. Training labels are stored separately from runtime features.',
        '- Coverage first passes January 2023. No constituent crash evidence from 2020/2022; historical holdings availability is a 45-day assumption, adjusted histories are revised and delistings incomplete. An earlier stage cannot repair these data limitations.',
        '- Multiple-testing audits cover the current twelve variants and separately the eight direct contrasts, not the prior research search. Do not regard selected positive IR or fitted branches as independent discovery.',
        '- High-cost/delay stresses are predeclared for selection signed, its price control and SOTA. The tree comparison is not separately cost-stressed; positive tree evidence would still need that check and new data before inclusion.', '',
        'Files: protocol/input manifests, models.json, training_records.json, summary/comparisons/uncertainty JSON, exposure_audit.json, daily_returns.csv and all native datasets/runs. Source, model, training-label and result evidence is in ClickHouse; native receipts enter the research-only PostgreSQL registry.', '']
    (root/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    sys.path.insert(0,'D:/systematic_trading_data/lean/research/plot_dependencies')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(16,10))
    mask=days>='2023-01-01';stamps=[datetime.fromisoformat(d) for d in days[mask]]
    selected=['late_signed','early_signed','selection_signed','tree_joint','selection_price','tree_price']
    for n in selected:
        relative=np.cumprod(1+vectors[n][mask])/np.cumprod(1+vectors['sota'][mask])-1
        axes[0,0].plot(stamps,relative,label=n,lw=1.3,ls='--' if 'price' in n else '-')
    axes[0,0].axhline(0,color='#94a3b8',lw=.8)
    axes[0,0].set_title('Relative wealth vs SOTA, 2023 onward')
    axes[0,0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0,0].legend(fontsize=8,ncol=2,frameon=False)
    values=[summary[n]['reused_post2023']['cagr_delta']*100 for n in candidates]
    axes[0,1].barh(candidates,values,color=['#0891b2' if v>0 else '#b45309' for v in values])
    axes[0,1].axvline(0,color='#94a3b8',lw=.8)
    axes[0,1].set_title('Incremental CAGR, percentage points (2023 onward)')
    values=[summary[n]['reused_post2023']['information_ratio'] or 0 for n in candidates]
    axes[1,0].barh(candidates,values,color=['#0891b2' if v>0 else '#b45309' for v in values])
    for i,n in enumerate(candidates):
        if summary[n]['reused_post2023']['information_ratio'] is None:
            axes[1,0].text(0,i,' n/a: no active return',va='center',fontsize=8,color='#64748b')
    axes[1,0].axvline(0,color='#94a3b8',lw=.8)
    axes[1,0].set_title('Information ratio vs SOTA (2023 onward)')
    for n in ('late_signed','early_signed','selection_signed','tree_joint'):
        r=[r for r in exposures[n]['decisions'] if r['date']>='2023-01-01']
        axes[1,1].step([datetime.fromisoformat(x['date']) for x in r],[x['spy_delta'] for x in r],where='post',label=n,lw=1.1)
    axes[1,1].axhline(0,color='#94a3b8',lw=.8)
    axes[1,1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1,1].set_title('SPY target change: same 3pp maximum risk budget')
    axes[1,1].legend(fontsize=8,ncol=2,frameon=False)
    fig.suptitle('Does earlier constituent information improve ETF allocation?',x=.04,ha='left',fontsize=20,weight='bold')
    fig.text(.04,.935,'Native LEAN | Selection / allocation / tree ablations | Reused public-data sample | Residual tree first active February 2025',fontsize=10,color='#475569')
    fig.tight_layout(rect=(.02,.02,1,.915),w_pad=4,h_pad=3)
    fig.savefig(root/'results.png',dpi=160)
    plt.close(fig)
    models=json.loads((root/'models.json').read_text())
    fig,axes=plt.subplots(2,2,figsize=(15,9))
    labels={'mom_63':'SPY 63-session momentum','mom_126':'SPY 126-session momentum','base_forecast':'Original tree forecast',
            'breadth':'Stock breadth','signed_activity':'Stock signed activity'}
    def draw_node(ax,node,x=.5,y=.84,width=.45,depth=0):
        feature=node['feature']
        if feature is None:
            label=f"Residual {node['value']:+.2%}\n{node['samples']} training months"
            color='#e2e8f0'
        else:
            label=f"{labels[feature]}\nthreshold {node['threshold']:.3f}\nn={node['samples']}"
            color='#ffedd5' if feature in ('breadth','signed_activity') else '#dbeafe'
        ax.text(x,y,label,ha='center',va='center',fontsize=9,bbox=dict(boxstyle='round,pad=.45',fc=color,ec='#64748b'))
        if feature is not None:
            for child,direction in ((node['left'],-1),(node['right'],1)):
                nx,ny=x+direction*width/2,y-.31
                ax.plot([x,nx],[y-.07,ny+.07],c='#94a3b8',lw=1,zorder=-1)
                ax.text((x+nx)/2,(y+ny)/2,'≤' if direction<0 else '>',ha='center',fontsize=9,color='#475569')
                draw_node(ax,child,nx,ny,width/2,depth+1)
    for i,kind in enumerate(('joint','price')):
        for j,(d,record) in enumerate(sorted(models[kind].items())):
            ax=axes[i,j];ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
            ax.set_title(f"{d[:4]} — {'Constituents + price' if kind=='joint' else 'Price-only control'}",pad=12)
            draw_node(ax,record['model']['root'])
    fig.suptitle('What the shallow correction trees actually learned',x=.04,ha='left',fontsize=20,weight='bold')
    fig.text(.04,.93,'Orange nodes use constituent data. Leaf residuals are shrunk to 25% and capped at ±1pp before modifying the original forecast.',fontsize=10,color='#475569')
    fig.tight_layout(rect=(.02,.02,1,.90),w_pad=3,h_pad=2)
    fig.savefig(root/'trees.png',dpi=160)
    plt.close(fig)
    shutil.copyfile(__file__,root/'analysis_source.py')
    files=['summary.json','comparisons.json','uncertainty.json','exposure_audit.json','reference_parity.json','daily_returns.csv','report.md','results.png','trees.png','analysis_source.py']
    write_json(root/'analysis_manifest.json',{n:sha256(root/n) for n in files})
    store=AnalyticsStore.from_settings(AppSettings())
    observations=[observation(n+'/'+w,'research_constituent_backtest',n,r) for n,periods in summary.items() for w,r in periods.items()]
    observations += [observation(w+'/'+n,'research_constituent_contrast',n,r) for w,pairs in comparisons.items() for n,r in pairs.items()]
    docs=[dict(point_key=n,media_type='text/markdown' if n.endswith('.md') else 'application/json',payload=(root/n).read_text(encoding='utf-8'))
          for n in ('report.md','summary.json','comparisons.json','uncertainty.json','exposure_audit.json','analysis_manifest.json')]
    version=digest(encode(json.loads((root/'analysis_manifest.json').read_text())))
    changed=store.publish('constituent-research/'+root.name+'/results',version,observations,docs,
        provenance=dict(research_only=True,selected_followup=True,all_native_parity_passed=True,prior_reference_parity=references))
    write_json(root/'results_clickhouse_receipt.json',dict(version=version,changed=changed,observations=len(observations),documents=len(docs)))
    registry=PostgresStore.from_settings(AppSettings())
    write_json(root/'registry_receipt.json',{n:register_run(registry,root/'runs'/n) for n in economies})
    print((root/'report.md').read_text(encoding='utf-8'),flush=True)


if __name__=='__main__':
    main()
