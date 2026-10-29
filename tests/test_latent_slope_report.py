from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_latent_slope_report import weakest_training_choice,static_figure  # noqa:E402


def test_weakest_uses_chosen_policy_and_declared_primary_case():
    def row(symbol,value,**kw):
        return dict(symbol=symbol,cumulative=value,era='late',variant='selected',cost_bp=5,delay=0)|kw
    rows=[row('BIL',-.99),row('Y',-.2),row('X',-.2),row('Z',-.9,variant='slope'),
          row('Q',-.8,cost_bp=20),row('R',-.7,delay=1),row('S',-.6,era='early')]
    assert weakest_training_choice(rows,'late')['symbol']=='X'
    assert weakest_training_choice(rows,'early')['symbol']=='S'


def test_static_chart_accepts_null_training_context_from_json_cache(tmp_path):
    c=dict(days=['2022-12-29','2022-12-30','2023-01-03','2023-01-04'],
           close=[100,101,100,102],volume=[1e6]*4,trades=[],old_trades=[],evaluation_start='2023-01-03')
    for field in ('slow_level','fast_level','stop','fast_up','fast_down','slow_up','slow_down',
                  'slow_slope','fast_slope','slow_lo','slow_hi','nav','baseline','buyhold'):
        c[field]=[None,None,1.,2.]
    output=tmp_path/'cached.png'
    static_figure(c,output,'Cached context regression')
    assert output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
