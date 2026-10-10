"""Bounded economic-response revisit on the frozen M1/14 candidate pool."""
from datetime import UTC,date,datetime,timedelta
from decimal import Decimal as D
from pathlib import Path
import shutil

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import read_json,checked_files,verify_usd_bundle,freeze_usd_bundle,run_usd_reference
from systematic_trading.research.construction_controls import FinalWeightCapOverlay,gross
from systematic_trading.research.economic_response import tilt

VARIANTS={'CR':('context','linear'),'CT':('context','tree'),'FR':('financial','linear'),'FT':('financial','tree'),
    'MR':('matched','linear'),'AR':('augmented','linear'),'AT':('augmented','tree')}
CONTROLS=['M1','CP','F3','CR12','RP14']
ARMS=[*CONTROLS,*VARIANTS,'URTH']
LABELS={'M1':'Unchanged M1/14','CP':'M1/14 + explicit 45% final cap','F3':'Current funded F3',
    'CR12':'Unchanged monitored context ridge / 12 ETFs','RP14':'14-ETF inverse volatility','URTH':'URTH buy and hold',
    'CR':'M1/14 + context ridge','CT':'M1/14 + context tree','FR':'M1/14 + financial ridge','FT':'M1/14 + financial tree',
    'MR':'M1/14 + context ridge, augmented-matched sample','AR':'M1/14 + combined ridge','AT':'M1/14 + combined tree'}
COMPARISONS=[('CP','M1')]+[(a,'CP') for a in VARIANTS]+[(a,'M1') for a in ('CR','FR','AR')]+[
    ('CT','CR'),('FT','FR'),('AT','AR'),('AR','MR'),('FR','CR'),('AR','CR'),('CR12','F3')]
_DATA=None


def job_name(job):return f'{job[0]}-cost{job[1]}-delay{job[2]}-{job[3]}'


def jobs():return [(a,c,d,w) for a in ARMS for c,d in ((5,0),(10,0),(20,0),(5,1)) for w in ('full','evaluation')]


def cap_row(row):
    targets=FinalWeightCapOverlay().apply([AllocationTarget.model_validate(t) for t in row['targets']],None)
    return dict(row,targets=[t.model_dump(mode='json') for t in targets])


def overlay_row(parent,fitted,kind):
    original=[AllocationTarget.model_validate(t) for t in parent['targets']];targets=tilt(original,fitted,kind)
    if gross(targets)!=gross(original):raise ValueError('Economic overlay changed capped-parent cash')
    if {t.symbol for t in targets if t.target_weight>0}!={t.symbol for t in original if t.target_weight>0}:
        raise ValueError('Economic overlay changed selection membership')
    if any(t.target_weight>D('.45') for t in targets):raise ValueError('Economic cap violation')
    return dict(parent,targets=[t.model_dump(mode='json') for t in targets],economic=dict(group=fitted['group'],kind=kind,
        ready=fitted['ready'],reason=fitted['reason'],training_rows=fitted['training_rows'],
        training_sha256=fitted['training_sha256'],last_label_end=fitted['last_label_end']))


