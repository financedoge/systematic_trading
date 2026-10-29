"""Frozen-evidence synthesis and historical selector preview; no portfolio backtest."""
import gzip
import hashlib
import html
import io
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
OUT=ROOT/'research/trend-sleeve-synthesis-20261029-v1'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def rank_preview(charts,asof,short=63,long=252):
    """All mature strategy account returns, including zero-return cash sessions."""
    rows=[];series={};calendar=None
    for key,c in sorted(charts.items()):
        if not key.endswith('_late') or key.startswith('BIL_'):continue
        ix=[i for i,d in enumerate(c['days']) if d<=asof and c['arms']['baseline']['nav'][i] is not None]
        if len(ix)<long+1:continue
        ix=ix[-long-1:];nav=np.array(c['arms']['baseline']['nav'])[ix].astype(float)
        dates=[c['days'][i] for i in ix]
        if dates[-1]!=asof:continue
        if calendar is None:calendar=dates
        if dates!=calendar:raise ValueError('Unaligned strategy-return calendar; do not splice or fill')
        r=nav[1:]/nav[:-1]-1
        if not np.isfinite(r).all() or np.std(r,ddof=1)<=1e-12 or np.count_nonzero(abs(r)>1e-12)<2:continue
        symbol=key[:-5];series[symbol]=r
        def metrics(x):return float(np.prod(1+x)-1),float(np.sqrt(252)*x.mean()/x.std(ddof=1)) if x.std(ddof=1)>1e-12 else None
        sr,ss=metrics(r[-short:]);lr,ls=metrics(r)
        if ss is None:continue
        rows.append(dict(symbol=symbol,short_return=sr,short_sharpe=ss,long_return=lr,long_sharpe=ls,
            volatility=float(np.std(r,ddof=1)*np.sqrt(252)),active=bool(c['arms']['baseline']['held'][ix[-1]]),
            nonzero_days=int(np.count_nonzero(abs(r)>1e-12))))
    from scipy.stats import rankdata
    for k in ['short_return','short_sharpe','long_return','long_sharpe']:
        z=rankdata([r[k] for r in rows],method='average')
        for r,v in zip(rows,z):r[k+'_percentile']=float((v-1)/max(1,len(rows)-1))
    for r in rows:r['score']=sum(r[k+'_percentile'] for k in ['short_return','short_sharpe','long_return','long_sharpe'])/4
    rows.sort(key=lambda r:(-r['score'],r['symbol']))
    for j,r in enumerate(rows,1):r['rank']=j
    return rows,series


def allocation(rows,series,n,kind):
    selected=rows[:n];symbols=[r['symbol'] for r in selected];m=len(selected)
    if not m:return dict(symbols=[],weights=[],cash=1.,invested=0.,erc_error=None)
    if kind=='equal':w=np.ones(m)/m;error=None
    else:
        r=np.column_stack([series[s] for s in symbols]);sample=np.cov(r,rowvar=False,ddof=1)*252
        sample=np.atleast_2d(sample);cov=.5*sample+.5*np.diag(np.diag(sample))
        cov+=np.diag(np.maximum(0,.05**2-np.diag(cov)))
        # Convex equal-risk-budget problem; normalize its positive solution.
        b=np.ones(m)/m
        def fun(x):return .5*x@cov@x-np.sum(b*np.log(x))
        def jac(x):return cov@x-b/x
        z=minimize(fun,1/np.sqrt(np.diag(cov)*m),jac=jac,bounds=[(1e-9,None)]*m,method='L-BFGS-B',options={'ftol':1e-14,'gtol':1e-10,'maxiter':3000})
        if not z.success:raise RuntimeError(z.message)
        w=z.x/z.x.sum();rc=w*(cov@w)/(w@cov@w);error=float(np.max(abs(rc-1/m)))
        assert error<1e-6
    invested=float(sum(a for a,r in zip(w,selected) if r['active']))
    return dict(symbols=symbols,weights=w.tolist(),cash=1-invested,invested=invested,erc_error=error)


def equation_svg(text):
    fig=plt.figure(figsize=(13,.65));fig.text(.01,.5,'$'+text+'$',fontsize=14,va='center')
    stream=io.StringIO();fig.savefig(stream,format='svg',bbox_inches='tight',pad_inches=.1);plt.close(fig)
    return stream.getvalue()[stream.getvalue().index('<svg'):]


