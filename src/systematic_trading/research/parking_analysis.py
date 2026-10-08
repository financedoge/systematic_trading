"""Reconciled economics, paired uncertainty and full reports for F4."""
from datetime import date
import html
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import write_json, sha256
from systematic_trading.research.momentum_replay import read_json, checked_files, verify_usd_bundle
from systematic_trading.research.parking_study import ARMS, COMPARISONS, LABELS, jobs, job_name


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    results={};parity={};parent=Path(read_json(root/'data_receipt.json')['parent'])
    for job in jobs():
        name=job_name(job);path=root/'python'/(name+'.json');bundle=root/'bundles'/name
        receipt=read_json(path.with_suffix('.receipt.json'));verify_usd_bundle(bundle)
        if receipt['sha256']!=sha256(path) or receipt['manifest_sha256']!=sha256(bundle/'manifest.json'):
            raise ValueError('Replay receipt mismatch')
        economic=read_json(path);stats=statistics(economic,read_json(bundle/'quotes.json'))
        stats['calmar']=stats['cagr']/abs(stats['max_drawdown']) if stats['max_drawdown'] else None
        returns=np.array(stats['daily_returns']);q=np.quantile(returns,.05)
        stats['expected_shortfall_daily_95']=float(returns[returns<=q].mean())
        nav=np.array([1e6]+[float(r['nav']) for r in economic['nav']]);duration=longest=0
        for below in nav<np.maximum.accumulate(nav):
            duration=duration+1 if below else 0;longest=max(longest,duration)
        stats['max_underwater_sessions']=longest
        stats['trades']=len(economic['fills'])
        stats['bil_trades']=sum(f['symbol']=='BIL' for f in economic['fills'])
        stats['bil_fees_usd']=sum(float(f['fee']) for f in economic['fills'] if f['symbol']=='BIL')
        if job[0] in ['F0','F1','F3']:
            previous=read_json(parent/'python'/(name+'.json'))
            fields=['nav','fills','final_positions','decisions']
            if any(previous[k]!=economic[k] for k in fields):raise ValueError('Frozen control economics changed: '+name)
            parity[name]=dict(exact=True,fields=fields)
        results[name]=stats
    write_json(root/'statistics.json',results)
    write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    write_json(root/'control_parity.json',parity)


