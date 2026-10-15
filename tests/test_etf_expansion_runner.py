"""Resumed studies execute only their verified frozen source."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('valid', [True, False])
def test_resume_checks_source_before_running_it(tmp_path, valid):
    runner=tmp_path/'source/run_etf_expansion.py';runner.parent.mkdir()
    runner.write_text("print('verified frozen runner')\n",encoding='utf8')
    expected=hashlib.sha256(runner.read_bytes()).hexdigest() if valid else '0'*64
    (tmp_path/'input_manifest.json').write_text(json.dumps({'source/run_etf_expansion.py':expected}))
    project=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(project/'scripts/run_etf_expansion.py'),
        'replay','--root',str(tmp_path)],capture_output=True,text=True,timeout=15)
    if valid:
        assert result.returncode==0 and result.stdout.strip()=='verified frozen runner'
    else:
        assert result.returncode!=0 and 'Frozen research input hash mismatch' in result.stderr
        assert 'verified frozen runner' not in result.stdout
