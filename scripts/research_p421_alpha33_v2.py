"""Same frozen strategy, separately qualified CRSP raw open/close publication."""
from pathlib import Path
from datetime import UTC, datetime

from research_p421_alpha33 import ROOT, QUARTER, START, END, checked, digest, read, write, positions

OUT=ROOT/'research/p421-alpha33-pilot-20261108-v2'
WORK=ROOT/'var/research'/OUT.name


def freeze():
    if (OUT/'protocol.json').exists():
        raise FileExistsError('V2 protocol already frozen')
    parent=ROOT/'research/p421-alpha33-pilot-20261107-v1'
    p=read(parent/'protocol.json')
    p.update(id=OUT.name,frozen_at=datetime.now(UTC).isoformat(),
        parent_protocol_sha256=digest(parent/'protocol.json'),
        parent_results_sha256=digest(parent/'results.json'),
        amendment='Data expansion only. V1 produced no alpha trades: five ETFs passed the unchanged 95% value/70% name gate. Retain it as a coverage-limited run. V2 uses a newly audited, single-provider CRSP raw open/close panel, never a silent source splice. Same formula, holdings quarter, dates, construction, timing, costs and controls; no performance selection.',
        identity='Unique filed valid CUSIP9 (or previously declared embedded identifier) to a dated CRSP PERMNO; exactly one CIZ interval and matching daily CUSIP on each observation date. Tickers are labels, not join keys. Duplicates/ambiguity remain missing.',
        price_audit='Audited single-provider CRSP raw open/close, published before strategy access. Require uniquely dated permanent identity, daily CUSIP match, valid trade-close flag TR, positive finite open/close, no duplicate security/date and expected US sessions. Reconcile overlaps against the pinned continuous history using inherited 0.5% relative price tolerance; quarantine conflicting overlaps. Missing independent overlaps are explicitly single-source observations, not filled values or claimed independent confirmations. Audit original source SQL/types/row hashes and native publication readback. No constituent volume, cross-session stock return or fabricated adjusted levels are consumed.',
        input_basis='Raw traded stock open/close for the same-session Alpha33 ratio; common split/dividend factors cancel. ETF portfolio returns, sizing, vol and momentum continue to use the existing pinned split/dividend-adjusted histories. No raw stock return series is presented as total return.',
        source_capture=read(parent/'capture.json'),
        prior_field_audit_sha256=digest(parent/'publication.json'),
        prior_field_auditor_sha256=digest(ROOT/'scripts/qualify_p421_alpha33.py'),
        independent_check='Every available historical overlap is checked; uncorroborated rows remain explicitly labelled single_source_audited. This is a retrospective data qualification, not original-vintage certification or execution readiness.',
        code_at_freeze={f.relative_to(ROOT).as_posix():digest(f) for f in [Path(__file__),ROOT/'scripts/capture_p421_alpha33.py',ROOT/'scripts/qualify_p421_alpha33.py']})
    p['limitations'].append('CRSP-only observations without an independent existing overlap are admitted after source/identity/field/session checks and labelled single-source. Historical availability and corporate-action vintage are not certified; no constituent total returns are inferred.')
    p['reuse_reviews'].append(dict(asset='crsp-raw-open-close-research-v1',decision='New isolated finite native publication, keyed by permanent security ID. Existing adjusted price and activity services untouched. No runtime registration or promotion.'))
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    write(OUT/'protocol.json',p)
    print('V2 data amendment frozen',digest(OUT/'protocol.json'),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    checked(QUARTER/'artifact-manifest.json',p['holdings_manifest_sha256'])
    for name,h in p['code_at_freeze'].items():
        checked(ROOT/name,h)
    return p


if __name__=='__main__':
    freeze()
