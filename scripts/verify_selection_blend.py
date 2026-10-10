"""Independent rank, eligibility, causality and artifact acceptance checks."""
from decimal import Decimal as D
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json
import re
import subprocess

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import checked_files,read_json
from systematic_trading.research.selection_blend import ARMS,VARIANTS,BLENDS

ROOT=Path('var/research/selection-blend-20261010-v1')
OUT=Path('research/selection-blend-2026-10-10')


def exact_ranks(values):
    order=sorted(values,key=lambda s:(values[s],s))
    result={}
    i=0
    while i<len(order):
        end=i+1
        while end<len(order) and values[order[end]]==values[order[i]]:
            end+=1
        rank=Fraction(i+end-1,len(order)-1)-1
        for s in order[i:end]:
            result[s]=rank
        i=end
    return result


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs=[]
        self.ids=set()

    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src') and v:
                self.refs.append(v)
            elif k=='id':
                self.ids.add(v)


def verify():
    checked_files(ROOT,'input_manifest.json')
    checked_files(ROOT,'decision_manifest.json')
    receipt=read_json(ROOT/'data_receipt.json')
    for file,h in receipt['parents'].items():
        assert sha256(Path(file))==h
    report=read_json(ROOT/'report.json')
    assert sha256(ROOT/'report.json')==read_json(ROOT/'report_receipt.json')['sha256']
    macro=read_json(ROOT/'macro.json')
    xgb=read_json(ROOT/'forecasts.json')
    parent=read_json(ROOT/'parent_selection.json')
    selection=read_json(ROOT/'selection.json')
    cp=read_json(ROOT/'decisions/CP.json')
    checked,rank_cells=0,0
    for a,recipe in VARIANTS.items():
        decisions=read_json(ROOT/'decisions'/(a+'.json'))
        for day,row in decisions.items():
            q=selection[day][a]
            w={t['symbol']:D(t['target_weight']) for t in row['targets']}
            assert set(w)==set(xgb[day]) and len(w)==14
            assert len([v for v in w.values() if v>0])<=6 and all(0<=v<=D('.45') for v in w.values())
            eligible=set(parent[day]['M1_14']['eligible'])
            assert set(q['eligible'])==eligible
            assert set(q['selected']).issubset(eligible)
            original={s:D(v['total']) for s,v in parent[day]['M1_14']['scores'].items()}
            mr=exact_ranks(original)
            xr=exact_ranks({s:D(str(v)) for s,v in xgb[day].items()})
            if recipe['blend']:
                weights=BLENDS[recipe['blend']]
                rr={s:Fraction(0) for s in mr}
                m=macro[day][recipe['group']] if recipe['group'] else None
                missing=bool(weights[2] and not m['ready'])
                assert q['abstained']==missing
                if weights[2] and not missing:
                    field='mean_return' if recipe.get('mean_only') else 'linear_forecast'
                    rr=exact_ranks({s:D(str(v[field])) for s,v in m['models'].items()})
                expected={}
                for s in mr:
                    value=(weights[0]*mr[s]+weights[1]*xr[s]+weights[2]*rr[s])/sum(weights)
                    expected[s]=original[s] if missing else (D(value.numerator)/D(value.denominator)).quantize(D('1e-18'))
                    assert abs(D(q['rank_table'][s]['combined'])-expected[s])<D('1e-20')
                    rank_cells+=1
            else:
                expected=original
            chosen=set(sorted(eligible,key=lambda s:(-expected[s],s))[:6]) if len(eligible)>=4 else eligible&{'IEF','TLT','GLD'}
            assert set(q['selected_before_downstream'])==chosen
            assert set(q['selected']).issubset(chosen)
            if q['abstained'] and not recipe.get('remove_xgb') and not recipe.get('match_gross'):
                assert w=={t['symbol']:D(t['target_weight']) for t in cp[day]['targets']}
            if recipe.get('match_gross') and q['gross_control']['matched']:
                assert sum(w.values())==sum(D(t['target_weight']) for t in cp[day]['targets'])
            if recipe['group']:
                m=macro[day][recipe['group']]
                assert all(v['end']<=row['known_through'] and v['vintage']<v['start'] for v in m['training_labels'])
            checked+=1
    # Poison current/future observations in memory. Prior-close decisions must be identical.
    from systematic_trading.research import selection_blend_study as study
    study.initialize(ROOT)
    day='2025-04-01'
    _,before=study.decision(day)
    for key in ('typed','raw'):
        for symbol,rows in study._DATA[key].items():
            study._DATA[key][symbol]=[r.model_copy(update=dict(close=D('999999'),open=D('888888'),volume=1))
                                     if str(r.trade_date)>=day else r for r in rows]
    for future in list(study._DATA['macro']):
        if future>day:
            study._DATA['macro'][future]={}
    for future in list(study._DATA['models']['rolling']):
        if future>=day:
            study._DATA['models']['rolling'][future]={}
    _,after=study.decision(day)
    assert before==after
    presentation=read_json(ROOT/'presentation_receipt.json')
    assert presentation['report_sha256']==sha256(ROOT/'report.json')
    for file,h in presentation['files'].items():
        assert sha256(OUT/file)==h
    for a,receipt in presentation['native'].items():
        native=ROOT/'native'/(a+'-cost5-delay0-full')
        assert sha256(native/'run.json')==receipt['run'] and sha256(native/'parity.json')==receipt['parity']
        assert read_json(native/'run.json')['status']=='succeeded' and read_json(native/'parity.json')['passed']
    scripts=ROOT/'validation_scripts'
    scripts.mkdir(exist_ok=True)
    shared=[]
    for file in OUT.rglob('*.html'):
        text=file.read_text(encoding='utf8')
        parser=Links()
        parser.feed(text)
        for ref in parser.refs:
            u=urlsplit(ref)
            if not u.scheme and u.path:
                assert (file.parent/unquote(u.path)).exists(),(file,ref)
            elif not u.path and u.fragment:
                assert u.fragment in parser.ids
        if 'const report = ' in text:
            data,_=json.JSONDecoder().raw_decode(text.split('const report = ',1)[1])
            assert data['accountingCurrency']=='USD' and data['decisionDiagrams'] and len(data['benchmarkOptions'])>=5
            shared.append(file.name)
        for i,script in enumerate(re.findall(r'<script\b[^>]*>(.*?)</script>',text,re.S|re.I)):
            f=scripts/(file.stem+'-'+str(i)+'.js')
            f.write_text(script,encoding='utf8')
            process=subprocess.run(['node','--check',str(f)],capture_output=True,text=True)
            assert process.returncode==0,process.stderr
    assert len(shared)==len(ARMS)
    # Exercise our own artifact's rendering/event code in a minimal DOM, without browser access.
    harness=r'''const fs=require('fs'),vm=require('vm');
    class Element{constructor(){this.value='';this.children=[];this.events={};this.textContent='';this.className='';}
    appendChild(v){this.children.push(v);}replaceChildren(){this.children=[];}addEventListener(k,v){this.events[k]=v;}}
    const elements={arm:new Element(),day:new Element(),'rank-body':new Element(),'rank-note':new Element()};elements.arm.value='CEQ';
    const context={document:{getElementById:id=>elements[id],createElement:()=>new Element()},console};vm.createContext(context);
    vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
    const count=vm.runInContext(`(()=>{let n=0;for(const d of days){day.value=d;for(const a of Object.keys(snapshots[d])){arm.value=a;display();const rows=document.getElementById('rank-body').children;if(rows.length!==14)throw Error('Wrong rank row count');const chosen=rows.filter(r=>r.className==='chosen').length;if(chosen!==snapshots[d][a].selected.length)throw Error('Wrong selection highlighting');n++;}}return n;})()`,context);
    console.log(count);'''
    harness_path=scripts/'dom-check.cjs'
    harness_path.write_text(harness,encoding='utf8')
    process=subprocess.run(['node',str(harness_path),str(scripts/'index-0.js')],capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    result=dict(status='passed',protocol_sha256=sha256(ROOT/'protocol.json'),report_sha256=sha256(ROOT/'report.json'),
        rank_cells_independently_checked=rank_cells,selection_gate_cap_label_checks=checked,
        future_price_and_model_poison_invariance=True,full_controls_replayed_exactly=len(report['control_parity']),
        economic_replays=len(report['results']),native_checks=len(presentation['native']),inference_jobs=len(read_json(ROOT/'inference.json')),
        shared_reports=len(shared),rank_table_states_exercised=int(process.stdout.strip()),
        source_artifact_hashes=True,local_links=True,javascript_syntax=True,
        browser_ui='Not automated: browser security policy blocks file URLs; used source/DOM harness and static chart inspection.',
        verifier_sha256=sha256(Path(__file__)),no_app_or_execution_mutations=True)
    write_json(ROOT/'acceptance.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    verify()