def prepare(root,runner):
    from systematic_trading.config import AppSettings
    from systematic_trading.storage.factory import create_trading_store
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.research.strategy_lifecycle import membership
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.candidate_pool import audited_bar
    from systematic_trading.recorders.economics import EconomicInputs
    from systematic_trading.research.economic_response import SPEC as context_spec
    from systematic_trading.research.economic_financial import SPEC as financial_spec,FEATURE_SPEC
    if root.exists():raise FileExistsError('Preserve frozen expanded-economics study')
    candidate=Path('var/research/candidate-pool-momentum-20261009-v1').resolve()
    financial=Path('var/research/economic-financial-20261007-v1').resolve()
    app=Path('var/tracked_strategies/baad7794e23ccaeee3d359fd6c6ee0565d6873cfd60c67e9cc31ffb5e9e991c6/usd').resolve()
    for folder,manifests in ((candidate,['input_manifest.json','decision_manifest.json','model_manifest.json']),
        (financial,['input_manifest.json','feature_manifest.json']),(app,['input_manifest.json'])):
        for manifest in manifests:checked_files(folder,manifest)
    settings=AppSettings(transactional_store_backend='postgres',market_data_store_backend='clickhouse');store=create_trading_store(settings)
    before=dict(control=control_state(store),membership=membership(settings,store),orders=[r.model_dump(mode='json') for r in store.list_broker_order_records()])
    if before['control']['sota_key']!='research_fallback_f3_v1':raise ValueError('Funded/SOTA baseline requires review')
    receipt=read_json(candidate/'data_receipt.json');old=read_json(candidate/'protocol.json')
    reader=GovernedInputs(Path('var/governance/research-2026-10-08-b1185e4ae091'),receipt['batch'])
    expected=read_json(candidate/'bars.json');bars={s:[audited_bar(r) for r in reader.rows(s,old['warmup_start'],old['end'])] for s in expected}
    if bars!=expected:raise ValueError('Published candidate prices changed')
    urth=read_json(candidate/'urth.json')
    observed=[dict(trade_date=r['trade_date'],open=str(r['adjusted_open']),close=str(r['adjusted_close'])) for r in reader.rows('URTH',old['warmup_start'],old['end'])]
    if observed!=urth:raise ValueError('Published URTH changed')
    pin=read_json(Path('var/research/economic-financial-input-pin-20261007.json'));macro=EconomicInputs(pin['root'],pin['batch'])
    if macro.catalog!=read_json(financial/'economic_catalog.json'):raise ValueError('Economic catalog differs from published pin')
    for item in macro.catalog['snapshots']:macro.snapshot(item['series'],item['vintage'])
    controls={a:read_json(candidate/'decisions'/(b+'.json')) for a,b in [('M1','M1_14'),('F3','F3'),('RP14','RP14')]}
    cr_bundle=app/'bundles/research_economic_context_ridge_v1';verify_usd_bundle(cr_bundle)
    controls['CR12']=read_json(cr_bundle/'decisions.json');controls['CP']={day:cap_row(row) for day,row in controls['M1'].items()}
    if any(list(sorted(v))!=list(sorted(controls['M1'])) for v in controls.values()):raise ValueError('Unmatched monthly decisions')
    protocol=dict(version='expanded-economics-v1',registered_at=datetime.now(UTC).isoformat(),
        start='2016-01-04',calibration_end='2020-12-31',evaluation_start='2021-01-04',end=old['end'],warmup_start=old['warmup_start'],
        initial_cash_usd='1000000',currency='USD',cash_interest='zero',arms=LABELS,variants=VARIANTS,comparisons=COMPARISONS,
        hypothesis='Do the existing economic response models add useful information to fixed M1 momentum selection on 14 candidates?',
        parent_rule='Exact frozen M1/14: original 12 plus XLE/XLB; 21/63/126 momentum, positive 126 gate, top six/minimum four, defensive-cash fallback and existing per-pool overlays. No forced holding.',
        cap_bridge='CP clips final individual M1 weights to 45%, sends excess to cash. All economic arms start from CP. CP−M1 isolates this change; every model comparison with CP preserves exact gross, cash and positive membership.',
        context_model=context_spec,financial_model=financial_spec,financial_features=FEATURE_SPEC,
        model_capacity='Reuse 13 context, 8 financial and 21 augmented features; per-ETF ridge alpha1 and tree depth2/minleaf12; expanding monthly completed labels, minimum36; no parameter search.',
        matching='MR uses context features on the same rows/current readiness as AR. Compare AR−MR for added information; CR uses original context readiness. Models refit for all 14 ETFs; no price, issuer, EIA or CFTC feature additions.',
        primary='CR−CP; financial and augmented groups plus paired trees are registered secondary comparisons. No candidate/pool/momentum retuning.',
        screen=dict(min_sharpe_gain=.05,min_calmar_gain=.05,max_cagr_sacrifice=.005,max_drawdown_worsening=.005),
        assessment='Retention requires Sharpe +0.05 and Calmar +0.05 versus CP at 5bp, CAGR sacrifice <=0.5pp and DD worsening <=0.5pp versus both CP and M1; positive Sharpe/Calmar versus CP and CAGR sacrifice <=0.5pp versus M1 at 10/20bp and one-session delay. Trees must also beat paired ridge; augmented models must beat MR. Return superiority additionally requires positive mean-return CI and Holm p<.05 in all block lengths. No automatic promotion.',
        cost_bps=[5,10,20],delay_sessions=1,bootstrap_blocks=[3,6,12],bootstrap_replications=10000,seed=2026101001,
        budget=dict(replays=len(jobs()),native=len(ARMS),comparisons=len(COMPARISONS),monthly_models=130*4),promotion_eligible=False,
        limitations=[*macro.catalog['limitations'],
            'Published audited adjusted histories are pinned, but revised/reconstructed prices do not establish historical dissemination. Current 14-ETF membership is not a survivorship-free point-in-time universe.',
            'Historical economics use the explicit prior-day ALFRED archive assumption; first actual app capture was October 2026. No current vintage or nearest-date replacement is permitted.',
            '2016–2026 was previously inspected; 2021+ is a chronological fresh-cash evaluation, not an untouched holdout. M1 was selected retrospectively in earlier research.',
            'US macro inputs are conditional predictors for global ETFs, not country-specific fundamentals or identified causal shocks. XLE/XLB are sectors, not pure single-industry baskets.',
            'Recent missing context vintages abstain to CP; prospective captures cannot repair older missing decisions. MR/AR comparisons share exact labels and availability.',
            'The explicit final cap is a separate intervention and can lower gross. Economic tilts only redistribute among positive capped-parent holdings; rejected candidates remain zero.',
            'No historical EIA/CFTC/holdings inputs are used because their publication qualification remains unresolved. No SPY dip-buying study is started.',
            'Zero-interest USD cash; no uncertified FX. Whole adjusted units, next-open fills, sale-before-buy and same-rebalance proceeds; settlement/account permission and separate spread/impact/taxes are not modeled.',
            '5/10/20bp per traded dollar. Bootstrap uses paired calendar months; multiple comparisons are jointly Holm-adjusted within each block sensitivity. Ratio intervals remain marginal.',
            'Monitored CR12 is a legacy reference with inherited activity/model limitations; CP is the matched information-effect control. Monitoring, capital and execution authority remain unchanged.'])
    root.mkdir(parents=True);write_json(root/'before.json',before);write_json(root/'protocol.json',protocol)
    shutil.copytree(Path(__file__).parents[1],root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));shutil.copy2(runner,root/'runner.py')
    write_json(root/'bars.json',bars);write_json(root/'urth.json',urth);write_json(root/'prior_features.json',read_json(financial/'features.json'))
    for a,rows in controls.items():write_json(root/'controls'/(a+'.json'),rows)
    for a,b in [('M1','M1_14'),('F3','F3'),('RP14','RP14'),('URTH','URTH')]:
        file=candidate/'python'/(b+'-cost5-delay0-full.json');bundle=candidate/'bundles'/(b+'-cost5-delay0-full')
        if read_json(file.with_suffix('.receipt.json'))!=dict(sha256=sha256(file),manifest_sha256=sha256(bundle/'manifest.json')):raise ValueError('Parent replay receipt changed')
        write_json(root/'original_economics'/(a+'.json'),read_json(file))
    write_json(root/'original_economics/CR12.json',read_json(app/'python/research_economic_context_ridge_v1.json'))
    locations=[];shutil.copytree(financial/'economic',root/'economic')
    original={(s['series'],s['vintage']):s for s in macro.catalog['snapshots']}
    for item in read_json(financial/'economic_locations.json'):
        prior=original[(item['series'],item['vintage'])]
        if {k:v for k,v in prior.items() if k!='root'}!={k:v for k,v in item.items() if k!='root'}:raise ValueError('Economic copy identity changed')
        locations.append(dict(item,root=str(root/'economic'/item['series']/item['vintage'])))
    write_json(root/'economic_catalog.json',macro.catalog);write_json(root/'economic_locations.json',locations)
    write_json(root/'data_receipt.json',dict(price_batch=receipt['batch'],governed_files=reader.used,economic_pin=pin,
        candidate=str(candidate),candidate_manifest_sha256=sha256(candidate/'input_manifest.json'),candidate_decisions_sha256=sha256(candidate/'decision_manifest.json'),
        financial=str(financial),financial_manifest_sha256=sha256(financial/'input_manifest.json'),financial_features_sha256=sha256(financial/'features.json'),
        cr12_bundle_manifest_sha256=sha256(cr_bundle/'manifest.json'),cr12_economic_sha256=sha256(app/'python/research_economic_context_ridge_v1.json'),image=receipt['image']))
    write_json(root/'input_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in root.rglob('*') if f.is_file()})
    return dict(root=str(root),protocol_sha256=sha256(root/'protocol.json'),budget=protocol['budget'])


def initialize(root):
    from systematic_trading.recorders.economics import EconomicInputs
    global _DATA
    root=Path(root);checked_files(root,'input_manifest.json');reader=object.__new__(EconomicInputs)
    reader.catalog=dict(read_json(root/'economic_catalog.json'),snapshots=read_json(root/'economic_locations.json'))
    reader.batch=read_json(root/'data_receipt.json')['economic_pin']['batch'];bars=read_json(root/'bars.json')
    _DATA=dict(root=root,p=read_json(root/'protocol.json'),reader=reader,bars=bars,opens={s:{r['trade_date']:r['open'] for r in rows} for s,rows in bars.items()},
        controls={a:read_json(root/'controls'/(a+'.json')) for a in CONTROLS})
    if (root/'features.json').exists():checked_files(root,'feature_manifest.json');_DATA['features']=read_json(root/'features.json')


def feature_decision(day):
    from systematic_trading.research.economic_financial import panel
    from systematic_trading.recorders.economics import NY
    from systematic_trading.live.trading_calendar import us_equity_market_close
    known=date.fromisoformat(_DATA['controls']['M1'][day]['known_through'])
    for rows in _DATA['controls'].values():
        if rows[day]['known_through']!=str(known):raise ValueError('Mismatched control clocks')
    return day,panel(_DATA['reader'],str(known-timedelta(days=1)),datetime.combine(known,us_equity_market_close(known),NY))


def freeze_features(root,features):
    if features!=read_json(root/'prior_features.json'):raise ValueError('Published feature reproduction changed')
    write_json(root/'features.json',features);write_json(root/'feature_manifest.json',{'features.json':sha256(root/'features.json')})


def model_decision(day):
    from systematic_trading.research.economic_response import fit_predict as context
    from systematic_trading.research.economic_financial import fit_predict as financial
    data=_DATA;known=data['controls']['M1'][day]['known_through']
    models={'context':context(day,known,data['features'],data['opens'],'combined')}
    models.update({g:financial(day,known,data['features'],data['opens'],g) for g in ('financial','matched','augmented')})
    if any(models['matched'][k]!=models['augmented'][k] for k in ('sample_sha256','ready','training_rows','last_label_end')):
        raise ValueError('Augmented and matched samples differ')
    parent=data['controls']['CP'][day]
    return day,dict(models=models,decisions={a:overlay_row(parent,models[g],kind) for a,(g,kind) in VARIANTS.items()})


def freeze_decisions(root,rows):
    for a in CONTROLS:write_json(root/'decisions'/(a+'.json'),read_json(root/'controls'/(a+'.json')))
    for a in VARIANTS:write_json(root/'decisions'/(a+'.json'),{d:rows[d]['decisions'][a] for d in sorted(rows)})
    write_json(root/'models.json',{d:rows[d]['models'] for d in sorted(rows)})
    paths=[*(root/'decisions').glob('*.json'),root/'models.json']
    write_json(root/'decision_manifest.json',{f.relative_to(root).as_posix():sha256(f) for f in paths})


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data=_DATA;root=data['root'];p=data['p'];a,c,delay,window=job;checked_files(root,'decision_manifest.json')
    bars={'URTH':read_json(root/'urth.json')} if a=='URTH' else data['bars'];days=[r['trade_date'] for r in data['bars']['SPY']]
    quotes,sessions=quotes_for_data(bars,days,p['start'] if window=='full' else p['evaluation_start'])
    if a=='URTH':decisions={sessions[0]:dict(signal_session=sessions[0],known_through=days[days.index(sessions[0])-1],targets=[
        AllocationTarget(symbol='URTH',sleeve='benchmark',target_weight=D(1),rationale='Buy and hold').model_dump(mode='json')])}
    else:decisions={d:v for d,v in read_json(root/'decisions'/(a+'.json')).items() if d>=sessions[0]}
    if delay:decisions={sessions[sessions.index(d)+delay]:v for d,v in decisions.items() if sessions.index(d)+delay<len(sessions)}
    name=job_name(job);bundle=root/'bundles'/name;freeze_usd_bundle(bundle,root,dict(arm=a,label=LABELS[a],delay_sessions=delay,window=window),decisions,quotes,sessions,c)
    out=run_usd_reference(bundle)
    if c==5 and delay==0 and window=='full' and (root/'original_economics'/(a+'.json')).exists():
        before=read_json(root/'original_economics'/(a+'.json'))
        for key in ('nav','fills','final_positions'):
            if before[key]!=out[key]:raise ValueError('Unchanged control economics differs: '+a+'/'+key)
    path=root/'python'/(name+'.json')
    if path.exists():raise FileExistsError('Preserve completed replay '+name)
    write_json(path,out);write_json(path.with_suffix('.receipt.json'),dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json')))
    return name
