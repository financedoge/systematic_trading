"""Descriptive replay of one inspected loss; no fit or strategy modification."""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import research_reset_policy as study

OUT = ROOT / 'research/inda-trade-20261027-v1'


def main():
    fits, calibration, initial = study.verified()
    chart_path = study.OUT / 'chart-data.json.gz'
    validation = json.loads((study.OUT / 'validation.json').read_text())
    assert study.prior.study.digest(chart_path) == validation['chart_sha256']
    cached = json.loads(gzip.decompress(chart_path.read_bytes()))['INDA_late']
    fit = fits['INDA']['late']
    _, _, first, last = next(e for e in study.ERAS if e[0] == 'late')
    f = study.prior.model.Features.build(study.prior.study.load_asset('INDA')).truncated(last)
    f.hmm_models = fit['hmms']
    cl = study.prior.model.classify(f, fit['selected']['selected']['parameters'])
    start = int(np.searchsorted(f.days, np.datetime64(first))) - 1
    sim = study.model.simulate(f, cl, initial['INDA']['late']['states'],
                               calibration['INDA']['late'], start=start,
                               arm='regime_reset', cost_bp=5, delay=0)
    trade = next(e for e in sim['episodes'] if str(f.days[e['entry_index']]) == '2024-12-03')
    saved = next(e for e in cached['arms']['regime_reset']['trades'] if e['entry_date'] == '2024-12-03')
    for key in ('entry_index', 'exit_index', 'entry_signal', 'exit_signal', 'entry', 'exit_price', 'net_return'):
        assert trade[key] == saved[key], (key, trade[key], saved[key])
    ix = np.searchsorted(f.days, np.array(cached['days'], dtype='datetime64[D]'))
    expected = np.array(cached['arms']['regime_reset']['nav'], float) / 100
    nav_error = float(np.nanmax(np.abs(sim['nav'][ix] - expected)))
    assert nav_error < 1e-12
    fee = .0005
    a, b = trade['entry_index'], trade['exit_index']
    rows = []
    for t in range(int(np.searchsorted(f.days, np.datetime64('2024-11-01'))), b + 2):
        rows.append(dict(day=str(f.days[t]), open=f.open[t], close=f.close[t],
                         volume=f.volume[t], down=cl['fast_probability'][t, 0],
                         neutral=cl['fast_probability'][t, 1], up=cl['fast_probability'][t, 2],
                         slow_down=cl['slow_probability'][t, 0],
                         slow_up=cl['slow_probability'][t, 2],
                         fast_slope=cl['fast_slope'][t], slow_slope=cl['slow_slope'][t],
                         transition=sim['regime_change'][t], stop=sim['stop'][t],
                         policy=sim['policy'][t], exit_threshold=sim['exit_threshold'][t],
                         net_mark=f.close[t] / trade['entry'] * (1-fee)/(1+fee)-1))
    # Illustrations declared before replay: no grid search or threshold selection.
    rules = [('up_below_20pct_two_closes', cl['fast_probability'][:, 2] < .2),
             ('negative_fast_slope_two_closes', cl['fast_slope'] < 0)]
    illustrations = []
    for label, condition in rules:
        count = 0
        for t in range(a, b):
            count = count + 1 if condition[t] else 0
            if count == 2:
                illustrations.append(dict(rule=label, known=str(f.days[t]),
                    fill=str(f.days[t+1]), price=f.open[t+1],
                    net_return=f.open[t+1]/trade['entry']*(1-fee)/(1+fee)-1))
                break
    held = cl['fast_probability'][a:b]
    result = dict(identity=OUT.name, purpose='Inspected incident; illustrations are not validation or tuned candidates',
        parent_protocol=study.prior.study.digest(study.OUT/'protocol.json'),
        published_inputs=json.loads((study.OUT/'protocol.json').read_text())['published_inputs'],
        parent_chart_hash=validation['chart_sha256'], replay_nav_error=nav_error,
        trade=saved, policy=sim['parameters'][trade['entry_policy']], sigma=cl['sigma'],
        hmm=f.hmm_models['hmm'], illustrations=illustrations,
        max_down_while_held=float(held[:, 0].max()),
        max_down_date=str(f.days[a+int(np.argmax(held[:, 0]))]),
        close_mfe=float(np.max(f.close[a:b])/trade['entry']-1),
        rows=rows)
    OUT.mkdir(exist_ok=True)
    study.write(OUT/'trace.json', result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    days=np.array([r['day'] for r in rows],dtype='datetime64[D]')
    data=lambda key:np.array([r[key] for r in rows],float)
    fig,axs=plt.subplots(4,1,figsize=(13,11),sharex=True,layout='constrained',height_ratios=[2,1,.7,.6])
    axs[0].plot(days,data('close'),label='Adjusted close',color='#183e53')
    axs[0].plot(days,data('stop'),label='Actual adopted stop',color='#b64f61')
    axs[0].scatter(f.days[a],trade['entry'],marker='^',s=85,color='#008675',label='Actual buy')
    axs[0].scatter(f.days[b],trade['exit_price'],marker='v',s=85,color='#b64f61',label='Actual sell: -10.82%')
    axs[0].axvline(np.datetime64(illustrations[0]['fill']),color='#c78b28',ls='--',label='Illustrative thesis exit')
    axs[0].legend(loc='lower left',fontsize=9,ncol=2);axs[0].set_ylabel('Adjusted USD')
    for key,color in [('up','#008675'),('neutral','#a28b4a'),('down','#b64f61')]:
        axs[1].plot(days,data(key),label=key,color=color)
    axs[1].axhline(.7,ls=':',color='#b64f61',label='Required down probability: 70%')
    axs[1].axhline(.2,ls=':',color='#008675',label='Illustrative up floor: 20%')
    axs[1].legend(loc='center right',fontsize=9);axs[1].set_ylim(0,1);axs[1].set_ylabel('HMM state probabilities')
    axs[2].plot(days,data('fast_slope')*100,label='Fast log-price slope',color='#008675')
    axs[2].plot(days,data('slow_slope')*100,label='Slow log-price slope',color='#5c6bb0')
    axs[2].axhline(0,color='#888',lw=.8);axs[2].legend(fontsize=9);axs[2].set_ylabel('Slope (% / session)')
    axs[3].bar(days,data('volume')/1e6,color='#98aab4');axs[3].set_ylabel('Raw volume (m)')
    for ax in axs:
        ax.grid(alpha=.15)
        ax.axvspan(f.days[a],f.days[b],alpha=.035,color='#008675')
    axs[-1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO,interval=2))
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(axs[-1].get_xticklabels(),rotation=35,ha='right')
    fig.suptitle('INDA: the up-state thesis faded in December; the exit waited until February\nFrozen-policy replay; illustrative early exit is not an independently validated strategy')
    fig.savefig(OUT/'incident.png',dpi=130);plt.close(fig)
    pct=lambda v:f'{100*v:.2f}%'
    detail=''.join('<tr><td>'+r['day']+'</td>'+''.join(f'<td>{v}</td>' for v in
        (f"{r['close']:.3f}",pct(r['up']),pct(r['neutral']),pct(r['down']),
         pct(r['slow_down']),f"{100*r['fast_slope']:.3f}%",'—' if not np.isfinite(r['stop']) else f"{r['stop']:.3f}"))+'</tr>' for r in rows)
    alternatives=''.join(f"<tr><td>{e['rule'].replace('_',' ')}</td><td>{e['known']}</td><td>{e['fill']}</td><td>{pct(e['net_return'])}</td></tr>" for e in illustrations)
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>INDA: a reversal thesis that failed</title><style>body{max-width:1150px;margin:35px auto;padding:0 20px;font:17px/1.55 system-ui;color:#173d54;background:#f7f9fb}img{width:100%}h1,h2{line-height:1.2}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px;border-bottom:1px solid #d9e2e8;text-align:right}th:first-child,td:first-child{text-align:left}.box{background:white;padding:16px;border-left:4px solid #008675;margin:18px 0}.formula{font-family:serif;font-size:20px;padding:12px;background:white}.scroll{overflow:auto}a{color:#006c73}</style>
<h1>INDA: the reversal thesis failed well before the stop</h1><p>27 October 2026 · Review of the 3 December 2024–27 February 2025 trade · No new strategy fit</p>
<p class="box"><b>The model noticed the loss of upward momentum, but the exit contract did not act on it.</b> It required a strong down-state classification or a distant protective stop. The long-trend warning was also disabled in this ETF's selected policy.</p>
<h2>What the algorithm actually did</h2>
<p>The 2 December close had fast HMM up probability 68.91%, above the 60% entry threshold, and a positive fast slope. That generated the 3 December open purchase at adjusted $54.575. It did not require an explicit downward-to-upward transition. The slow model already assigned 81.64% probability to a downward slope, but the selected policy had context=false. This was effectively a countertrend rebound trade with no stricter countertrend exit.</p>
<div class="formula">Entry: p<sup>fast</sup><sub>up,t</sub> ≥ 0.60 and b<sup>fast</sup><sub>t</sub> &gt; 0.<br>Actual exit: p<sup>fast</sup><sub>down,t</sub> ≥ 0.70 or C<sub>t</sub> &lt; S<sub>t</sub>; execute at the next open.</div>
<p>The up-state probability declined from 91.07% on 6 December to 15.16% on 16 December, 3.83% on 17 December and 0.42% on 18 December. On the latter date the model assigned 99.21% to its neutral state. Neutral was not an exit. Down probability peaked at only 66.30% on 15 January during the holding period, never reaching 70%.</p>
<p>That classification has a concrete cause: the trained down state's mean fast log-price slope corresponds to approximately −0.823% per session; neutral is centered at zero with about 0.264% slope standard deviation and a 93.71% self-transition probability. Moderate persistent declines can remain neutral. These are emission statistics of a filtered slope, not forecasts of daily ETF returns. The state names do not guarantee economically sensible corridor recognition.</p>
<p>The initial protection distance was 7.5 × training daily volatility (1.4995%), or 11.25% of the entry price. The initial stop was $48.437; the modest early rally raised it to $49.242. The highest close gained only 1.47% from entry. The stop stayed there until the 26 February close ($49.020) breached it; the next open sold at $48.720 for −10.82% net. The 14 February large-loss warning reset learning statistics but retained the position, policy and stop.</p>
<p>The previous chart's fast-up curve is a <em>state</em> probability. Its separate transition curve measures any state change. Neither is a calibrated probability that the original trade thesis is true, and the transition reset was not a sell instruction.</p>
<a href="incident.png"><img src="incident.png" alt="INDA price, stops, three HMM state probabilities, fast and slow slopes, and raw volume"></a>
<h2>Two diagnostic earlier exits</h2><p>These rules illustrate when information was available. Thresholds were not optimized, but this is an already-inspected losing trade, so the apparent improvement is not out-of-sample evidence. Each row retains the original entry, charges 5 bp per side and sells next open. Subsequent re-entry and portfolio effects are not simulated.</p>
<table><tr><th>Illustration</th><th>Known at close</th><th>Next-open sale</th><th>Trade net return</th></tr>__ALTERNATIVES__</table>
<h2>Three improvements to investigate</h2>
<p><b>1. Monitor whether the entry thesis remains supported.</b> For a rebound against a slow downtrend, a persistent loss of up-state support should permit exit without waiting for strong down-state confidence. An initial test could use two closes below an up-probability floor; require stronger price confirmation or allow more time in a slow uptrend. Fit and assess the context thresholds on training data across the full pool. Permit re-entry on genuinely renewed evidence so an early exit does not permanently exclude a GLD-like trend.</p>
<div class="formula">Illustration: τ = inf{t ≥ entry : p<sup>fast</sup><sub>up,t−1</sub> &lt; 0.20 and p<sup>fast</sup><sub>up,t</sub> &lt; 0.20}.</div>
<p><b>2. Compare the trade's predictions with a failed-reversal alternative daily.</b> Register an upward-continuation predictive model at entry and a range/down alternative. Use each day's previously forecast return distribution; accumulate evidence for the alternative. Stop when the evidence exceeds a boundary selected before evaluation. This can detect a persistent moderate decline even when the existing HMM calls it neutral. Improve the model's shallow-decline representation as part of that work.</p>
<div class="formula">L<sub>t</sub> = Σ<sub>s=entry…t</sub> log[q<sub>failed</sub>(r<sub>s</sub> | F<sub>s−1</sub>) / q<sub>up</sub>(r<sub>s</sub> | F<sub>s−1</sub>)]; exit when L<sub>t</sub> ≥ h.</div>
<p>This is a proposed predictive likelihood-ratio monitor, not an implemented formal significance test. Do not multiply successive HMM posteriors as independent evidence: they reuse highly correlated price history. A formal repeated-testing guarantee requires a correctly specified conditional null or suitable confidence-sequence/e-process assumptions, handling serial dependence and entry selection. An ordinary 5% test repeated daily does not supply that guarantee. See <a href="https://arxiv.org/abs/1810.08240">Howard et al., time-uniform confidence sequences</a>.</p>
<p><b>3. Give the reversal a separate price-risk boundary.</b> At entry, record the support/reclaim level whose failure invalidates the setup, using only then-available observations, and combine a volatility buffer with a maximum accepted loss. A new countertrend trade gets less room than an established uptrend. Bayesian refitting must not postpone this exit. A close-based stop still permits overnight gaps; it is not a guaranteed maximum realized loss.</p>
<div class="formula">S<sub>entry</sub> = max(P<sub>entry</sub>(1−R<sub>max</sub>), support<sub>known at entry</sub>−k·ATR<sub>prior</sub>); S<sub>t</sub> ≥ S<sub>t−1</sub>.</div>
<p>Support must lie below the entry after its buffer, otherwise reject the setup. Parameters and confirmation rules remain hypotheses. First compare the existing strategy, simple thesis invalidation, and a predictive evidence exit; keep risk and re-entry rules consistent to identify which change helps. No new full-pool test is claimed here.</p>
<details><summary>Exact daily dates, states and stop levels</summary><div class="scroll"><table><tr><th>Date</th><th>Adj. close</th><th>Fast up</th><th>Neutral</th><th>Fast down</th><th>Slow down</th><th>Fast slope/session</th><th>Stop</th></tr>__ROWS__</table></div></details>
<p>Verified parent protocol and audited input hashes. Frozen simulation reproduces the original trade exactly and cached NAV within 1.12×10<sup>−16</sup>. Forward filtering only; no new price downloads. Raw volume is descriptive only. Daily adjusted prices and the parent publication-vintage limitations remain. <a href="trace.json">Full trace and provenance</a> · <a href="../reset-policy-20261026-v1/index.html">Original full ETF report</a></p></html>'''
    (OUT/'index.html').write_text(html.replace('__ALTERNATIVES__',alternatives).replace('__ROWS__',detail),encoding='utf-8')
    study.write(OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        runner_sha256=study.prior.study.digest(Path(__file__))))
    print(json.dumps(study.clean({k:v for k,v in result.items() if k not in ('rows','hmm','published_inputs')}),indent=2))
    for row in rows:
        if row['day'] in ['2024-12-02','2024-12-06','2024-12-13','2024-12-16','2024-12-17','2024-12-18','2025-01-13','2025-02-14','2025-02-26']:
            print(json.dumps(study.clean(row)))
    print('HMM',json.dumps(study.clean(result['hmm'])))


if __name__=='__main__':main()
