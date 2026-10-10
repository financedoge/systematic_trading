"""Independent rank-correlation checks and local artifact acceptance."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

import numpy as np
from scipy.stats import spearmanr

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.expanded_economics import VARIANTS

ROOT = Path('var/research/full-pool-signal-diagnostics-20261010-v1')
OUT = Path('research/full-pool-signal-diagnostics-2026-10-10')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('src','href'):
            if key in attrs:
                self.links.append(attrs[key])


def verify():
    data = read_json(ROOT/'analysis.json')
    base = Path(data['protocol']['parent'])
    receipt = read_json(ROOT/'analysis_receipt.json')
    for key,file in [('analysis','analysis.json'),('protocol','protocol.json'),('parent_receipt','parent_receipt.json')]:
        assert receipt[key]==sha256(ROOT/file)
    for file,h in receipt['sources'].items():
        assert sha256(ROOT/'source'/file)==h
    for file,h in read_json(ROOT/'parent_receipt.json').items():
        assert sha256(base/file)==h
    presentation = read_json(ROOT/'presentation_receipt.json')
    assert presentation['analysis_sha256']==sha256(ROOT/'analysis.json')
    for file,h in presentation['files'].items():
        assert sha256(OUT/file)==h
    assert presentation['renderer_sha256']==sha256(Path('scripts/render_full_pool_diagnostics.py'))
    assert receipt['sources']['full_pool_diagnostics.py']==sha256(Path('src/systematic_trading/research/full_pool_diagnostics.py'))
    parser = Links()
    parser.feed((OUT/'index.html').read_text(encoding='utf8'))
    for link in parser.links:
        if link.startswith('#'):
            assert link[1:] in parser.ids,link
        elif not urlsplit(link).scheme:
            assert (OUT/unquote(urlsplit(link).path)).exists(),link
    models = read_json(base/'models.json')
    bars = read_json(base/'bars.json')
    opens = {s:{r['trade_date']:float(r['open']) for r in rows} for s,rows in bars.items()}
    symbols = sorted(bars)
    prior = read_json(base/'diagnostics.json')
    count = 0
    for record in data['forecast']['records']:
        if not record['ready']:
            continue
        group,kind = VARIANTS[record['arm']]
        model = models[record['decision']][group]['models']
        realized = np.array([opens[s][record['label_end']]/opens[s][record['decision']]-1 for s in symbols])
        for metric,field in [('total_ic',kind+'_forecast'),('increment_ic',kind+'_increment'),('mean_ic','mean_return')]:
            expected = spearmanr([model[s][field] for s in symbols],realized).statistic
            assert abs(record[metric]-expected)<1e-12
            count += 1
        active = np.array([record['delta_weights'][s] for s in symbols])
        assert abs(active@realized-record['gross_return_delta'])<1e-12
    for arm,row in data['forecast']['summary'].items():
        group,kind = VARIANTS[arm]
        assert abs(row['total_ic']-prior['forecast_summary'][group+'/'+kind+'/all14']['rank_ic'])<1e-12
    result = dict(status='passed',independent_scipy_correlations=count,
        completed_weight_return_attributions=len(data['forecast']['records']),
        all_prior_total_ics_reproduced=True,source_and_artifact_hashes=True,
        local_links_and_anchors=len(parser.links),parent_entries=sum(data['verified_files'].values()),
        analysis_sha256=sha256(ROOT/'analysis.json'),presentation_receipt_sha256=sha256(ROOT/'presentation_receipt.json'),
        verification_source_sha256=sha256(Path(__file__)),
        scope='Read-only analysis of frozen evidence; no new strategy arm or service/execution mutation.')
    write_json(ROOT/'acceptance.json',result)
    print(result)


if __name__=='__main__':
    verify()
