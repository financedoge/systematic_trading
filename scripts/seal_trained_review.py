"""Seal completed research; never mutate frozen strategy or parameters."""
import json
from pathlib import Path
import research_trained_review as s


def main():
    p=json.loads((s.OUT/'protocol.json').read_text())
    assert s.clean(s.protocol())==p
    for name,digest in p['published_inputs']['files'].items():assert s.prior.study.digest(s.ROOT/name)==digest,name
    for name,digest in p['code'].items():assert s.prior.study.digest(s.ROOT/name)==digest,name
    validation=json.loads((s.OUT/'validation.json').read_text())
    assert validation['control_cases']==612 and validation['asset_cases']==1836
    assert validation['chart_sha256']==s.prior.study.digest(s.OUT/'chart-data.json.gz')
    native=json.loads((s.OUT/'native-checks.json').read_text())
    assert len(native)==4 and all(r['status']=='succeeded' and r['max_native_reference_dollars']<=.011 for r in native)
    qa=json.loads((s.OUT/'qa.json').read_text())
    assert qa['offline_chart_combinations']==306 and qa['focused_python_tests']==41
    files=[Path(__file__),*[s.ROOT/f'scripts/{name}_trained_review.py' for name in ('analyze','inspect','validate')],
        s.ROOT/'scripts/build_trained_review_report.py',s.ROOT/'scripts/assets/trained-review-script.js',
        s.ROOT/'scripts/assets/trained-review-template.html',s.ROOT/'tests/trained_review_controls.cjs',
        s.ROOT/'tests/test_trained_review_contract.py',s.ROOT/'docs/trained-review-results-2026-10-28.md']
    manifest=dict(files={f.name:s.prior.study.digest(f) for f in s.OUT.iterdir() if f.is_file() and f.name!='manifest.json'},
        report_code={f.relative_to(s.ROOT).as_posix():s.prior.study.digest(f) for f in files})
    s.write(s.OUT/'manifest.json',manifest)
    for name,digest in manifest['files'].items():assert s.prior.study.digest(s.OUT/name)==digest
    print('Sealed',len(manifest['files']),'artifacts; frozen protocol, inputs and sources verified.')


if __name__=='__main__':main()
