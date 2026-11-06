"""Prepare the completed item's evidence review and compact retention classification."""
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import research_expanded_fr25_net as s
from systematic_trading.research.evidence_review import assess


def main():
    p=s.validate()
    plan=s.read(s.OUT/'analysis-plan.json')
    if plan['results_exist']:raise ValueError('Analysis recipe was not frozen before results')
    for path,expected in plan['files'].items():
        if s.digest(s.REPO/path)!=expected:raise ValueError('Analysis code differs from preregistered recipe: '+path)
    for name in ('model-manifest.json','signal-manifest.json','result-manifest.json'):
        s.check_manifest(s.OUT/name)
    summary=s.read(s.OUT/'review-summary.json');native=s.read(s.OUT/'native-validation.json')
    if len(native['cases'])!=3 or any(r['status']!='succeeded' or r['max_nav_error_usd']>.01 for r in native['cases']):
        raise ValueError('Native validation incomplete')
    policy=s.REPO/'config/research-evidence-policy-v1.json'
    roles={'protocol.json':['protocol'],'definitions.json':['strategy_recipe'],
        'input-verification.json':['published_input_verification'],'selection.json':['selection'],
        'results.json':['net_results','cost_delay','chronology'],'comparisons.json':['matched_controls'],
        'uncertainty.json':['uncertainty'],'signal-diagnostics.json':['decay_stability'],
        'training-stability.json':['decay_stability'],'native-validation.json':['independent_validation'],
        'monthly-target-parity.json':['independent_validation'],'results.md':['weakest_inspections']}
    roles.update({f.name:['weakest_inspections'] for f in s.OUT.glob('weakest-*.png')})
    dossier=dict(schema_version=1,policy_version='research-evidence-v1',policy_sha256=s.digest(policy),
        study_id=s.OUT.name,candidate_id=summary['selected'],purpose='retain_research',
        sample=dict(windows=[dict(role=role,start=start,end=end,prior_use='previously_inspected')
            for role,start,end in [('calibration',s.START,'2024-12-31'),('evaluation','2025-01-02',s.END)]],
            selection_basis='training_only',claim='retrospective_development',recipe_frozen_at=p['registered_at'],
            observations_captured_after_freeze=False,trial_count=20,
            prior_search_and_multiplicity='Five recipe families x four timing policies, plus four buyhold/cash references; six friction settings each. Sixteen expanded-policy/control contrasts have approximate family intervals. Earlier screens and repeated strategy searches mean total lifetime search count is unknown.',
            label_boundary_and_overlap='Causal model label cutoffs enforced by shared application code. Forward IC endpoints confined to each era;1/5/10/21/63 daily labels overlap. Paired21-session block intervals are approximate and may understate longer-label dependence.'),
        inputs=dict(publication_batch=p['price_pin']['batch'],price_basis='dividend_split_adjusted',activity_basis='audited_raw',
            historical_availability='reconstructed_or_unknown',historical_membership='retrospective_or_unknown',full_supported_pool=True,
            limitations_and_missing_policy='52 supported histories from54 candidates; BWX/XOP unresolved identity holds. Audited adjusted prices/raw activity with explicit missing exclusions. Original-vintage financial/USD series remain limited by historical capture availability; monthly carry preserves source dates.'),
        fixed_and_dynamic_evaluated=True,preregistered_net_rule=p['selection'],net_verdict='not_established',
        decay=[dict(signal='Expanded FR25 combined selection rank',status='unidentifiable',horizons=[1,5,10,21,63],
            half_life_sessions=None,method_uncertainty_and_caveats='Return-horizon rank-IC curve with1000 circular21-session block draws does not identify an exponential signal half-life. Overlapping labels, regime dependence and prior sample reuse remain;63-session dependence can exceed the block length.',
            cadence_and_delay_interpretation='Evaluate monthly and0.10/0.40/0.80 target-change policies on realized net portfolios, with5/10/20bp and0/1 extra delay. Missing half-life is not a profitability veto.')],
        coverage_gaps=['Fresh prospective performance has not been collected for this expanded recipe.',
            'Historical security-master membership and first publication availability remain uncertified.',
            'No measured spreads/impact or paper evidence for expanded allocation; bootstrap does not account for all prior searches.'],
        prospective_plan_or_gap='Not authorized or started. Any future trial must freeze the recipe before new audited/captured observations; this report remains retrospective development evidence.',
        operator_disposition='November2: operator authorized this next item after retaining prior Alpha54 research. Numerical item completed and paused for discussion; no claim that the operator has accepted the new conclusions or authorized tracking.',
        artifacts=[dict(path=(s.OUT/name).relative_to(s.REPO).as_posix(),sha256=s.digest(s.OUT/name),roles=value) for name,value in roles.items()])
    if all(summary['guard_counts'][w][b]==6 for w in ('calibration','later')
            for b in ('original-'+summary['selected'].split('-')[1],'m1-'+summary['selected'].split('-')[1],
                      'momentum-'+summary['selected'].split('-')[1],'unranked-'+summary['selected'].split('-')[1])):
        dossier['net_verdict']='guarded_advantage'
    s.write(s.OUT/'dossier.json',dossier)
    review=assess(dossier,s.REPO,policy)
    if review['integrity_and_claim_issues']:raise ValueError(review['integrity_and_claim_issues'])
    s.write(s.OUT/'assessment.json',review)
    tests=s.REPO/'var/maintenance/expanded-fr25-net-20261102/tests.xml'
    suites=ET.parse(tests).getroot();suite=next(iter(suites))
    s.write(s.OUT/'acceptance.json',dict(completed_at=datetime.now(timezone.utc).isoformat(),cases=summary['cases'],
        tests={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')},test_receipt_sha256=s.digest(tests),
        native=native,monthly_policy_checks=s.read(s.OUT/'monthly-target-parity.json'),
        independent_book_max_error_usd=summary['book_error_usd'],assessment_sha256=s.digest(s.OUT/'assessment.json'),
        frozen_protocol_sha256=s.digest(s.OUT/'protocol.json'),
        scripts={f'scripts/{name}.py':s.digest(s.REPO/'scripts'/(name+'.py')) for name in
            ('research_expanded_fr25_net','report_expanded_fr25_net','validate_expanded_fr25_net','close_expanded_fr25_net')},
        authority=dict(monitoring=False,promotion=False,allocation=False,execution=False)))
    s.write(s.WORK/'protocol.json',p);s.write(s.WORK/'summary.json',summary)
    folders=[f for f in s.WORK.iterdir() if f.is_dir()]
    s.write(s.OUT/'retention.json',dict(status='Completed numerical item, retained for current operator discussion; queue routine retirement after disposition.',
        deletion_performed=False,retained='Compact report, protocol/definitions, input receipts/hashes, results/diagnostics, weakest charts/trade tables, independent receipts, dossier and scripts.',
        disposable_generated_folders=[dict(path=f.relative_to(s.REPO).as_posix(),bytes=sum(x.stat().st_size for x in f.rglob('*') if x.is_file())) for f in folders],
        remaining_compact_working_inputs='inputs.npz, pool.json.gz and published input copies can also retire after discussion closure; canonical publications are protected.',
        action='Add the explicit closed-study classification and model-cache folder to guarded housekeeping after discussion closure; recheck current dependencies/path containment and emit actual retirement receipts. Do not permanently pin duplicated fits or native bundles. No full backup required.'))
    s.write(s.OUT/'artifact-manifest.json',{f.name:s.digest(f) for f in sorted(s.OUT.iterdir()) if f.is_file() and f.name!='artifact-manifest.json'})
    print('Review',review['status'],review['net_verdict'],'tests',suite.attrib['tests'],flush=True)


if __name__=='__main__':main()
