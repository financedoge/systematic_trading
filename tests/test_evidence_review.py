"""Governance invariants: evidence integrity, sample reuse and no authority."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from systematic_trading.research.evidence_review import Evidence, assess, sha256

REPO=Path(__file__).resolve().parents[1]
POLICY=REPO/'config/research-evidence-policy-v1.json'


@pytest.fixture
def dossier(tmp_path):
    policy=json.loads(POLICY.read_text())
    artifact=tmp_path/'evidence.json'
    artifact.write_text(json.dumps(dict(ic=-.1,annual_cost_bp=2000)))
    return dict(schema_version=1,policy_version=policy['version'],policy_sha256=sha256(POLICY),study_id='test',
        candidate_id='frozen-candidate',purpose='retain_research',
        sample=dict(windows=[dict(role='calibration',start='2021-01-04',end='2024-12-31',prior_use='previously_inspected'),
                            dict(role='evaluation',start='2025-01-02',end='2026-10-30',prior_use='previously_inspected')],
            selection_basis='training_only',claim='retrospective_development',recipe_frozen_at='2026-10-31T00:00:00+00:00',
            observations_captured_after_freeze=False,trial_count=24,prior_search_and_multiplicity='Repeated development; family-adjusted intervals.',
            label_boundary_and_overlap='Forward labels end within era; paired block uncertainty.'),
        inputs=dict(publication_batch='a'*64,price_basis='dividend_split_adjusted',activity_basis='audited_raw',
            historical_availability='reconstructed_or_unknown',historical_membership='retrospective_or_unknown',
            full_supported_pool=True,limitations_and_missing_policy='No filling; revised vintages and surviving cohort.'),
        fixed_and_dynamic_evaluated=True,preregistered_net_rule='Matched net outcomes with return and drawdown guards.',
        net_verdict='not_established',decay=[dict(signal='candidate',status='unidentifiable',horizons=[1,5,10,21],
            half_life_sessions=None,method_uncertainty_and_caveats='Non-exponential evidence; no positive lifetime established.',
            cadence_and_delay_interpretation='All timing/friction outcomes retained.')],coverage_gaps=[],
        prospective_plan_or_gap='Not started; later evidence is retrospective.',operator_disposition='Retain research only.',
        artifacts=[dict(path='evidence.json',sha256=sha256(artifact),roles=policy['required_research_roles'])])


def test_negative_ic_high_cost_and_unknown_half_life_do_not_veto_retention(dossier,tmp_path):
    result=assess(dossier,tmp_path,POLICY)
    assert result['status']=='research_evidence_reviewable'
    assert result['requested_stage']=='ready_for_human_review'
    assert not any(result['authority'].values())


def test_short_half_life_has_no_universal_minimum(dossier,tmp_path):
    dossier['decay'][0].update(status='estimated',half_life_sessions=.1)
    assert assess(dossier,tmp_path,POLICY)['status']=='research_evidence_reviewable'


@pytest.mark.parametrize('status,number',[('estimated',None),('unidentifiable',12),('right_censored',float('inf')),
                                          ('estimated',float('nan')),('estimated',True),('estimated',0)])
def test_unknown_is_not_infinite_and_estimates_must_be_finite(dossier,status,number):
    dossier['decay'][0].update(status=status,half_life_sessions=number)
    with pytest.raises(ValidationError):Evidence.model_validate(dossier)


@pytest.mark.parametrize('horizons',[[5,1],[1,1],[0,5],[True,5]])
def test_horizon_contract_rejects_invalid_grid(dossier,horizons):
    dossier['decay'][0]['horizons']=horizons
    with pytest.raises(ValidationError):Evidence.model_validate(dossier)


@pytest.mark.parametrize('change',['file','role','missing','escape','duplicate'])
def test_integrity_failures_close_review(dossier,tmp_path,change):
    ref=dossier['artifacts'][0]
    if change=='file':(tmp_path/'evidence.json').write_text('changed')
    if change=='role':ref['roles'].remove('net_results')
    if change=='missing':ref['path']='missing.json'
    if change=='escape':ref['path']='../evidence.json'
    if change=='duplicate':dossier['artifacts'].append(deepcopy(ref))
    result=assess(dossier,tmp_path,POLICY)
    assert result['status']=='incomplete_evidence' and result['integrity_and_claim_issues']
    assert not any(result['authority'].values())


def test_unknown_or_reused_holdout_cannot_be_called_untouched(dossier,tmp_path):
    dossier['sample']['claim']='untouched_holdout'
    for use in ('unknown','previously_inspected'):
        dossier['sample']['windows'][1]['prior_use']=use
        assert assess(dossier,tmp_path,POLICY)['status']=='incomplete_evidence'
    dossier['sample']['windows'][1]['prior_use']='uninspected'
    dossier['sample']['selection_basis']='evaluation_informed'
    assert assess(dossier,tmp_path,POLICY)['status']=='incomplete_evidence'
    dossier['sample']['claim']='retrospective_development'
    result=assess(dossier,tmp_path,POLICY)
    assert result['status']=='research_evidence_reviewable'
    assert any('selection/development' in w for w in result['warnings'])


def test_prospective_requires_freeze_first_capture_and_pit(dossier,tmp_path):
    sample=dossier['sample'];sample['claim']='prospective';sample['windows'][1]['prior_use']='uninspected'
    result=assess(dossier,tmp_path,POLICY)
    assert len(result['integrity_and_claim_issues'])==2
    sample['recipe_frozen_at']='2024-12-31T10:00:00+00:00';sample['observations_captured_after_freeze']=True
    dossier['inputs'].update(historical_availability='certified_point_in_time',historical_membership='certified_point_in_time')
    assert assess(dossier,tmp_path,POLICY)['status']=='research_evidence_reviewable'


def test_complete_promotion_checklist_still_never_grants_authority(dossier,tmp_path):
    p=json.loads(POLICY.read_text());dossier['purpose']='promotion_review'
    result=assess(dossier,tmp_path,POLICY)
    assert result['requested_stage']=='needs_evidence'
    assert any('net-performance' in g for g in result['evidence_gaps'])
    dossier['artifacts'][0]['roles']+=p['required_monitoring_roles']+p['required_promotion_roles']
    dossier['sample'].update(claim='prospective',recipe_frozen_at='2024-12-31T10:00:00+00:00',observations_captured_after_freeze=True)
    dossier['sample']['windows'][1]['prior_use']='uninspected'
    dossier['inputs'].update(historical_availability='certified_point_in_time',historical_membership='certified_point_in_time')
    dossier['net_verdict']='guarded_advantage'
    result=assess(dossier,tmp_path,POLICY)
    assert result['requested_stage']=='ready_for_human_review'
    assert not any(result['authority'].values())


def test_retention_can_record_missing_decay_but_new_recipe_needs_it(dossier,tmp_path):
    dossier['decay'][0]['status']='insufficient'
    assert assess(dossier,tmp_path,POLICY)['requested_stage']=='ready_for_human_review'
    dossier['purpose']='new_monitored_recipe'
    result=assess(dossier,tmp_path,POLICY)
    assert result['requested_stage']=='needs_evidence'
    assert 'Unresolved decay/stability coverage: candidate' in result['evidence_gaps']


def test_full_pool_fixed_dynamic_and_disjoint_dates_are_required(dossier,tmp_path):
    dossier['inputs']['full_supported_pool']=False;dossier['fixed_and_dynamic_evaluated']=False
    assert len(assess(dossier,tmp_path,POLICY)['integrity_and_claim_issues'])==2
    dossier['sample']['windows'][1]['start']='2024-12-31'
    with pytest.raises(ValidationError):Evidence.model_validate(dossier)


def test_changed_policy_and_forged_authority_are_rejected(dossier,tmp_path):
    dossier['policy_sha256']='0'*64
    with pytest.raises(ValueError,match='policy bytes'):assess(dossier,tmp_path,POLICY)
    dossier['policy_sha256']=sha256(POLICY);dossier['promotion']=True
    with pytest.raises(ValidationError):assess(dossier,tmp_path,POLICY)


def test_review_binds_all_dossier_declarations(dossier,tmp_path):
    before=assess(dossier,tmp_path,POLICY)
    dossier['sample']['prior_search_and_multiplicity']='Additional inspected variants discovered.'
    after=assess(dossier,tmp_path,POLICY)
    assert before['dossier_fingerprint']!=after['dossier_fingerprint']
