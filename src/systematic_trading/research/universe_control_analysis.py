"""Matched diagnostics and shared full reports for the frozen universe control."""
from datetime import date
import html

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files, verify_usd_bundle
from systematic_trading.research.universe_control import ARMS, LABELS, jobs, job_name


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    checked_files(root,"input_manifest.json");checked_files(root,"decision_manifest.json")
    results={};parity={}
    for job in jobs():
        name=job_name(job);path=root/"python"/(name+".json");bundle=root/"bundles"/name
        verify_usd_bundle(bundle);receipt=read_json(path.with_suffix(".receipt.json"))
        if receipt != dict(sha256=sha256(path),manifest_sha256=sha256(bundle/"manifest.json")):
            raise ValueError("Replay receipt mismatch")
        economic=read_json(path);stats=statistics(economic,read_json(bundle/"quotes.json"))
        stats["calmar"]=stats["cagr"]/abs(stats["max_drawdown"]) if stats["max_drawdown"] else None
        if job==("F3",5,0):
            previous=read_json(root/"baseline_economic.json")
            if any(previous[k] != economic[k] for k in ["nav","fills","decisions","final_positions"]):
                raise ValueError("Existing F3 economics failed exact reproduction")
            parity[name]=True
        results[name]=stats
    write_json(root/"statistics.json",results)
    write_json(root/"statistics_receipt.json",dict(sha256=sha256(root/"statistics.json")))
    write_json(root/"control_parity.json",parity)


def inference(job):
    from pathlib import Path
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,block=job;root=Path(root);p=read_json(root/"protocol.json")
    if read_json(root/"statistics_receipt.json")["sha256"] != sha256(root/"statistics.json"):
        raise ValueError("Changed statistics")
    r=read_json(root/"statistics.json");a,b=(r[job_name((s,5,0))] for s in ["RP14","RP12"])
    if a["dates"] != b["dates"]:
        raise ValueError("Unmatched dates")
    months=sorted(a["monthly"])
    means=paired_bootstrap(np.array([[a["monthly"][m]-b["monthly"][m]] for m in months]),
        block=block,replications=p["bootstrap_replications"],seed=p["seed"])
    ratios=bootstrap_ratios(a["dates"],a["daily_returns"],b["daily_returns"],block=block,
        replications=p["bootstrap_replications"],seed=p["seed"])
    return str(block),dict(means=means,ratios=ratios)


def finalize(root,uncertainty):
    p=read_json(root/"protocol.json");r=read_json(root/"statistics.json")
    a,b=(r[job_name((s,5,0))] for s in ["RP14","RP12"]);screen=p["retention_screen"]
    checks=dict(sharpe=a["sharpe_zero_cash"]-b["sharpe_zero_cash"]>=screen["min_sharpe_gain"],
        calmar=a["calmar"]-b["calmar"]>=screen["min_calmar_gain"],
        return_budget=a["cagr"]>=b["cagr"]-screen["max_cagr_sacrifice"],
        drawdown=a["max_drawdown"]>=b["max_drawdown"]-screen["max_drawdown_worsening"])
    checks["robustness"]=all(r[job_name(("RP14",c,d))]["sharpe_zero_cash"]>r[job_name(("RP12",c,d))]["sharpe_zero_cash"]
        and r[job_name(("RP14",c,d))]["calmar"]>r[job_name(("RP12",c,d))]["calmar"] for c,d in [(10,0),(20,0),(5,1)])
    outcome="retain_for_observation" if all(checks.values()) else "reject_unchanged_sizing_expansion"
    write_json(root/"report.json",dict(protocol=p,results=r,inference=dict(uncertainty),checks=checks,
        outcome=outcome,promotion_eligible=False,control_parity=read_json(root/"control_parity.json")))
    return dict(outcome=outcome,checks=checks,metrics={s:{k:r[job_name((s,5,0))][k] for k in
        ["cagr","sharpe_zero_cash","calmar","max_drawdown","annual_turnover"]} for s in ARMS})


