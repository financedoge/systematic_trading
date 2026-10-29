"""All-ETF chart report with explicit mathematical definitions."""
import gzip
from html import escape
from io import BytesIO
import json
import re
import numpy as np
import research_trained_review as study

NAMES={'baseline':'A · Standing protection','stop':'B · Trained price reviewer','review':'C · Trained price + volume'}
COLORS={'baseline':'#8b9caa','stop':'#c98a21','review':'#008675'}


def figure(c,symbol,era,path,limits=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    d=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['review']
    fig,ax=plt.subplots(7,1,figsize=(15,15),sharex=True,layout='constrained',height_ratios=[2.3,.6,.8,.65,.8,.8,1.4])
    mask=np.ones(len(d),bool) if not limits else (d>=np.datetime64(limits[0]))&(d<=np.datetime64(limits[1]))
    ax[0].plot(d,c['close'],color='#173d54',label='Adjusted close');ax[0].plot(d,np.array(a['stop'],float),color='#b64f61',label='C active stop',marker='_',ms=5,lw=.9)
    ax[0].vlines(d[mask],np.array(c['low'])[mask],np.array(c['high'])[mask],color='#91a3ae',lw=.7)
    for e in a['fills']:
        if limits and not limits[0]<=e['day']<=limits[1]:continue
        buy=e['side']=='buy';rec=any(t['entry_date']==e['day'] and t.get('entry_reason')=='exit_review' for t in a['trades'])
        ax[0].scatter(np.datetime64(e['day']),e['price'],marker='^' if buy else 'v',color=('#d58b20' if rec else '#008675') if buy else '#b64f61',s=34,zorder=5)
    ax[0].set_ylabel('Adjusted USD');ax[0].legend(fontsize=8,ncol=2)
    ax[1].bar(d,np.array(c['volume'])/1e6,color='#9aabb6');ax[1].set_ylabel('Volume (m)')
    for k,color in [('fast_up','#008675'),('neutral','#b09a52'),('fast_down','#b64f61')]:ax[2].plot(d,c[k],label=k,color=color)
    for k,color in [('slow_up','#008675'),('slow_down','#b64f61')]:ax[3].plot(d,c[k],label=k,color=color)
    for k,color in [('hold_value','#b64f61'),('recover_value','#008675')]:ax[4].plot(d,np.array(a[k],float),label=k,color=color,marker='.',ms=3,lw=.8)
    margin=c['training']['models']['volume']['margin']
    if margin is not None:
        ax[4].axhline(margin,ls='--',color='#777',lw=.7);ax[4].axhline(-margin,ls='--',color='#777',lw=.7)
    for k,color in [('reviewer_owned','#173d54'),('review_signal','#c98a21')]:ax[5].plot(d,np.array(a[k],float),label=k,color=color)
    for arm in study.model.ARMS:ax[6].plot(d,np.array(c['arms'][arm]['nav'],float),label=NAMES[arm],color=COLORS[arm])
    for i in range(2,7):ax[i].legend(fontsize=8,ncol=3)
    for i in (2,3,5):ax[i].set_ylim(-.02,1.02)
    for x in ax:x.grid(alpha=.15)
    if limits:
        ax[-1].set_xlim(np.datetime64(limits[0]),np.datetime64(limits[1]))
        values=[c[k][i] for i in np.flatnonzero(mask) for k in ('low','high')]+[a['stop'][i] for i in np.flatnonzero(mask) if a['stop'][i] is not None]
        lo,hi=min(values),max(values);ax[0].set_ylim(lo-(hi-lo)*.06,hi+(hi-lo)*.06)
        navs=[c['arms'][arm]['nav'][i] for arm in study.model.ARMS for i in np.flatnonzero(mask) if c['arms'][arm]['nav'][i] is not None]
        lo,hi=min(navs),max(navs);pad=max(.5,(hi-lo)*.07);ax[6].set_ylim(lo-pad,hi+pad)
        ax[1].set_ylim(0,max(np.array(c['volume'])[mask])/1e6*1.1)
    else:ax[-1].set_xlim(np.datetime64(c['evaluation_start']),d[-1])
    ax[-1].set_ylabel('NAV / initial100');ax[-1].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m-%d'))
    ax[4].set_ylabel('Value / ATR unit')
    status='Reviewer disabled by training' if margin is None else f'Reviewer enabled; margin = {margin} ATR units'
    fig.suptitle(f'{symbol} | {era} | C trained price/volume reviewer (frozen evaluation coefficients)\n{status}\nGreen buys / red sells; orange recovery buys. 5 bp per side + 5 bp stop slippage; next-open decisions.',fontsize=12)
    fig.savefig(path,dpi=110);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    import matplotlib.pyplot as plt
    formulas=['a_t=\\max(ATR_t/C_t,0.0001),\\quad EMA_{s,t}=EMA_{s,t-1}+\\frac{2}{s+1}(X_t-EMA_{s,t-1})', 'x^P_t=[1,\\ r_t/a_t,\\ (r_t+r_{t-1}+r_{t-2})/(\\sqrt{3}a_t),\\ (C_t-EMA_{10,t})/(C_ta_t),\\ (EMA_{10,t}-EMA_{60,t})/(C_ta_t),\\ 2CL_t-1,\\ldots]', '[\\ldots,(C_t-Ref_t)/(C_ta_t),\\ (Peak_t-C_t)/(C_ta_t),\\ \\min(Age_t,60)/20,\\ (C_t-S_{t+1})/(C_ta_t),\\ Owned_t]', 'x^V_t=[x^P_t,\\ \\log(V_t/EMA_{20,t}(V)),\\ VP_t,\\ (2CL_t-1)\\log(V_t/EMA_{20,t}(V))]', 'CL_t=(C_t-L_t)/(H_t-L_t),\\quad VP_t=\\frac{\\sum_{i=t-2}^t sign(C_i-C_{i-1})V_i}{\\sum_{i=t-2}^tV_i}', 'R_t=P^{exit}_{t}/O_{t+1}-1,\\quad D_t=\\max(0,1-P^{lowest}_{t}/O_{t+1}),\\quad Y_t=[R_t,D_t]/a_t', 'P^{exit}_t=\\mathrm{protected\\ path\\ exit\\ or}\\ O_{t+11};\\quad Y_t\\ \\mathrm{becomes\\ available\\ only\\ at}\\ t+11', '\\omega_i=1/N_{episode(i)},\\quad z_i=(clip(x_i,-5,5)-\\bar x_{train})/\\max(sd_{train},0.1)', '\\hat B=(Z^TWZ+\\lambda I^*)^{-1}Z^TWY,\\quad \\lambda\\in\\{1,10,100\\};\\quad \\mathrm{alternative}:\\ \\hat Y=\\bar Y_{train}', '\\lambda^*=\\arg\\min_{\\lambda}\\sum_{i\\in validation}\\omega_i[(\\hat Y_{i,1}-Y_{i,1})^2+0.25(\\hat Y_{i,2}-Y_{i,2})^2]', '\\hat R_t=a_t(z_t\\hat B)_1,\\quad \\hat D_t=a_t\\max(0,(z_t\\hat B)_2)', 'U^H_t=(\\hat R_t-0.25\\hat D_t)/a_t,\\quad U^R_t=\\left[(1+\\hat R_t)\\frac{1-f}{1+f}-1-0.25\\hat D_t\\right]/a_t', '\\mathrm{sell\\ if}\\ U^H_t<-m;\\quad\\mathrm{recover\\ if}\\ U^R_t>m;\\quad m\\in\\{0,0.25,0.5,\\mathrm{disabled}\\}', '\\mathrm{validation}:\\ Sharpe>Sharpe_A+0.01,\\ Return\\geq Return_A-0.005,\\ MaxDD\\geq MaxDD_A-0.01', '\\mathrm{recovery\\ fill\\ requires}\\ |O_{t+1+delay}-C_t|\\leq ATR_t;\\quad 1\\leq t-t_{last\\ sale}\\leq20', 'S_{entry}=O_{entry}-d\\sigma O_{entry},\\quad S_{t+1}=\\max(S_t,Peak_t-d_t\\sigma O_{entry}),\\quad L_t\\leq S_t\\Rightarrow F_t=\\min(O_t,S_t)(1-s)', 'Owned_{entry}=1\\ \\mathrm{for\\ recovery};\\quad Owned_t=0\\ \\mathrm{after\\ eligible\\ upward\\ confirmation};\\quad \\mathrm{protection\\ always\\ active}', '\\mathrm{shadow}:\\ S_0=20I,\\ B_0=20\\hat B,\\ \\rho=2^{-1/63};\\quad S\\leftarrow\\rho S+zz^T/10,\\ B\\leftarrow\\rho B+zY^T/10', '\\hat Y^{shadow}_t=z_t(S+10^{-6}I)^{-1}B;\\quad\\mathrm{update\\ only\\ matured\\ labels;\\ no\\ effect\\ on\\ traded\\ policy}']
    parts=[]
    for i,formula in enumerate(formulas):
        buf=BytesIO();mathtext.math_to_image('$'+formula+'$',buf,prop=FontProperties(size=13),format='svg',color='#17384d')
        svg=buf.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{i}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{i}_{m[1]}"',svg)
        parts.append('<div class="equation">'+svg+'</div>')
    fig,axes=plt.subplots(len(formulas),1,figsize=(24,19),layout='constrained')
    for ax,formula in zip(axes,formulas):ax.axis('off');ax.text(.005,.3,'$'+formula+'$',fontsize=12)
    fig.savefig(study.OUT/'equation-proof.png',dpi=95,bbox_inches='tight');plt.close(fig);study.write(study.OUT/'equations.json',formulas)
    return ''.join(parts)


def main():
    validation=json.loads((study.OUT/'validation.json').read_text());assert validation['chart_sha256']==study.prior.study.digest(study.OUT/'chart-data.json.gz')
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text())
    sums=json.loads((study.OUT/'summary.json').read_text());weakest=json.loads((study.OUT/'weakest-cases.json').read_text())
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0];lookup={(r['symbol'],r['era'],r['arm']):r for r in primary}
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%';num=lambda x:'—' if x is None else f'{x:.3f}'
    def table(heads,body):return '<div class="scroll"><table><tr>'+''.join('<th>'+h+'</th>' for h in heads)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in body)+'</table></div>'
    summary=table(['Era','Model','Median Sharpe','Median CAGR','Preserved ETFs','Fee + slip bp/year','Pass'],[
        [r['era'],NAMES.get(r['arm'],r['arm']),num(r['median_sharpe']),pct(r['median_cagr']),pct(r['guard_fraction']),f"{r['median_annual_cost_bp']:.1f}",r['passed']]
        for r in sums if r['cost_bp']==5 and r['delay']==0 and r['arm'] in NAMES])
    pool=[]
    for era,*_ in study.ERAS:
        for c in sorted((r for r in primary if r['era']==era and r['arm']=='review'),key=lambda r:r['cumulative']):
            a,b=lookup[c['symbol'],era,'baseline'],lookup[c['symbol'],era,'stop']
            pool.append([c['symbol'],era,pct(a['cumulative']),pct(b['cumulative']),pct(c['cumulative']),num(c['sharpe']),num(c['calmar']),pct(-c['maxdd']),num(c['ic5']),('Yes' if c['enabled'] else 'No'),f"{c['wins']}/{c['closed_trades']}"])
    focus={('CPER','late'),('IWM','late'),('GLD','late'),('WEAT','late'),('TLT','late'),('SLV','late'),('DBA','late'),('SOXX','late'),*((r['symbol'],e) for e,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[symbol+'_'+era],symbol,era,study.OUT/f'{symbol}_{era}.png')
    for symbol,a,b in [('CPER','2025-03-04','2025-09-04'),('IWM','2024-07-01','2024-12-01')]:figure(charts[symbol+'_late'],symbol,'late',study.OUT/f'{symbol}-incident.png',(a,b))
    figure(charts['WEAT_late'],'WEAT','late',study.OUT/'WEAT-churn.png',('2023-01-03','2023-03-31'))
    figure(charts['MCHI_early'],'MCHI','early',study.OUT/'MCHI-loss.png',('2021-06-21','2021-07-15'))
    html=(study.ROOT/'scripts/assets/trained-review-template.html').read_text(encoding='utf-8')
    def display(v):
        if isinstance(v,float):return round(v,8)
        if isinstance(v,list):return [display(x) for x in v]
        if isinstance(v,dict):return {k:display(x) for k,x in v.items()}
        return v
    forecasts=json.loads((study.OUT/'forecast-diagnostics.json').read_text());cal=[]
    for era,*_ in study.ERAS:
        for arm in ('stop','review'):
            for task in ('hold','recover'):
                rr=[r[task] for r in forecasts if r['era']==era and r['arm']==arm and r['symbol']!='BIL' and r[task]['count']]
                losses=[float(np.median([r[k]['loss'] for r in rr])) for k in ('constant','fixed','shadow')]
                cal.append([era,NAMES[arm],task,sum(r['count'] for r in rr),*[num(v) for v in losses]])
    replacements=dict(FORECASTS=table(['Era','Model','Decision','Observations','Constant loss','Fitted loss','Shadow loss'],cal),FINDINGS=(study.OUT/'findings.html').read_text(encoding='utf-8'),SUMMARY=summary,
        POOL=table(['ETF','Era','A return','B return','C return','C Sharpe','C Calmar','C maxDD','HMM IC','C enabled','C wins/trades'],pool),
        STRESS=table(['Era','Fee bp','Extra delay','Model','Median Sharpe','Median CAGR','Preserved','Pass'],[[r['era'],r['cost_bp'],r['delay'],NAMES[r['arm']],num(r['median_sharpe']),pct(r['median_cagr']),pct(r['guard_fraction']),r['passed']] for r in sums if r['arm'] in ('stop','review')]),
        COMPONENTS=table(['Era','Diagnostic','Sharpe','CAGR','Preserved'],[[r['era'],r['arm'],num(r['median_sharpe']),pct(r['median_cagr']),pct(r['guard_fraction'])] for r in sums if r['arm'] not in NAMES]),
        YEARLY=table(['Era','Model','Year','Median return'],[[r['era'],NAMES[r['arm']],y,pct(v)] for r in sums if r['arm'] in NAMES and r['cost_bp']==5 and r['delay']==0 for y,v in r['yearly'].items()]),
        EQUATIONS=equations(),EXPORTS=' · '.join(f'<a href="{s}_{e}.png">{s} {e}</a>' for s,e in sorted(focus))+' · <a href="CPER-incident.png">CPER selected dates</a> · <a href="IWM-incident.png">IWM selected dates</a>',
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),
        SCRIPT=(study.ROOT/'scripts/assets/trained-review-script.js').read_text(encoding='utf-8'))
    for key,value in replacements.items():html=html.replace('__'+key+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');print('Built306 chart cases',flush=True)


if __name__=='__main__':main()