def flow(name,nodes):
    fig,ax=plt.subplots(figsize=(12,len(nodes)*.9));ax.set(xlim=(0,10),ylim=(0,len(nodes)));ax.axis('off')
    for j,(head,body) in enumerate(nodes):
        y=len(nodes)-j-.5
        ax.text(5,y,head+'\n'+body,ha='center',va='center',fontsize=11,
                bbox=dict(boxstyle='round,pad=.55',facecolor='#e9f2f4',edgecolor='#176b73'))
        if j<len(nodes)-1:ax.annotate('',xy=(5,y-.67),xytext=(5,y-.32),arrowprops=dict(arrowstyle='->',color='#176b73',lw=1.8))
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');fig.savefig(OUT/(name+'.png'),dpi=130,bbox_inches='tight');plt.close(fig)


def figure(c,name):
    a=c['arms']['baseline'];days=np.array(c['days'],dtype='datetime64[D]');v=lambda x:np.array([np.nan if y is None else y for y in x],float)
    fig,ax=plt.subplots(5,1,figsize=(13,12),sharex=True,gridspec_kw={'height_ratios':[3,1,1.2,1.2,2]})
    ax[0].plot(days,c['close'],lw=1,label='Adjusted close');ax[0].vlines(days,c['low'],c['high'],alpha=.25,lw=.5)
    ax[0].plot(days,v(a['stop']),color='#bd465c',lw=1,label='Closing protection boundary')
    for side,col,marker in [('buy','#00897b','^'),('sell','#bd465c','v')]:
        fills=[f for f in a['fills'] if f['side']==side]
        ax[0].scatter(np.array([f['day'] for f in fills],dtype='datetime64[D]'),[f['price'] for f in fills],c=col,marker=marker,s=25,label=side)
    ax[0].legend(loc='upper left');ax[0].set_ylabel('Adjusted USD')
    ax[1].bar(days,np.array(c['volume'])/1e6,color='#8fa5af');ax[1].set_ylabel('Raw volume (m)')
    for k,col in [('fast_up','#00897b'),('neutral','#ba9b39'),('fast_down','#bd465c')]:ax[2].plot(days,c[k],label=k,color=col,lw=1)
    ax[2].legend(ncol=3);ax[2].set_ylabel('Fast HMM')
    for k,col in [('slow_up','#00897b'),('slow_down','#bd465c')]:ax[3].plot(days,c[k],label=k,color=col,lw=1)
    ax[3].legend(ncol=2);ax[3].set_ylabel('Slow slope')
    ax[4].plot(days,v(a['nav']),label='Chosen: symmetric HMM + close exits',color='#00897b')
    ax[4].plot(days,v(c['arms']['stop']['nav']),label='Standing-stop comparator',color='#c58b22',alpha=.7)
    start=next(i for i,x in enumerate(a['nav']) if x is not None)
    bh=np.array(c['close'][start:])/c['close'][start]*100
    ax[4].plot(days[start:],bh,label='Close-normalized asset, before costs',color='#8296a9',alpha=.6)
    ax[4].set_ylabel('NAV / initial 100');ax[4].legend(fontsize=8)
    for z in ax:z.grid(alpha=.15)
    fig.suptitle(name.replace('_',' | ')+' — selected baseline; 5 bp each side, next-open fills\nProtection is checked at the close; gaps and intraday losses are not capped.',fontsize=12)
    fig.tight_layout();fig.savefig(OUT/(name+'.png'),dpi=125);plt.close(fig)