def artifacts(root,output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    checked_files(root,"input_manifest.json");checked_files(root,"decision_manifest.json")
    report=read_json(root/"report.json");p=report["protocol"];result={};economics={};quotes={}
    output.mkdir(parents=True,exist_ok=True);(output/"reports").mkdir(exist_ok=True)
    for arm in ARMS:
        name=job_name((arm,5,0));economics[arm]=read_json(root/"python"/(name+".json"));quotes[arm]=read_json(root/"bundles"/name/"quotes.json")
        result[arm]=report_result(economics[arm],quotes[arm],p["initial_cash_usd"],"2015-12-31")
    for arm in ARMS:
        data,warnings=build_backtest_report_data(result=result[arm],result_path=root/"python"/(job_name((arm,5,0))+".json"),
            split_date=p["evaluation_start"],benchmark_name=LABELS["F3"],benchmark_nav_series=result["F3"]["nav_series"],
            extra_benchmarks=[dict(id=s,name=LABELS[s],nav_series=result[s]["nav_series"]) for s in ARMS if s!=arm and s!="F3"],
            market_prices={s:{d:float(q["close"]) for d,q in v.items()} for s,v in quotes[arm].items()},
            market_fx_rates={r["date"]:1. for r in economics[arm]["nav"]})
        flow=["Pinned audited adjusted histories; verified hashes, identity and complete common calendar",
              "XOP excluded; issuer, EIA, CFTC and holdings features excluded from historical decisions"]
        if arm.startswith("RP"):
            flow += ["Original 12 ETFs"+(" plus XLE and XLB" if arm=="RP14" else ""),
                     "Monthly decision using previous completed close; inverse 63-session price volatility",
                     "45% target cap and 2% cash floor; no volume, model, ranking or fundamental signal"]
        elif arm=="F3":
            flow += ["Replay the exact frozen app F3 targets; original 12 ETFs and inherited model schedules",
                     "Original positive 252-session momentum and price/volume top-6 selection",
                     "Weak breadth: qualified IEF/TLT/GLD at incoming weights, remainder cash",
                     "Rolling XGBoost, relative/adaptive, lag-20 activity and USD layers preserve reduced budget"]
        else:
            flow += ["Invest once in URTH at the first scheduled session; no rebalancing"]
        flow += ["Next-session open fills; whole adjusted units, 5bp costs and zero-interest residual cash",
                 "Daily held weights and USD NAV from fills; matched benchmarks; no promotion or execution authority"]
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 '+str(len(flow)*65+10)+'">'
        for i,line in enumerate(flow):
            svg+=f'<rect x="5" y="{i*65+5}" width="1090" height="55" rx="8" fill="#e9f1f5"/><text x="18" y="{i*65+37}" font-family="sans-serif" font-size="13">{i+1}. {html.escape(line)}</text>'
        svg+='</svg>'
        data.update(title=LABELS[arm]+" · finite universe control",accountingCurrency="USD",
            database="Published audited histories",allocationSource="Reconstructed from simulated fills",
            splitLabel="Previously inspected chronological boundary",sampleLabels={"in_sample":"2016–2020 retrospective","out_of_sample":"2021 onward retrospective"},
            decisionDiagrams=[dict(title="Complete decision flow",svg=svg)],strategyDefinition=dict(id=arm,protocol=p),
            warnings=[*warnings,*p["limitations"],
                "The chart includes initial capital on 2015-12-31. Its calendar annualization includes those four extra days; the frozen study table annualizes from the first simulated session, 2016-01-04."])
        (output/"reports"/(arm+".html")).write_text(render_backtest_report_html(data),encoding="utf8")
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for arm in ARMS:
        nav=np.array([float(r["nav"])/1e6 for r in economics[arm]["nav"]]);days=[date.fromisoformat(r["date"]) for r in economics[arm]["nav"]]
        axes[0].plot(days,nav,label=arm);axes[1].plot(days,nav/np.maximum.accumulate(np.maximum(nav,1))-1)
    axes[0].legend(ncol=4);axes[0].set_ylabel("Value / initial USD");axes[1].set_ylabel("Drawdown");axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle("XLE/XLB universe control · same sizing · USD · 5bp costs · retrospective")
    fig.tight_layout();fig.savefig(output/"comparison.png",dpi=150);plt.close(fig)
    rows=[]
    for arm in ARMS:
        s=report["results"][job_name((arm,5,0))]
        rows.append(f'<tr><td><a href="reports/{arm}.html">{html.escape(LABELS[arm])}</a></td><td>{s["cagr"]:.2%}</td><td>{s["sharpe_zero_cash"]:.3f}</td><td>{s["calmar"]:.3f}</td><td>{s["max_drawdown"]:.2%}</td></tr>')
    body='<!doctype html><html><head><meta charset="utf-8"><title>Energy/materials universe control</title><style>body{font:16px system-ui;margin:32px auto;max-width:1200px;padding:0 20px;color:#233748;background:#f6f8fa}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:right;border-bottom:1px solid #ddd}td:first-child,th:first-child{text-align:left}img{width:100%}li{margin:10px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#17549d}</style></head><body><h1>Energy/materials universe control</h1>'
    body+=f'<p>{p["start"]}–{p["end"]} · USD · 5bp costs · zero-interest cash · retrospective research</p><p><strong>Disposition: {html.escape(report["outcome"].replace("_"," "))}.</strong> This measures the effect of adding XLE/XLB under the same inverse-volatility sizing. It does not test expanded F3 signals. XOP remains quarantined; account trading permission remains unverified.</p>'
    body+='<table><tr><th>Complete strategy report</th><th>CAGR</th><th>Sharpe (zero RF)</th><th>Calmar</th><th>Max drawdown</th></tr>'+''.join(rows)+'</table><img src="comparison.png" alt="Matched portfolio values and drawdowns">'
    body+='<h2>Predeclared acceptance checks</h2><ul>'+''.join('<li>'+html.escape(k.replace('_',' '))+': '+('pass' if v else 'fail')+'</li>' for k,v in report['checks'].items())+'</ul>'
    body+='<h2>Paired block uncertainty</h2><p>Changes are expanded minus original universe. All 95% intervals include zero; 10,000 draws per block length. Annualized mean monthly return differs from CAGR.</p><table><tr><th>Block months</th><th>Mean return change (95% CI)</th><th>p-value</th><th>Sharpe change (95% CI)</th><th>Calmar change (95% CI)</th></tr>'
    for block,v in sorted(report['inference'].items(),key=lambda pair:int(pair[0])):
        m=v['means'][0];s=v['ratios']['sharpe'];c=v['ratios']['calmar_252']
        body+=f'<tr><td>{block}</td><td>{m["mean_annual"]:.2%} ({m["ci95"][0]:.2%}, {m["ci95"][1]:.2%})</td><td>{m["p"]:.3f}</td><td>{s["difference"]:.3f} ({s["ci95"][0]:.3f}, {s["ci95"][1]:.3f})</td><td>{c["difference"]:.3f} ({c["ci95"][0]:.3f}, {c["ci95"][1]:.3f})</td></tr>'
    body+='</table><p>Calmar bootstrap uses 252-session annualization; the primary full-period table uses calendar years. The complete reports also show the pre-trade initial-capital date, 2015-12-31.</p>'
    body+='<h2>Interpretation and remaining gates</h2><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in p["limitations"])+'</ul></body></html>'
    (output/"index.html").write_text(body,encoding="utf8")
    # Presentation corrections are separate from the frozen calculation source.
    # Retain the exact changed renderer modules to reproduce this report edition.
    from pathlib import Path
    from systematic_trading.web import asset_names
    (output/"presentation_source").mkdir(exist_ok=True)
    for source in [Path(__file__),Path(asset_names.__file__)]:
        (output/"presentation_source"/source.name).write_bytes(source.read_bytes())
    write_json(output/"receipt.json",dict(study=str(root),protocol_sha256=sha256(root/"protocol.json"),report_sha256=sha256(root/"report.json"),
        files={f.relative_to(output).as_posix():sha256(f) for f in output.rglob("*") if f.is_file() and f.name!="receipt.json"}))
    return str((output/"index.html").resolve())
