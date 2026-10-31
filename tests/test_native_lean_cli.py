import runpy

import pytest


def test_native_cli_does_not_require_a_container_image(tmp_path,monkeypatch):
    main=runpy.run_path('scripts/run_lean_backtest.py')['main']
    calls=[]
    monkeypatch.setitem(main.__globals__,'run_bundle',lambda **kwargs: calls.append(kwargs))
    monkeypatch.setenv('ST_LEAN_RUNTIME_BACKEND','native')
    monkeypatch.setattr('sys.argv',['run_lean_backtest.py','--bundle',str(tmp_path/'inputs'),
                                  '--output',str(tmp_path/'outputs')])
    main()
    assert calls[0]['runtime']=='native' and calls[0]['image'] is None


@pytest.mark.parametrize('script,args',[
    ('run_lean_backtest.py',['--bundle','unused','--output','unused']),
    ('validate_lean_integration.py',['--root','unused']),
])
def test_legacy_cli_still_requires_pinned_image(script,args,monkeypatch):
    main=runpy.run_path('scripts/'+script)['main']
    monkeypatch.setattr('sys.argv',[script,*args,'--runtime','docker'])
    with pytest.raises(SystemExit) as error:main()
    assert error.value.code==2


@pytest.mark.parametrize('memory',[None,'1g'])
def test_native_runner_has_no_implicit_docker_quota(tmp_path,monkeypatch,memory):
    from systematic_trading.lean import runner,native_runner
    calls=[]
    monkeypatch.setattr(native_runner,'run_native_bundle',lambda **kwargs:calls.append(kwargs))
    runner.run_bundle(bundle=tmp_path/'bundle',output=tmp_path/'output',runtime='native',memory=memory)
    assert calls[0]['memory']==memory
