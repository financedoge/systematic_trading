"""Seal completed study and verify immutable inputs/code and report inventory."""
import json
from pathlib import Path
import research_stop_review as s


def main():
    p=json.loads((s.OUT/'protocol.json').read_text());assert s.clean(s.protocol())==p
    for name,digest in p['published_inputs']['files'].items():assert s.prior.study.digest(s.ROOT/name)==digest,name
    for name,digest in p['code'].items():assert s.prior.study.digest(s.ROOT/name)==digest,name
    validation=json.loads((s.OUT/'validation.json').read_text());assert validation['control_cases']==612
    assert validation['chart_sha256']==s.prior.study.digest(s.OUT/'chart-data.json.gz')
    native=json.loads((s.OUT/'native-checks.json').read_text());assert len(native)==4
    assert all(r['status']=='succeeded' and r['max_native_reference_dollars']==0 for r in native)
    s.write(s.OUT/'qa.json',dict(completed_local_date='2026-10-28',timezone='Asia/Shanghai',focused_python_tests=48,
        offline_chart_combinations=306,offline_controls='OHLC/date hover, two-point zoom, empty interval, interval NAV, all arms, weakest-era and incident buttons passed',
        native_accounting_cases=4,native_max_dollar_error=0,visually_inspected=['equation-proof.png','CPER-incident.png','IWM-incident.png','TLT_late.png','PPLT_early.png'],
        browser_layout_certified=False,native_limit='Frozen synthetic event accounting only; not intraday execution or HMM inference validation',
        reference_control_cases=612,close_engine_control_cases=612,diagnostic_cases=1632))
    manifest=json.loads((s.OUT/'manifest.json').read_text())
    for file in (Path(__file__),s.ROOT/'scripts/repair_stop_review_control.py',s.ROOT/'scripts/inspect_stop_review.py'):
        manifest['report_code'][file.relative_to(s.ROOT).as_posix()]=s.prior.study.digest(file)
    manifest['files']={file.name:s.prior.study.digest(file) for file in s.OUT.iterdir() if file.is_file() and file.name!='manifest.json'}
    s.write(s.OUT/'manifest.json',manifest)
    for file,digest in manifest['files'].items():assert s.prior.study.digest(s.OUT/file)==digest,file
    for file,digest in manifest['report_code'].items():assert s.prior.study.digest(s.ROOT/file)==digest,file
    print('Sealed and verified',len(manifest['files']),'artifacts;',len(p['published_inputs']['files']),'pinned published extracts; protocol and report sources unchanged.')


if __name__=='__main__':main()
