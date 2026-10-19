"""Independent Windows-native accounting replay for the GLD daily diagnostic."""
from pathlib import Path
import numpy as np
from run_joint_breakout import ROOT as PARENT, asset, check, read, write, digest, SingleReplay, transitions
from build_gld_drilldown import ROOT
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    check(PARENT)
    if AppSettings().lean_runtime_backend != 'native':
        raise ValueError('Native Windows engine required')
    a=asset('GLD');signal=np.load(PARENT/'evaluation/GLD/signal.npz')['active']
    runner=SingleReplay(a,'GLD','2024-01-01')
    indices=transitions(signal,a['days'],'2024-01-01','event')
    path,economic,_=runner.run(.98*signal[:,None],indices,5,0,detailed=True)
    rows=runner.decisions(.98*signal[:,None],indices,0);days=a['days'].tolist()
    decisions={str(d):dict(signal_session=str(d),known_through=days[days.index(str(d))-1],
        targets=[t.model_dump(mode='json') for t in targets]) for d,targets in rows.items()}
    quotes={s:{str(d):{k:str(source[d][s]) for k,source in (('open',runner.open),('close',runner.close),('reference',runner.reference))}
        for d in runner.days} for s in runner.symbols}
    recipe=dict(id='gld_daily_diagnostic_v1',universeKey='GLD',
        universeMembers=[x.model_dump(mode='json') for x in runner.members.values()])
    bundle=ROOT/'native_bundle';output=ROOT/'native'
    freeze_usd_bundle(bundle,PARENT,recipe,decisions,quotes,runner.day_strings.tolist(),5)
    image=read(Path('config/strategy-monitoring.json'))['calculation']['image']
    receipt=native_parity(bundle,output,image,cpus='2');result=read(output/'economic.json')
    delta=float(np.max(np.abs(np.array([float(r['nav']) for r in result['nav']])-path['nav'])))
    if delta>.011 or result['fills']!=economic['fills']:
        raise ValueError('Daily engine mismatch')
    proof=dict(status=receipt['status'],maximum_nav_error_usd=delta,fills=len(result['fills']),
        bundle_manifest_sha256=digest(bundle/'manifest.json'),artifacts_sha256=digest(output/'artifact_manifest.json'),
        parity=read(output/'parity.json'))
    write(ROOT/'native_verification.json',proof)
    print(proof)


if __name__=='__main__':
    main()
