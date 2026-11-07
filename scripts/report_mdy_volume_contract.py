"""Render the compact source-definition handoff without new research inputs."""
import html
from pathlib import Path

from qualify_mdy_volume_contract import OUT,ROOT,read,save,sha


def run():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    assessment=read(OUT/'assessment.json')
    stocks=assessment['stocks']
    fig,ax=plt.subplots(figsize=(10,5.5),layout='constrained')
    for i,r in enumerate(stocks):
        ax.plot([r['p01'],r['p99']],[i,i],color='#779cab',linewidth=5,solid_capstyle='round')
        ax.plot(r['median'],i,'o',color='#096b7a',markersize=8)
    for c in assessment['controls']:
        i=next(i for i,r in enumerate(stocks) if r['symbol']==c['symbol'])
        ax.plot(c['all_hours']['median'],i,'D',color='#bc6b19',markersize=7)
    ax.plot([],[],'o',color='#096b7a',label='Regular-hours median; line = 1st–99th percentile')
    ax.plot([],[],'D',color='#bc6b19',label='All-hours control median (three stocks)')
    ax.axvline(1,color='#67717b',ls='--',lw=1)
    ax.set(yticks=range(len(stocks)),yticklabels=[r['symbol'] for r in stocks],xlim=(0,1.07),
           xlabel='IBKR volume as returned / published raw-volume value',
           title='Volume differences vary by stock and date')
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis='x',alpha=.18)
    ax.spines[['top','right','left']].set_visible(False)
    ax.legend(loc='upper left',bbox_to_anchor=(0,-.13),frameon=False,fontsize=9)
    fig.savefig(OUT/'volume-comparison.png',dpi=150)
    plt.close(fig)

    title='Volume qualification: define coverage before changing data'
    lead=('The definition review is complete. The ten-stock discrepancy is not explained by our split '
          'reconstruction or a fixed shares/lots multiplier. Session coverage explains part of the difference; '
          'the remaining trade-coverage and unit semantics need a documented source. A proposed input '
          'contract and a 50-stock-day qualification request are ready. No new history or asset was published.')
    sections=[
      ('What we ruled out',
       'All 2,530 matched published rows have split multiplier one and raw volume equal to source volume. '
       'The dates align exactly. Our split-reconstruction arithmetic therefore does not create this gap. '
       'The fixed 0.01, 1 and 100 multiplier checks do not reconcile the series. Even fitting a separate '
       'constant to each stock leaves 99th-percentile absolute relative discrepancies of 43.6%–77.7%. '
       'That fitted scale is diagnostic only; it was never applied to the database. '
       'The result does not prove every corporate action in the source ledger is correct.'),
      ('What session coverage explains',
       'The existing all-hours controls for CSL, WSO and XPO are larger than the regular-hours values '
       'on every one of their 759 observations, and still below the published values on every observation. '
       'Their median ratios rise to 54.0%, 49.8% and 68.7%. Even after median scaling, their all-hours '
       '99th-percentile discrepancies remain 24.0%–51.6%. We retain the source values and do not infer '
       'an undocumented unit conversion.'),
      ('Why price agreement cannot validate volume',
       'Price and volume can legitimately count different trades. The UTDF specification describes a '
       'closing consolidated volume that includes pre- and post-market activity; it can exist without a '
       'regular-session last sale. Massive documents separate condition rules for price and volume, '
       'including a condition that updates volume without updating price. These definitions establish '
       'why matching closes cannot certify matching volume; they do not certify our Yahoo or IBKR captures.'),
      ('The proposed activity definition',
       'Use unadjusted consolidated share volume for the completed tape reporting day, with explicit '
       'historical session hours and eligible exchange/off-exchange trades. Preserve the source rules '
       'for auctions, odd lots, corrections and cancellations. Pair it with the same activity-date '
       'audited raw regular-session close. Close times volume remains an activity proxy, not actual '
       'traded dollar value or net capital flow. A regular-session consolidated series can be a separate '
       'control; filtered broker history is not silently substituted for either series.'),
      ('A necessary timing rule',
       'Keep the frozen preceding-close information cutoff. Full-session volume including after-hours '
       'trading is not available at that same close. For the March 3, 2025 decision with a February 28 '
       '16:00 New York cutoff, February 28 full-session volume is ineligible. February 27 is only a '
       'candidate if its publication and capture timestamps support the cutoff. Use the latest genuinely '
       'available complete price/volume pair and shift the whole activity stencil and matching return '
       'direction together. A November 2026 download cannot establish actual March 2025 availability. '
       'Any retrospective availability assumption must be declared separately.'),
      ('Asset reuse and implementation boundary',
       'The new catalog search found activity-raw-v1 and activity-audited-lag20-v1, plus related legacy '
       'signals. Their pinned definitions were inspected. The existing raw asset certifies its frozen '
       'raw-basis contract, not a new full-universe consolidated-coverage claim. This item reused '
       'GovernedInputs, calendar/audit utilities and the repaired verified HTTP reader for inspection. '
       'It changed no registered asset, composite, shared service, runtime fingerprint or calculation. '
       'A future consolidated-activity version needs pinned inputs, a reuse review and a monitoring '
       'contract before a tracked composite can demand it.'),
      ('Source access and the next concrete action',
       'Four bounded Nasdaq requests for February 24–28, 2025 returned no rows (CSL, WSO, XPO, MANH); '
       'the recent CSL control returned three rows. These results establish the tested requests, not a '
       'general historical retention limit. NYSE Daily TAQ and a documented SIP-based vendor are routes '
       'to investigate for a matching source; product documentation alone does not qualify a dataset. '
       'The prepared request is the ten frozen identities over five dates (50 stock-days), plus three '
       'previously observed price exceptions. Establish existing access or obtain a bounded evaluation '
       'extract, check its definitions, and then decide whether to expand acquisition. No purchase, '
       'subscription or provider contact was made.'),
      ('Status and limitations',
       'This completes the volume-definition item and stops for operator discussion. Closing-price '
       'corroboration remains useful; volume eligibility, security continuity, historical availability '
       'and previous source reviews remain unresolved. No portfolio policy or performance result was '
       'calculated, so a weakest-ETF trading inspection does not apply. Thirty-two focused tests passed, '
       'including missing/invalid ratios, time-varying versus constant scales, and future/naive-timestamp '
       'rejection. Dependency contract preflight passed. Compact findings, contracts, hashes and runners '
       'are retained; small public probe caches and the rendered chart are disposable after closure. '
       'The earlier protected broker evidence retains its existing retention status.')]
    sources=read(OUT/'sources.json')['sources']
    refs={s['id']:s for s in sources}
    links=[('Field contract','field-contract.json'),('Prepared data request','source-request.json'),
           ('Detailed diagnostics','assessment.json'),('Asset reuse review','reuse-review.json'),
           ('Source references','sources.json'),('Artifact hashes','artifact-manifest.json')]
    cells=[[r['symbol'],f"{r['median']:.1%}",f"{r['p01']:.1%}–{r['p99']:.1%}",
             f"{r['p99_residual_after_median_scaling']:.1%}"] for r in stocks]
    headers=['Stock','Median volume ratio','1st–99th percentile ratio','99th percentile error after fitted constant']
    md=['# '+title,'','November 7, 2026','',lead,'','![Volume ratio comparison](volume-comparison.png)','',
        '| '+' | '.join(headers)+' |','| '+' | '.join(['---']*4)+' |']
    md+=['| '+' | '.join(row)+' |' for row in cells]
    web_sections=[]
    for heading,body in sections:
        md+=['','## '+heading,'',body]
        cite=[]
        if heading=='Why price agreement cannot validate volume':cite=[refs['utp'],refs['massive']]
        if heading=='Source access and the next concrete action':cite=[refs['nyse']]
        if cite:md+=['',' · '.join(f"[{s['title']}]({s['url']})" for s in cite)]
        web_sections.append('<section><h2>'+html.escape(heading)+'</h2><p>'+html.escape(body)+'</p>'
             +'<p>'+ ' · '.join('<a href="'+s['url']+'">'+html.escape(s['title'])+'</a>' for s in cite)+'</p></section>')
    md+=['',' · '.join(f'[{label}]({url})' for label,url in links),'']
    (OUT/'results.md').write_text('\n'.join(md),encoding='utf8',newline='\n')
    table='<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'
    table+=''.join('<tr>'+''.join('<td>'+html.escape(c)+'</td>' for c in row)+'</tr>' for row in cells)+'</tbody></table>'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page+='<title>'+html.escape(title)+'</title><style>body{font:17px/1.65 system-ui,sans-serif;background:#f4f6f8;color:#182536}main{max-width:1060px;background:white;margin:30px auto;padding:36px;border-radius:12px}h1{font-size:34px;line-height:1.2}h2{font-size:22px;margin-top:30px}img{width:100%;height:auto}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #dbe2e8;text-align:left}th{background:#e9f2f5}a{color:#086680}@media(max-width:700px){main{margin:0;padding:16px}td,th{padding:4px}}</style>'
    page+='<main><p>Research evidence · November 7, 2026</p><h1>'+html.escape(title)+'</h1><p>'+html.escape(lead)+'</p>'
    page+='<img src="volume-comparison.png" alt="Volume ratios vary across stocks and dates">'+table+''.join(web_sections)
    page+='<p>'+' · '.join('<a href="'+url+'">'+label+'</a>' for label,url in links)+'</p></main></html>'
    (OUT/'index.html').write_text(page,encoding='utf8',newline='\n')
    save(OUT/'acceptance.json',dict(tests_passed=32,stock_days=2530,control_stock_days=759,
        source_probes=5,new_publications=0,new_assets=0,shared_services_changed=[],
        status='Definition review complete; source qualification and historical availability unresolved.',
        protected_evidence='Earlier broker and canonical audited histories remain protected.',
        retirement='Public probe cache and rendered reports/chart are disposable after closure; retain compact diagnostics, contracts, request, hashes and runners.',
        runner_hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [Path(__file__),
            ROOT/'scripts/qualify_mdy_volume_contract.py',ROOT/'tests/test_mdy_volume_contract.py']}))
    save(OUT/'artifact-manifest.json',{p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*'))
                                     if p.is_file() and p.name!='artifact-manifest.json'})


if __name__=='__main__':
    run()
