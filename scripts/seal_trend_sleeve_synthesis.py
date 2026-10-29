"""Seal this descriptive handoff without changing historical strategy sources."""
from pathlib import Path
import re
from build_trend_sleeve_synthesis import ROOT,OUT,read,write,digest


def main():
    provenance=read(OUT/'provenance.json')
    assert provenance['exact_parent_return_comparisons']==612 and provenance['model_snapshots']==102
    for name,h in provenance['sources'].items():assert digest(ROOT/name)==h,name
    for name,h in provenance['batch']['files'].items():assert digest(ROOT/name)==h,name
    qa=read(OUT/'qa.json');assert qa['python_tests_passed']==5 and qa['chart_combinations']==102 and qa['allocation_previews']==10
    h=(OUT/'index.html').read_text(encoding='utf-8')
    assert not re.findall(r'__[A-Z_]+__',h)
    for link in re.findall(r'(?:href|src)="([^"]+)"',h):
        if not link.startswith(('http','#')):assert (OUT/link).exists(),link
    sources=[Path(__file__),ROOT/'scripts/build_trend_sleeve_synthesis.py',
        *[ROOT/'scripts/assets'/('trend-sleeve-'+name) for name in ['synthesis.html','synthesis.js','equations.json']],
        ROOT/'tests/test_trend_sleeve_synthesis.py',ROOT/'tests/trend_sleeve_synthesis_controls.cjs',
        ROOT/'docs/trend-sleeve-synthesis-2026-10-29.md']
    write(OUT/'manifest.json',dict(files={p.name:digest(p) for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        sources={p.relative_to(ROOT).as_posix():digest(p) for p in sources}))
    print('Sealed synthesis; sources, published input files, links and QA verified.')


if __name__=='__main__':main()
