"""Post-evaluation semantic audit; descriptive, never feeds selection."""
import json
from pathlib import Path
import numpy as np
import research_regime_entry as study


def main():
    market,_,_,_,selected=study.verified();rows=[];incidents={}
    for symbol in sorted(market):
        full=study.prior.model.Features.build(study.prior.study.load_asset(symbol))
        for era,_,first,last in study.ERAS:
            if era not in selected[symbol]:continue
            f=full.truncated(last);f.hmm_models=market[symbol][era]['hmms']
            p=market[symbol][era]['selected']['selected']['parameters'];q=selected[symbol][era]
            cl=study.model.classification(f,p,q['exit_rule'],q['hmm']['model'])
            valid=f.days>=np.datetime64(first);prob=cl['fast_probability'];z=cl['fast_slope']/cl['sigma']
            opposite_down=valid&(z>0)&(prob[:,0]>=.8);opposite_up=valid&(z<0)&(prob[:,2]>=.8)
            rows.append(dict(symbol=symbol,era=era,days=int(valid.sum()),down_score_above80_with_positive_slope=int(opposite_down.sum()),
                up_score_above80_with_negative_slope=int(opposite_up.sum()),directional_variances=q['hmm']['model']['variance'],
                meaning='Descriptive semantic mismatch, not latent-state accuracy against ground truth. No refit or result selection from this audit.'))
            if symbol in ('ITA','TLT','INDA','WEAT'):
                incidents[f'{symbol}_{era}']=[dict(day=str(f.days[t]),close=float(f.close[t]),normalized_fast_slope=float(z[t]),
                    down=float(prob[t,0]),range=float(prob[t,1]),up=float(prob[t,2])) for t in np.flatnonzero(opposite_down|opposite_up)]
    study.write(study.OUT/'state-semantics-audit.json',dict(rows=rows,incidents=incidents,
        protocol_sha256=study.prior.study.digest(study.OUT/'protocol.json'),script_sha256=study.prior.study.digest(Path(__file__)),
        verdict='Reject directional interpretation of unconstrained unequal-variance Gaussian tails; implementation checks do not certify economic labels.'))
    for era in ('late','early'):
        a=[r for r in rows if r['era']==era and r['symbol']!='BIL']
        print(era,'ETFs with opposite-sign high-confidence state',sum(r['down_score_above80_with_positive_slope']+r['up_score_above80_with_negative_slope']>0 for r in a),
              'down/positive sessions',sum(r['down_score_above80_with_positive_slope'] for r in a),'up/negative sessions',sum(r['up_score_above80_with_negative_slope'] for r in a),flush=True)


if __name__=='__main__':main()
