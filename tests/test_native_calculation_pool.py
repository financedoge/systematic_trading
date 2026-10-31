from dataclasses import replace
import json
import os
from pathlib import Path
import shutil

import pytest

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.lean.fixtures import make_fixture_bundle


pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows calculation integration')


def test_native_usd_parallel_preparation_preserves_targets_fills_and_nav(tmp_path):
    from systematic_trading.research.native_usd_preparation import prepare
    from systematic_trading.research.strategy_catalog import risk_parity_definition
    from systematic_trading.research.momentum_replay import read_json
    fixture=tmp_path/'fixture';make_fixture_bundle(fixture)
    bars=read_json(fixture/'bars.json')
    outputs=[]
    for name,workers in [('serial',1),('parallel',2)]:
        root=tmp_path/name;root.mkdir()
        shutil.copytree(Path('src/systematic_trading'),root/'source/systematic_trading',
            ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        definition=risk_parity_definition()
        write_json(root/'worker.json',dict(bars=bars,rolling=None,base_models={},usd=None,economic=None,
            definitions=[definition.to_dict(),replace(definition,key='engineering-control').to_dict()]))
        write_json(root/'protocol.json',dict(initial_cash_usd='10000',limitations=['Synthetic engineering fixture']))
        write_json(root/'input_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()})
        receipt={}
        result=prepare(root,start='2024-11-01',cost='5',max_workers=workers,receipt=receipt)
        assert receipt['workers']==workers and receipt['replay_workers']==workers
        assert receipt['aggregate_memory_limit_bytes'] is None
        assert receipt['memory_policy']=='windows_managed'
        outputs.append((root,{k:{f:v for f,v in value.items() if f!='elapsed_seconds'} for k,value in result.items()}))
    assert outputs[0][1]==outputs[1][1]
    for key in outputs[0][1]:
        assert read_json(outputs[0][0]/'bundles'/key/'decisions.json')==read_json(outputs[1][0]/'bundles'/key/'decisions.json')


def test_native_parallel_model_fits_match_serial_models(tmp_path):
    import sys
    from datetime import date,timedelta
    from systematic_trading.lean.windows_worker import run
    from systematic_trading.research.rolling_tracking import rolling_xgboost_spec
    from systematic_trading.research.strategy_catalog import current_sota_definition
    from systematic_trading.research import instruments_for_definition
    fixture=tmp_path/'fixture';make_fixture_bundle(fixture)
    bars=json.loads((fixture/'bars.json').read_text())
    # Full feature warmup before the one-year fitting window: the ordinary
    # replay fixture is deliberately too short for 100 asset-month fit rows.
    from systematic_trading.live.trading_calendar import is_us_trading_day
    prior=[date(2022,1,1)+timedelta(days=i) for i in range(365)]
    prior=[str(day) for day in prior if is_us_trading_day(day)]
    bars={symbol:[dict(rows[i],trade_date=day) for i,day in enumerate(prior)]+rows
        for symbol,rows in bars.items()}
    schedules=[]
    for name,workers in [('serial',1),('parallel',2)]:
        root=tmp_path/name;root.mkdir()
        attempt=root/'attempt';attempt.mkdir()
        cache=root/'fits';cache.mkdir()
        # Each model root gets an independent cache, so equality cannot come
        # from the parallel branch simply reading the serial branch's fits.
        model=root/'model';model.mkdir()
        write_json(model/'request.json',dict(recipe=rolling_xgboost_spec(),bars=bars,
            symbols=list(instruments_for_definition(current_sota_definition())),start='2024-11-01',max_workers=workers))
        source=Path('src').resolve()
        run([sys.executable,'-B','-m','systematic_trading.research.rolling_training',str(model),str(attempt)],
            output=attempt,read_roots=[model,source,Path(sys.prefix),Path(sys.base_prefix)],write_roots=[cache],
            environment={'PYTHONPATH':str(source)},cpus=16,timeout=90)
        receipt=json.loads((attempt/'receipt.json').read_text())
        assert receipt['workers']==workers and receipt['reused_fits']==0
        schedules.append(json.loads((attempt/'schedule.json').read_text()))
    assert schedules[0]==schedules[1]
