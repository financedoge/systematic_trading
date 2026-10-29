"""One recorded correctness amendment, before accepting evaluation results."""
from concurrent.futures import ProcessPoolExecutor
import json
import research_stop_review as s


def main():
    if (s.OUT/'asset-results.json').exists():raise ValueError('Cannot amend accepted evaluation')
    assert s.prior.study.digest(s.OUT/'protocol-before-control-fix.json')=='768cfe132021d93010d567c99e57ddd0f5a6807c07ec1b1a69a157adecbe25b3'
    market,_,_,_,_,selected=s.previous.verified();oldfits=json.loads((s.WORK/'fits-before-control-fix.json').read_text());newfits={}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol,value in pool.map(s.fit_asset,[(k,{k:market[k]},{k:selected[k]}) for k in sorted(market)]):newfits[symbol]=value
    s.write(s.OUT/'protocol.json',s.protocol());s.write(s.OUT/'fits.json',newfits)
    s.write(s.OUT/'fit-manifest.json',dict(protocol=s.prior.study.digest(s.OUT/'protocol.json'),fits=s.prior.study.digest(s.OUT/'fits.json')))
    receipt=dict(reason='Full-pool control validation found opening exit fills erased rearming observed during a delayed exit wait. Preserve that rearm; allow ordinary signal at exit close for subsequent-open entry. Recovery still requires a later session; protective exits invalidate/rearm independently.',
        evidence='Original B matched saved 612 cases exactly; 30 delayed control cases differed in new close-only event engine. No evaluation summary or returns were accepted; fix is contract parity, not tuned performance.',
        previous_protocol=s.prior.study.digest(s.OUT/'protocol-before-control-fix.json'),new_protocol=s.prior.study.digest(s.OUT/'protocol.json'),
        training_cases_changed=sum(newfits[k][e]!=oldfits[k][e] for k in newfits for e in newfits[k]),
        regression_tests=s.prior.study.digest(s.ROOT/'tests/test_stop_review_contract.py'),
        original_control_errors=s.prior.study.digest(s.WORK/'checks.json'))
    s.write(s.OUT/'correctness-amendment.json',receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