def inference(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,kind,block,index=job;root=Path(root);p=read_json(root/'protocol.json')
    if read_json(root/'statistics_receipt.json')['sha256']!=sha256(root/'statistics.json'):
        raise ValueError('Statistics receipt mismatch')
    results=read_json(root/'statistics.json')
    def primary(a):return results[job_name((a,5,0))]
    if kind=='means':
        months=sorted(primary('F0')['monthly'])
        matrix=np.array([[primary(a)['monthly'][m]-primary(b)['monthly'][m] for a,b in COMPARISONS] for m in months])
        return kind,str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    a,b=COMPARISONS[index];left,right=primary(a),primary(b)
    if left['dates']!=right['dates']:raise ValueError('Paired dates differ')
    return a+'-'+b,str(block),bootstrap_ratios(left['dates'],left['daily_returns'],right['daily_returns'],block=block,
        replications=p['bootstrap_replications'],seed=p['seed'])


def finalize(root, inference_rows):
    p=read_json(root/'protocol.json');r=read_json(root/'statistics.json');uncertainty={}
    for key,block,value in inference_rows:uncertainty.setdefault(key,{})[block]=value
    def result(a,c=5,d=0):return r[job_name((a,c,d))]
    control=read_json(root/'decisions/F1.json');days=sorted(control);episodes=[]
    for i,day in enumerate(days):
        if not control[day]['diagnostic']['fallback']:continue
        if not episodes or episodes[-1]['next_decision']!=day:episodes.append(dict(start=day,decisions=[],next_decision=None))
        ep=episodes[-1];ep['decisions'].append(day);ep['next_decision']=days[i+1] if i+1<len(days) else None
    for ep in episodes:
        ep['returns']={a:float(np.prod([1+v for m,v in result(a)['monthly'].items() if ep['start'][:7]<=m<(ep['next_decision'] or '9999')[:7]])-1)
                      for a in ['F0','F1','F3','F4','BIL']}
    screen=(result('F4',20)['cagr']>result('F1',20)['cagr'] and result('F4')['max_drawdown']>=result('F1')['max_drawdown']-.005)
    report=dict(protocol=p,results=r,inference=uncertainty,episodes=episodes,fallback_decisions=sum(len(ep['decisions']) for ep in episodes),
        economic_screen_passed=screen,promotion_eligible=False,control_parity=read_json(root/'control_parity.json'))
    write_json(root/'report.json',report)
    write_json(root/'report_receipt.json',dict(sha256=sha256(root/'report.json'),protocol_sha256=sha256(root/'protocol.json')))
    return {a:{k:result(a)[k] for k in ['cagr','sharpe_zero_cash','calmar','max_drawdown','annual_turnover','mean_cash_weight']} for a in ARMS}


def flow(arm):
    steps=['Verify pinned audited adjusted prices, coverage, hashes and previously frozen model/decision lineage']
    if arm in ['URTH','BIL']:
        steps+=['Buy and hold '+arm+' from the first evaluation session; keep fractional-unit residual cash']
    else:
        steps+=['Original 12 ETFs only: inverse 63-session volatility, initial 45% cap and 2% cash reserve']
        if arm!='RP':
            steps+=['Prior-close 252-session momentum eligibility; normal regime: price/volume top 6, renormalized incoming weights',
                'Fewer than four qualify: '+dict(F0='full-basket original fallback',F1='retain eligible positions; residual cash',
                    F3='eligible IEF/TLT/GLD only; residual cash',F4='retain eligible F1 positions; residual cash')[arm],
                'Frozen causal rolling XGBoost tilt → relative momentum → adaptive trend → activity lag-20 → USD ridge',
                'F1/F3/F4 preserve fallback membership and the declining risky-asset budget through later overlays']
        if arm=='F4':steps+=['Weak breadth only: add BIL = min(45%, max(0, 98% − final F1 gross)); original ETF weights unchanged',
                            'Otherwise target BIL at zero; no BIL ranking, model fitting or leverage']
    steps+=['Prior-close sizing → next-session open, whole adjusted units, sells before buys, 5bp primary transaction costs',
            'Daily USD holdings and NAV; distributions embedded in adjusted prices; residual cash earns zero; no order authority']
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1180 {len(steps)*72+20}" role="img" aria-label="Complete decision flow">'
    for i,s in enumerate(steps):
        y=10+i*72
        svg+=f'<rect x="10" y="{y}" width="1160" height="56" rx="8" fill="#eef5f8" stroke="#a9beca"/><text x="25" y="{y+33}" font-family="sans-serif" font-size="13">{i+1}. {html.escape(s)}</text>'
    return svg+'</svg>'


def artifacts(root, output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    report=read_json(root/'report.json');p=report['protocol'];result={};economic={};quotes={}
    output.mkdir(parents=True,exist_ok=True);(output/'reports').mkdir(exist_ok=True)
    for arm in ARMS:
        name=job_name((arm,5,0));economic[arm]=read_json(root/'python'/(name+'.json'));quotes[arm]=read_json(root/'bundles'/name/'quotes.json')
        result[arm]=report_result(economic[arm],quotes[arm],'1000000','2015-12-31')
    for arm in ARMS:
        data,warnings=build_backtest_report_data(result=result[arm],result_path=root/'python'/(job_name((arm,5,0))+'.json'),
            split_date='2023-01-01',benchmark_name='Current SOTA · matched USD',benchmark_nav_series=result['F0']['nav_series'],
            extra_benchmarks=[dict(id=a,name=LABELS[a]+' · USD',nav_series=result[a]['nav_series']) for a in ['F1','F3','RP','URTH','BIL'] if a!=arm],
            market_prices={s:{d:float(q['close']) for d,q in v.items()} for s,v in quotes[arm].items()},market_fx_rates={r['date']:1. for r in economic[arm]['nav']})
        data.update(title=LABELS[arm]+' · finite research',accountingCurrency='USD',database='Published audited histories',
            allocationSource='Daily held weights reconstructed from the simulated fill ledger.',splitLabel='Previously inspected calendar boundary',
            sampleLabels={'in_sample':'2016–2022 retrospective','out_of_sample':'2023 onward retrospective'},
            decisionDiagrams=[dict(title='Complete research decision flow',svg=flow(arm))],strategyDefinition=dict(id=arm,protocol=p),
            warnings=[*warnings,*p['limitations'],'Research only; no monitored membership or execution authority.'])
        (output/'reports'/(arm+'.html')).write_text(render_backtest_report_html(data),encoding='utf8')
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for arm in ['F0','F1','F3','F4']:
        nav=np.array([float(r['nav'])/1e6 for r in economic[arm]['nav']]);dates=[date.fromisoformat(r['date']) for r in economic[arm]['nav']]
        axes[0].plot(dates,nav,label=arm);axes[1].plot(dates,nav/np.maximum.accumulate(np.maximum(nav,1))-1,label=arm)
    axes[0].set_ylabel('Value / initial USD capital');axes[0].legend(ncol=4);axes[1].set_ylabel('Drawdown');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Treasury-bill parking · 2016–6 October 2026\n5bp costs · distributions included · zero cash interest · retrospective research')
    fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    rows=[]
    for arm in ARMS:
        s=report['results'][job_name((arm,5,0))]
        rows.append(f'<tr><td><a href="reports/{arm}.html">{arm} · {html.escape(LABELS[arm])}</a></td><td>{s["cagr"]:.2%}</td><td>{s["sharpe_zero_cash"]:.3f}</td><td>{s["calmar"]:.3f}</td><td>{s["max_drawdown"]:.2%}</td><td>{s["annual_turnover"]:.2f}</td></tr>')
    body='<!doctype html><html><head><meta charset="utf-8"><title>Treasury-bill parking research</title><style>body{font:16px system-ui;max-width:1300px;margin:30px;color:#203449;background:#f6f8fb}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;text-align:right;border-bottom:1px solid #dde3eb}td:first-child,th:first-child{text-align:left}img{width:100%}li{margin:.5em 0}a{color:#17549d}</style></head><body><h1>Treasury-bill parking research</h1><p>2016–6 October 2026 · USD · 5bp costs · distributions embedded in adjusted prices · residual cash earns zero.</p><p>F4 preserves F1’s original ETF targets and invests residual cash in BIL only when fewer than four ETFs qualify. BIL target cap: 45%; operational cash minimum: 2%. No tuning or promotion.</p><table><tr><th>Recipe — full report</th><th>CAGR</th><th>Sharpe (zero RF)</th><th>Calmar</th><th>Max drawdown</th><th>Turnover/year</th></tr>'+''.join(rows)+'</table><img src="comparison.png" alt="Portfolio values and drawdowns"><h2>Registered limitations</h2><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in p['limitations'])+'</ul></body></html>'
    (output/'index.html').write_text(body,encoding='utf8')
    write_json(output/'receipt.json',dict(study=str(root),protocol_sha256=sha256(root/'protocol.json'),report_sha256=sha256(root/'report.json'),
        files={f.relative_to(output).as_posix():sha256(f) for f in output.rglob('*') if f.is_file() and f.name!='receipt.json'}))
    return str((output/'index.html').resolve())