def main():
    import research_entry_value as study
    OUT.mkdir(exist_ok=True)
    parents=study.verified();market,selected=parents[0],parents[-1]
    entry=ROOT/'research/entry-value-20261027-v1';stop=ROOT/'research/stop-review-20261027-v1'
    for folder in [entry,stop]:
        validation=read(folder/'validation.json')
        assert digest(folder/'chart-data.json.gz')==validation['chart_sha256']
        manifest=read(folder/'manifest.json')
        files=manifest.get('files',manifest.get('artifacts',{}))
        if 'asset-results.json' in files:assert digest(folder/'asset-results.json')==files['asset-results.json']
    erows=read(entry/'asset-results.json');srows=read(stop/'asset-results.json')
    charts=json.loads(gzip.decompress((stop/'chart-data.json.gz').read_bytes()))
    er={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r for r in erows if r['arm']=='hmm'}
    sr={(r['symbol'],r['era'],r['cost_bp'],r['delay']):r for r in srows if r['arm']=='baseline'}
    assert len(er)==len(sr)==612
    assert max(abs(er[k]['cumulative']-sr[k]['cumulative']) for k in er)<1e-12
    snapshots={}
    for symbol,eras in selected.items():
        for era,q in eras.items():
            saved=market[symbol][era];p=study.model.parent.thesis_exit.grid(saved['selected']['selected']['parameters'])[0]
            snapshots[symbol+'_'+era]=dict(symbol=symbol,era=era,training_end=q['training_end'],
                slow=saved['hmms']['slow'],fast=saved['hmms']['fast'],sigma=saved['hmms']['sigma'],
                fast_hmm=q['hmm']['model'],policy=p,thesis_rule=q['exit_rule'],
                inherited_training_evidence=saved['selected']['selected']['evidence'],
                note='Legacy family/label records inherited parameter selection; fast inference is the symmetric HMM for every ETF.')
    write(OUT/'selected-models.json',snapshots)
    comparison=[];weakest={}
    for era in ['late','early']:
        for label,rows,arm in [('Original fixed detector',erows,'control'),('Selected symmetric HMM',erows,'hmm'),('Standing-stop comparator',srows,'stop')]:
            q=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==5 and r['delay']==0 and r['symbol']!='BIL']
            comparison.append(dict(era=era,model=label,count=len(q),**{k:float(np.median([r[k] for r in q if r[k] is not None])) for k in ['cumulative','cagr','sharpe','calmar','maxdd','ic5','exposure','correlation','cost_bp_annual']}))
            if arm=='hmm':weakest[era]=min(q,key=lambda r:(r['cumulative'],r['symbol']))
    write(OUT/'comparison.json',comparison);write(OUT/'weakest-cases.json',weakest)
    write(OUT/'selected-results.json',[r for r in erows if r['arm']=='hmm'])
    rank,series=rank_preview(charts,'2026-10-16')
    allocations={str(n):{k:allocation(rank,series,n,k) for k in ['equal','risk']} for n in [6,10,15,20,30]}
    preview=dict(asof='2026-10-16',short=63,long=252,primary_display_n=15,rows=rank,allocations=allocations,
        status='Historical design preview, not a portfolio backtest or a live target. N=15 is illustrative, not optimized.')
    write(OUT/'rank-preview.json',preview)
    write(OUT/'portfolio-design.json',dict(status='Specified for next experiment; not backtested or adopted',
        algorithm='symmetric-trend-sleeve-v1 (entry-value B)',
        universe='Full supported risky pool; BIL cash reference; complete aligned causal records',
        tracking='All virtual strategies continue daily while unselected; preserve states and cash days',
        rank=dict(primary_windows=[63,252],sensitivity_windows=[21,126],components=['short return','short Sharpe','long return','long Sharpe'],weights=[.25]*4,positive_return_gate=False),
        widths=[6,10,15,20,30],preview_width=15,preview_width_is_optimal=False,
        width_selection='Prior chronological validation; largest N within .05 Sharpe, 1pp CAGR and 2pp drawdown of best; report full curve',
        allocation=['equal sleeve capital','equal strategy-risk contribution'],
        risk=dict(observations=252,diagonal_shrinkage=.5,annual_volatility_floor=.05,uses='net strategy account covariance including cash',leverage=False),
        timing=dict(primary='month-end close to next open',control='month-end or theoretical/last-adopted cash-inclusive L1 >= .10',daily_signal_trading=True),
        cash='Sleeve retains cash after exit; no daily redistribution; budgets drift',
        joining='Join existing virtual state/protection next open; pending exit takes priority; departing member liquidated but shadow continues',
        accounting='Actual netted cash/share fills; charge costs once; shadow net returns drive ranks only',
        warmup='252 post-fit return observations; no fitted pre-cutoff NAV masquerading as causal ranking history',
        frictions=dict(each_side_bp=[5,10,20],extra_delay=[0,1]),
        controls=['unranked full-pool sleeves','matched raw-ETF momentum','cash and ETF buy/hold','FR25 on compatible data'],
        authority='No monitoring, promotion, allocation or broker changes'))
    for era,r in weakest.items():figure(charts[r['symbol']+'_'+era],r['symbol']+'_'+era)
    # Retain compact chart fields for every available chosen ETF; omit rejected learning streams.
    chartpack={k:{**{n:c[n] for n in ['days','open','high','low','close','volume','fast_up','neutral','fast_down','slow_up','slow_down']},
        'nav':c['arms']['baseline']['nav'],'stop':c['arms']['baseline']['stop'],'fills':c['arms']['baseline']['fills'],
        'trades':c['arms']['baseline']['trades']} for k,c in charts.items()}
    (OUT/'chart-data.json.gz').write_bytes(gzip.compress(json.dumps(chartpack,separators=(',',':')).encode(),mtime=0))
    eq=read(ROOT/'scripts/assets/trend-sleeve-equations.json')
    write(OUT/'equations.json',eq)
    equations=''.join('<h3>'+html.escape(x['title'])+'</h3><div class="equation">'+equation_svg(x['formula'])+'</div><p>'+x['explanation']+'</p>' for x in eq)
    fig=plt.figure(figsize=(16,len(eq)*.7))
    for j,x in enumerate(eq):fig.text(.01,1-(j+.6)/len(eq),'$'+x['formula']+'$',fontsize=11,va='center')
    fig.savefig(OUT/'equation-proof.png',dpi=115,bbox_inches='tight');plt.close(fig)
    flow('daily-flow',[
        ('1. Execute the previously adopted target at today\'s open','Cash-funded buy / complete sell; decisions from close t−1−delay.'),
        ('2. Observe the audited completed close','Update fast and slow Kalman states; filter the symmetric fast HMM.'),
        ('3. Update slow context and thesis evidence','Slow-up ≥ 70%; count low fast-up observations; no future smoothing.'),
        ('4. Rearm if fast-up < 50%','This step occurs before the decision below.'),
        ('5. If desired LONG: test exit','Down-state threshold OR thesis failure OR held close below old boundary → desired CASH; disarm.'),
        ('6. Else, if desired CASH and actually flat','Armed + up-state threshold + positive fast slope → desired LONG; disarm. Otherwise retain target.'),
        ('7. If held: ratchet protection for the next close','Update peak completed close; never loosen the adopted boundary.'),
        ('8. Mark NAV; carry target to its executable open','No intraday stop or fixed take-profit; repeat every session, even when portfolio-unselected.')])
    flow('portfolio-flow',[
        ('Daily: maintain every ETF\'s independent strategy account','Chosen frozen algorithm continues while unselected; cash days remain in its return history.'),
        ('Monthly close: calculate the whole rank table','63/252-session strategy returns and Sharpe → four percentile ranks → equal-weight combined score.'),
        ('Choose top N eligible strategy sleeves','N tested at 6 / 10 / 15 / 20 / 30; 15 shown only as a design preview.'),
        ('Assign sleeve capital: equal weight or equal risk contribution','Risk from covariance of daily strategy account returns, with shrinkage and a variance floor.'),
        ('Next open: rebalance membership and sleeve capital','Joining an active shadow trade follows its existing signal state; expose inherited protection levels.'),
        ('Between monthly selections: daily signals still trade','Each selected sleeve buys/sells with its algorithm; cash stays in that sleeve; do not refill vacant exposure.'),
        ('Measure full portfolio and attribution','Actual netted fills, fees, cash, drawdown, concentration and selection turnover; compare dynamic timing separately.')])
    table='<table><tr><th>Period</th><th>Model</th><th>Median return</th><th>CAGR</th><th>Sharpe</th><th>Calmar</th><th>Drawdown</th><th>IC5</th></tr>'
    for r in comparison:table+=f"<tr><td>{r['era']}</td><td>{r['model']}</td><td>{r['cumulative']:.2%}</td><td>{r['cagr']:.2%}</td><td>{r['sharpe']:.3f}</td><td>{r['calmar']:.3f}</td><td>{-r['maxdd']:.2%}</td><td>{r['ic5']:.3f}</td></tr>"
    table+='</table>'
    template=(ROOT/'scripts/assets/trend-sleeve-synthesis.html').read_text(encoding='utf-8')
    js=(ROOT/'scripts/assets/trend-sleeve-synthesis.js').read_text(encoding='utf-8')
    data=dict(rank=preview,charts=chartpack,models=snapshots,weakest={k:v['symbol'] for k,v in weakest.items()})
    result=template.replace('__COMPARISON__',table).replace('__EQUATIONS__',equations).replace('__SCRIPT__','const DATA='+json.dumps(data,separators=(',',':')).replace('</',r'<\/')+';\n'+js)
    (OUT/'index.html').write_text(result,encoding='utf-8')
    sources=[entry/'asset-results.json',entry/'protocol.json',entry/'fits.json',entry/'fit-manifest.json',stop/'asset-results.json',stop/'chart-data.json.gz',stop/'protocol.json']
    write(OUT/'provenance.json',dict(identity=OUT.name,algorithm='symmetric-trend-sleeve-v1; exact alias of entry-value B',
        batch=read(entry/'protocol.json')['published_inputs'],sources={x.relative_to(ROOT).as_posix():digest(x) for x in sources},
        exact_parent_return_comparisons=612,model_snapshots=len(snapshots),rank_date=preview['asof'],new_backtest=False))
    print('Built synthesis:',len(snapshots),'ETF/era models;',len(rank),'ranked risky ETFs; weakest',[(e,r['symbol'],r['cumulative']) for e,r in weakest.items()])


if __name__=='__main__':main()
