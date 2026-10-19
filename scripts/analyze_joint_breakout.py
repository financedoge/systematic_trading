"""Descriptive diagnostics only; never changes numeric fits or 2023 choices."""
from pathlib import Path
import json
import numpy as np
from run_joint_breakout import ROOT,PUBLIC,read,write,digest,asset,History
from evaluate_joint_breakout import table,pct,number
from systematic_trading.research.range_joint import v1_anchor,describe,WINDOWS


def main():
    result=read(PUBLIC/'summary.json');variants=read(ROOT/'variants.json')['variants'];choices=result['choices']
    names=('raw','moderate','strong','stable','local_stability','shrinkage','shared','selected')
    qualified=[s for s in choices if 'raw' in variants[s]];rows=[];diagnostics={}
    for name in names:
        before=[];validation=[];after=[];cagrs=[];bhwins=0;positive=0
        for s in qualified:
            mm=result['metrics'][s];v=read(ROOT/'validation'/f'{s}.json')
            if name=='selected':
                choice=choices[s];key=mm['selected_key'];vkey=v['selected']
                isrow=variants[s].get(choice['variant'],{}).get('IS',{}).get('scenarios',{}).get('5:0')
            else:
                key=name+'_event_c5d0';vkey=name+'_event';isrow=variants[s][name]['IS']['scenarios']['5:0']
            if isrow:
                before.append(isrow['components']['moderate'])
            validation.append(v['rows'][vkey]['scenarios']['5:0']['components']['moderate'])
            r=mm['rows'][key];after.append(r['components']['moderate']);cagrs.append(r['metrics']['cagr'])
            positive+=r['components']['moderate']>0
            bhwins+=r['metrics']['cagr']>mm['rows']['buyhold_event_c5d0']['metrics']['cagr']
        diagnostics[name]=dict(IS_median_utility=float(np.median(before)),IS_observations=len(before),
            validation_median_utility=float(np.median(validation)),OOS_median_utility=float(np.median(after)),
            OOS_median_cagr=float(np.median(cagrs)),OOS_positive_utility=int(positive),OOS_beats_BH=int(bhwins),cohort=len(qualified))
        d=diagnostics[name];rows.append([name,number(d['IS_median_utility']),number(d['validation_median_utility']),number(d['OOS_median_utility']),
                                      pct(d['OOS_median_cagr']),d['OOS_positive_utility'],d['OOS_beats_BH']])
    range_rows=[];ranges={}
    for s in ('GLD','USO','SOXX'):
        a=asset(s);h=History.build(a);c=choices[s]
        if c['parameters'] is not None:
            p=np.array(c['parameters']);t=h.signals(p);tail=int(p[5]);conf=int(p[13])
        elif c['variant']=='v1':
            p=v1_anchor();t=h.signals(p);tail=1;conf=3
        else:
            from calibrate_range_breakout import selected_signal
            ident=read('var/research/range-breakout-20261018-v2/selection.json')['selections'][s]['id']
            t=selected_signal(a,ident,details=True);tail=1;conf=3;p=None
        entries=np.flatnonzero(t['active'] & ~np.r_[False,t['active'][:-1]] & (a['days']>='2024-01-01'))
        data=[]
        for i in entries:
            L=int(t['duration'][i]);j=WINDOWS.tolist().index(L);cross=i-conf+1
            upper=h.arrays[4][tail,j,cross];lower=h.arrays[5][tail,j,cross]
            data.append(dict(confirmation=str(a['days'][i]),range_sessions=L,band_width=float(upper/lower-1)))
        ranges[s]=data
        range_rows.append([s,len(data),number(np.median([x['range_sessions'] for x in data])) if data else '—',
                           pct(np.median([x['band_width'] for x in data])) if data else '—',pct(describe(p)['absolute_width']) if p is not None and p[2]==0 else 'relative / v2'])
    guards=sum(v['guard_pass'] for v in choices.values())
    write(PUBLIC/'diagnostics.json',dict(variant_comparison=diagnostics,selected_entry_ranges=ranges,validation_guard_pass=guards,
        source_sha256=digest(Path(__file__)),summary_sha256=digest(PUBLIC/'summary.json')))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xx=np.arange(len(names));fig,ax=plt.subplots(figsize=(12,4),layout='constrained')
    for offset,key,label,color in [(-.24,'IS_median_utility','IS','#6e98b3'),(0,'validation_median_utility','2023','#b98b58'),(.24,'OOS_median_utility','2024+','#147e89')]:
        ax.bar(xx+offset,[diagnostics[n][key] for n in names],width=.24,label=label,color=color)
    ax.axhline(0,color='#69737c',lw=.8);ax.set_xticks(xx,names,rotation=20);ax.set_ylabel('Median common moderate utility')
    ax.set_title('From fitting to later periods | 50 history-qualified ETFs');ax.legend(ncol=3);ax.spines[['top','right']].set_visible(False)
    fig.savefig(PUBLIC/'overfit.png',dpi=125);plt.close(fig)
    block=f'''<section id="findings"><h2>What this experiment establishes</h2><p><b>The broad joint search does not validate a general breakout strategy.</b> The sealed2023 selection produces−0.19% annualized for GLD and−4.11% for USO in2024+, versus27.75% and36.67% for their buy-hold controls. SOXX is stronger:42.72% versus40.83%, with−28.46% drawdown versus−40.29%. All three case selections failed the2023 return/drawdown guards; they remain descriptive candidates.</p>
    <p>Selection is itself a source of instability. USO's raw/moderate joint fits earn8.02%/11.11% OOS, but2023 prefers the older v2 rule and its later result is negative. Gold's shared/monthly rule earns19.93% and v2 earns27.71%, while the2023-selected local/monthly fit misses the rally. Those alternatives are reported comparisons, not replacements chosen after seeing OOS.</p>
    <p>Equal-budget active sleeves earn7.24% with event timing or8.39% monthly, below matched momentum at10.11%/11.94%. The inherited inverse-vol trading sleeve earns2.75% with a Sharpe of3.58, but is dominated by BIL and cash. Its20% FR25 tilt earns16.24%, essentially the matched blend's16.20% and below FR25's19.64%. A high ratio alone is not sufficient evidence.</p>
    <p>Gold's selected initial stop is6.10 ATR, but its fitted no-follow-through rule demands a2.39 ATR gain within five sessions. All six completed OOS signal exits come from that time rule. This explains why widening the initial stop alone does not repair the missed rally. The monthly clock often never adopts these short-lived signals.</p>
    <h3>Regularization and selection did not reliably generalize</h3><p>{guards}/52 selections pass the2023 guards. The table uses the same50 history-qualified ETF cohort. Fixed variants use event timing; “selected” uses the chosen clock, and its IS median excludes legacy choices without a v3 IS record. Periods differ in market regimes and buy-hold returns, so deterioration is consistent with overfitting or regime change, not proof of one cause. The only positive family-adjusted bounds versus v1 are BIL and SHY; none beats buy-hold at that family confidence level.</p><img src="overfit.png" alt="Median joint utility in fitting, validation and OOS">'''+table(
        ['Variant','IS median utility','2023 median utility','OOS median utility','OOS median CAGR','OOS utility >0','Beat BH CAGR'],rows)+'''
    <h3>Did the fitted rule retain the tight-range premise?</h3><p>Not consistently. Gold's raw and moderate IS fits permit widths near87–90%, and the shared rule selected for SOXX permits96%; other filters may then do most of the work. Optimizing profit does not ensure the optimizer preserves the motivating economic story. The table describes fresh selected-signal confirmations during OOS; it excludes an inherited position at the boundary and does not claim every confirmation produces a monthly fill.</p>'''+table(['ETF','New confirmations','Median range sessions','Median actual band width','Absolute width cap'],range_rows)+'''
    <p><b>Next research design:</b> select regularization using several rolling validation windows entirely before2023, reserve2023 as a final model check, and reduce or pool weakly identified dimensions. Test a structural compression constraint separately from a general trend-following rule. Keep the present2024+ results as used evidence; further changes require later data or another explicitly retrospective study. Soft stop penalties help define preferences but cannot make the observed one-year selector reliable.</p><p><a href="diagnostics.json">Diagnostic values and provenance</a></p></section>'''
    p=PUBLIC/'index.html';doc=p.read_text(encoding='utf-8')
    if 'id="findings"' in doc:
        start=doc.index('<section id="findings"');end=doc.index('</section>',start)+len('</section>');doc=doc[:start]+doc[end:]
    doc=doc.replace('<section><h2>The mathematics</h2>',block+'<section><h2>The mathematics</h2>')
    p.write_text(doc,encoding='utf-8')
    print(json.dumps(diagnostics,indent=2))


if __name__=='__main__':
    main()

