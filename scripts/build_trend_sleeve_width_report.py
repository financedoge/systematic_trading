"""Three-width comparison with all historical ranks and ETF fill inspectors."""
import base64
import copy
import gzip
import json
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import research_trend_sleeve_width as w
import research_trend_sleeve_portfolio as s
from build_trend_sleeve_portfolio_report import table,pct,num,chart


def main():
    old=s.read(s.OUT/'results.json');new=s.read(w.OUT/'results.json')
    rows=[dict(r,n=15 if r['arm']!='all' else 'Full') for r in old]+new
    paths=json.loads(gzip.decompress((s.OUT/'paths.json.gz').read_bytes()));paths.update(json.loads(gzip.decompress((w.OUT/'paths.json.gz').read_bytes())))
    d0=json.loads(gzip.decompress((s.OUT/'detail.json.gz').read_bytes()));d1=json.loads(gzip.decompress((w.OUT/'detail.json.gz').read_bytes()))
    a0=s.read(s.OUT/'attribution.json');a1=s.read(w.OUT/'attribution.json')
    payload=json.loads(gzip.decompress((s.OUT/'report-data.json.gz').read_bytes()));width_data={}
    for n in (15,20,30):
        pd={};ad={}
        for era in ('late','early'):
            for arm in ('equal','risk','all'):
                if n==15 or arm=='all':z=d0[f'{era}_{arm}_c5d0'];a=a0[f'{era}_{arm}_c5d0']
                else:z=d1[f'{era}_{arm}_n{n}_c5d0'];a=a1[f'{era}_{arm}_n{n}_c5d0']
                pd[f'{era}_{arm}_c5d0']={k:z[k] for k in ('symbols','decisions','ranks','fills')};ad[f'{era}_{arm}_c5d0']=a
        width_data[str(n)]=dict(portfolio=pd,attribution=ad)
    payload['width_data']=width_data;payload['portfolio']=width_data['30']['portfolio'];payload['attribution']=width_data['30']['attribution']
    for era in ('late','early'):
        ds=np.array(paths[era+'_days'],dtype='datetime64[D]');fig,ax=plt.subplots(3,1,figsize=(13,10),sharex=True)
        colors={15:'#b87436',20:'#9a6aa5',30:'#137e79','Full':'#466eb7'}
        for kind,axis in [('equal',ax[0]),('risk',ax[1])]:
            for n in (15,20,30,'Full'):
                key=f'{era}_all_c5d0' if n=='Full' else f'{era}_{kind}_c5d0' if n==15 else f'{era}_{kind}_n{n}_c5d0'
                nav=np.array(paths[key]);axis.plot(ds,nav*100,color=colors[n],label='Full pool equal' if n=='Full' else f'N={n}',lw=1.4)
                if kind=='equal':ax[2].plot(ds,(nav/np.maximum.accumulate(nav)-1)*100,color=colors[n],label=str(n))
            axis.legend(ncol=4,fontsize=9);axis.set_ylabel(('Equal capital' if kind=='equal' else 'Strategy risk parity')+'\nvalue / initial 100')
        ax[2].set_ylabel('Equal capital drawdown %')
        for axis in ax:axis.grid(alpha=.2)
        fig.suptitle(f'{era.title()} | N=15,20,30 versus full pool | monthly, 5 bp/side, next-open\nSame rank definition and single-ETF strategies; cash remains inside each sleeve')
        fig.tight_layout();fig.savefig(w.OUT/f'{era}-widths.png',dpi=120);plt.close(fig)
    # Native report figures for the actual N30 detractors; all ETF charts remain interactive.
    original_out=s.OUT
    try:
        s.OUT=w.OUT
        for era,arm in [('late','equal'),('early','equal'),('late','risk'),('early','risk')]:
            key=f'{era}_{arm}_n30_c5d0';symbol=a1[key][0]['symbol']
            chart(payload['charts'][symbol+'_'+era],f'{symbol}_{era}_n30_{arm}',[f for f in d1[key]['fills'] if f['symbol']==symbol])
    finally:s.OUT=original_out
    naming=lambda x:'Equal capital' if x=='equal' else 'Risk parity' if x=='risk' else 'Full pool equal' if x=='all' else x.replace('_',' ')
    columns=[('n','N',str),('arm','Weights',naming),('cumulative','Net return',pct),('cagr','CAGR',pct),('sharpe','Sharpe¹',num),('max_drawdown','Max DD',pct),('calmar','Calmar',num),('average_invested','Invested',pct)]
    body='<h1>Does N = 20 or 30 improve the portfolio?</h1><p class="subtitle">29 October 2026 · same frozen 63/252 strategy ranks · monthly membership, daily trading</p>'
    body+='<div class="verdict"><b>N=30 improves breadth and the later risk-adjusted result, but does not establish a reliable selection advantage.</b> N20 is weaker in both primary periods. N30 equal capital improves later Sharpe and drawdown, with a little less return; the earlier period still loses money. The unranked full-pool strategy remains the stronger Sharpe control in both primary periods.</div>'
    body+='<p>Only selection width changed. We kept the same ETF models, 63/252-day four-rank score, cash treatment, risk-parity estimator, costs, delay conventions and 10% dynamic trigger. This is an operator-requested extension after inspecting N15, so the comparisons are development evidence, not fresh validation or proof of an optimal N. <a href="../trend-sleeve-portfolio-20261029-v1/index.html">N15 full mathematics, original controls and diagnosis</a> · <a href="../trend-sleeve-synthesis-20261029-v1/index.html">Underlying ETF algorithm</a>.</p>'
    for era,label in [('late','1 February 2024 – 16 October 2026'),('early','4 January 2021 – 30 December 2022')]:
        primary=[r for r in rows if r['era']==era and r['cost_bp']==5 and r['delay']==0 and r['arm'] in ('equal','risk','all')]
        primary.sort(key=lambda r:({'equal':0,'risk':1,'all':2}[r['arm']],r['n'] if isinstance(r['n'],int) else 99))
        body+=f'<h2>{era.title()} chronology · {label}</h2>'+table(primary,columns)+f'<img class="figure" src="{era}-widths.png" alt="{era} width comparison"/>'
    body+='<p class="note">¹ Sharpe uses daily arithmetic net returns and √252 annualization, with a zero cash reference rate; not BIL excess. Cash earns zero. Maximum drawdown is a positive loss magnitude. Fees are 5 bp per traded side, including net allocation changes. All methods start funded after the same 252-post-fit-session warmup and mark open positions at the end without forced sale. Later models train through 2022; earlier models through 2019. Funded results exclude the 2020 crash and 2023.</p>'
    body+='<h2>What changes when the pool widens?</h2><ul><li><b>Actual invested breadth improves.</b> Later equal capital averages 8.64, 11.16 and 16.51 active ETFs for N15/20/30; earlier 7.99, 10.40 and 15.35. N30 still has about 45% later / 49% earlier capital in cash. Thirty selected strategies therefore do not mean thirty active ETF positions.</li><li><b>The broader pool dilutes concentrated gains and losses.</b> Later EWY’s net contribution falls from +6.38pp at N15 to +4.16pp at N20 and +3.18pp at N30. IAT losses become less influential, but other weak trades are admitted. More ETF names also do not eliminate overlapping equity, sector and commodity risk.</li><li><b>Risk parity gets less concentrated, but does not consistently improve returns over equal capital.</b> At N30 its maximum capital sleeve falls to 15.2% later / 16.4% earlier, versus 27.2% / 25.0% at N15. Its effective invested breadth remains only 11.78 / 10.64 because weights differ.</li><li><b>Costs fall moderately with monthly N30.</b> Equal-capital annual cost falls from 76.97 to 67.16bp later and 78.29 to 69.35bp earlier. This helps, but does not turn the earlier strategy profitable.</li></ul>'
    body+='<details><summary>Exposure, concentration and turnover by width</summary>'+table([r for r in rows if r['cost_bp']==5 and r['delay']==0 and r['arm'] in ('equal','risk','all')],
        [('era','Era',str),columns[0],columns[1],('mean_active_count','Active ETFs',lambda x:f'{x:.2f}'),('mean_effective_invested_count','Effective held breadth',lambda x:f'{x:.2f}'),('max_capital_weight','Largest sleeve',pct),('turnover_annual','Gross turnover/year',lambda x:f'{x:.2f}×'),('cost_bp_annual','Cost bp/year',lambda x:f'{x:.1f}')])+'</details>'
    gates=s.read(w.OUT/'assessment.json');gate_rows=[]
    for n in (20,30):
        for arm in ('equal','risk'):
            z=[g for g in gates if g['n']==n and g['arm']==arm];gate_rows.append(dict(n=n,arm=arm,vs15=f"{sum(g['passed'] for g in z if g['control']=='N15')}/12",vsall=f"{sum(g['passed'] for g in z if g['control']=='all')}/12"))
    body+='<h2>Does the improvement survive costs and execution delay?</h2><p>Count a comparison only when net Sharpe improves, CAGR loses no more than 1 percentage point and maximum drawdown worsens by no more than 2 points. Twelve settings are two chronologies × 5/10/20bp × zero/one extra session. These are robustness comparisons, not independent statistical trials.</p>'+table(gate_rows,[columns[0],columns[1],('vs15','Passes versus matched N15',str),('vsall','Passes versus full pool',str)])
    body+='<p>N30 equal capital passes 8/12 comparisons against N15, but 0/12 against full-pool sleeves. Its 5bp return moves 16.72% → 16.46% later and −4.03% → −0.03% earlier when execution is delayed one additional session. Later timing becomes more stable; earlier timing still matters materially.</p>'
    stress_cols=[('era','Era',str),columns[0],columns[1],('cost_bp','bp/side',str),('delay','Extra days',str),*columns[2:6]]
    body+='<details><summary>All monthly cost and delay results</summary>'+table([r for r in rows if r['arm'] in ('equal','risk','all')],stress_cols)+'</details>'
    body+='<details><summary>Separate dynamic-selection control</summary><p>Monthly OR cash-inclusive L1 target change ≥10%, comparing latest theoretical target with the last adopted one. A single equal sleeve’s ETF/cash flip contributes 2/N: 13.33% at N15, 10% at N20, 6.67% at N30. N30 reduces later equal-capital adoption events to407, versus538 at N15 and561 at N20, but still far more than33monthly dates.</p><p>At5bp N30dynamic equal capital returns17.57%later/−3.20%earlier, Sharpe.928/−.178. Its annual costs are103/104bp versus67/69monthly; at20bp returns fall to9.32%/−9.19% without extra delay. This small primary gain does not establish a consistently better clock.</p>'+table([dict(r,arm=r['arm'].replace('_dynamic','')) for r in rows if r['arm'] in ('equal_dynamic','risk_dynamic')],stress_cols)+'</details>'
    body+='<h2>What if we simply rank and hold the ETF prices?</h2><p>The same four-metric rank on adjusted ETF returns, always invested in the chosen ETFs, earns substantially more in the later period. It also has higher drawdown. This is a useful lead for a future controlled test: the current trading sleeves and their substantial cash exposure may be giving up too much upside. Price ranks plus daily strategy trading would be a new ablation; these numbers do not yet isolate the ranking source from the exit/cash rule.</p>'+table([r for r in rows if r['arm']=='raw_momentum' and r['cost_bp']==5 and r['delay']==0],
        [('era','Era',str),columns[0],*columns[2:7]])
    body+='<h2>Inspect the actual allocations and weakest constituents</h2><p>For N30 equal capital, the largest detractors are <b>CPER −0.96pp later</b> and <b>PPLT −1.19pp earlier</b>. N30 risk parity’s largest detractors are <b>WEAT −0.90pp</b> and <b>GLD −0.78pp</b>. All contributions include actual fills and fees. The weakest continuously monitored shadow strategies remain TLT later / MCHI earlier because their trading algorithms did not change.</p>'
    body+='<div class="controls"><label>Selection width <select id="width"><option>15</option><option>20</option><option selected>30</option></select></label></div>'
    oldhtml=(s.OUT/'index.html').read_text(encoding='utf-8')
    inspector=oldhtml[oldhtml.index('<h2>Inspect ranks, allocations'):oldhtml.index('<h2>Costs, delay')]
    a=inspector.index('<h2>Weakest cases');b=inspector.index('<div class="controls"><label>Era <select id="era">',a)
    inspector=inspector[:a]+'<h2>Every ETF: dated price, state, stop and fill chart</h2><p>Orange circles use the width and weighting method selected above. The unselected virtual strategy keeps running; its green/red markers may differ from the funded portfolio.</p>'+inspector[b:]
    inspector=re.sub(r'<details><summary>Ready-to-open static weakest charts</summary>.*?</details>','',inspector,flags=re.S)
    inspector=inspector.replace('N15 equal-capital','selected portfolio').replace('Worst N15 equal contributor','Worst portfolio contributor').replace('N15','selected portfolio')
    body+=inspector
    body+='<details><summary>N30 weakest-contributor static charts</summary>'+''.join(f'<img class="figure" src="{name}.png" alt="N30 portfolio detractor chart"/>' for name in ('CPER_late_n30_equal','PPLT_early_n30_equal','WEAT_late_n30_risk','GLD_early_n30_risk'))+'</details>'
    body+='<h2>Conclusion and limits</h2><p><b>N30 equal capital is the more diversified reference to carry forward if we continue this family, but it is not an established winner.</b> N20 offers no primary improvement, and unranked full-pool sleeves still provide better primary Sharpe. Increasing N treats concentration; it does not repair weak prediction of future strategy returns or failed trend trades.</p><p>Before another parameter search, the more informative next test is to separate the rank source from the daily trading layer: same N30, strategy-based versus price-based ranks, with and without the frozen daily gate, all with matched cash treatment. That is a proposed next experiment, not a result of this one.</p><p>We added120runs using the same verified frozen shadow histories and dates. No new ETF model fitting, price fetch or width-specific tuning. Inputs are the published audited batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd; adjusted OHLC for returns and separately audited raw volume for chart context. Historical publication-vintage and retrospective cohort limitations remain. This study does not model tax, FX, actual market impact or intraday stops; zero cash interest understates funded cash yield. Rank histories include prior selection-sensitive model research. Both eras and now these widths are development evidence.</p><p>Native fixtures check multiasset accounting of exported execution-open target oracles, not independent inference or real-time execution. Fractional portfolio cash/share ledgers and contribution checks are separate. No recurring monitoring, broker, approval or live changes.</p><p><a href="protocol.json">Extension protocol</a> · <a href="results.json">All new results</a> · <a href="assessment.json">All comparison guards</a> · <a href="validation.json">Ledger validation</a> · <a href="native-checks.json">Native checks</a> · <a href="qa.json">Report QA</a></p>'
    js=(s.OUT/'controls.js').read_text(encoding='utf-8')
    js=js.replace("[el('era').value+'_equal_c5d0']","[el('era').value+'_'+el('parm').value+'_c5d0']")
    js+='\nfunction selectWidth(){const v=DATA.width_data[el("width").value];DATA.portfolio=v.portfolio;DATA.attribution=v.attribution;portfolioDates();render()}\nel("width").value="30";el("width").addEventListener("change",selectWidth);el("parm").addEventListener("change",()=>{portfolioDates();render()});selectWidth();el("etf").value=DATA.attribution[el("era").value+"_"+el("parm").value+"_c5d0"][0].symbol;choose();'
    (w.OUT/'controls.js').write_text(js,encoding='utf-8');s.gzwrite(w.OUT/'report-data.json.gz',payload)
    encoded=base64.b64encode((w.OUT/'report-data.json.gz').read_bytes()).decode()
    loader="(async()=>{try{const raw=Uint8Array.from(atob('"+encoded+"'),c=>c.charCodeAt(0));const text=await new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream('gzip'))).text();globalThis.DATA=JSON.parse(text);"+js+"}catch(e){document.getElementById('readout').textContent='Inspector could not load: '+e.message;console.error(e)}})();"
    css=oldhtml[oldhtml.index('<style>')+7:oldhtml.index('</style>')]
    (w.OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>N15 vs N20 vs N30 portfolio backtest</title><style>'+css+'</style><body>'+body+'<script>'+loader+'</script></body></html>',encoding='utf-8')
    print('Width report built: three widths, all100ETF/era charts',flush=True)


if __name__=='__main__':main()
