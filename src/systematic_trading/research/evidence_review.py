"""P4.20 read-only evidence contract. No numerical proxy gate or trading authority.

This validates declarations and referenced bytes, not the truth of a statistical
claim. The review is a governance prerequisite, not a monitoring/broker API.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import file_digest, sha256 as hash_bytes
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

VERSION = 'research-evidence-v1'
SHA = r'^[a-f0-9]{64}$'


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Artifact(Record):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA)
    roles: list[str] = Field(min_length=1)


class Window(Record):
    role: Literal['calibration', 'evaluation']
    start: date
    end: date
    prior_use: Literal['uninspected', 'previously_inspected', 'unknown']

    @model_validator(mode='after')
    def dates(self):
        if self.start > self.end:
            raise ValueError('Window end precedes start')
        return self


class SampleUse(Record):
    windows: list[Window] = Field(min_length=2)
    selection_basis: Literal['training_only', 'evaluation_informed']
    claim: Literal['retrospective_development', 'untouched_holdout', 'prospective']
    recipe_frozen_at: datetime
    observations_captured_after_freeze: StrictBool
    trial_count: int = Field(ge=1, strict=True)
    prior_search_and_multiplicity: str = Field(min_length=1)
    label_boundary_and_overlap: str = Field(min_length=1)

    @model_validator(mode='after')
    def boundaries(self):
        if self.recipe_frozen_at.tzinfo is None:
            raise ValueError('Recipe freeze requires an explicit timezone')
        train=[w for w in self.windows if w.role=='calibration']
        evaluation=[w for w in self.windows if w.role=='evaluation']
        if len(train)!=1 or len(evaluation)!=1:
            raise ValueError('Declare one calibration and one evaluation window per review')
        if train[0].end >= evaluation[0].start:
            raise ValueError('Calibration and evaluation must be chronological and disjoint')
        return self


class Inputs(Record):
    publication_batch: str = Field(pattern=SHA)
    price_basis: Literal['dividend_split_adjusted']
    activity_basis: Literal['audited_raw', 'not_used']
    historical_availability: Literal['certified_point_in_time', 'reconstructed_or_unknown']
    historical_membership: Literal['certified_point_in_time', 'retrospective_or_unknown']
    full_supported_pool: StrictBool
    limitations_and_missing_policy: str = Field(min_length=1)


class Decay(Record):
    signal: str = Field(min_length=1)
    status: Literal['estimated', 'right_censored', 'unidentifiable', 'insufficient', 'not_applicable']
    horizons: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1)
    half_life_sessions: float | None = Field(default=None, gt=0, strict=True)
    method_uncertainty_and_caveats: str = Field(min_length=1)
    cadence_and_delay_interpretation: str = Field(min_length=1)

    @model_validator(mode='after')
    def estimate(self):
        if self.horizons!=sorted(set(self.horizons)) or any(h<=0 for h in self.horizons):
            raise ValueError('Decay horizons must be positive, unique and increasing')
        if (self.status=='estimated') != (self.half_life_sessions is not None):
            raise ValueError('A finite half-life belongs only to an estimated status')
        return self


class Evidence(Record):
    schema_version: Literal[1]
    policy_version: Literal['research-evidence-v1']
    policy_sha256: str = Field(pattern=SHA)
    study_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    purpose: Literal['retain_research', 'new_monitored_recipe', 'promotion_review']
    sample: SampleUse
    inputs: Inputs
    fixed_and_dynamic_evaluated: StrictBool
    preregistered_net_rule: str = Field(min_length=1)
    net_verdict: Literal['guarded_advantage', 'not_established', 'adverse', 'inconclusive']
    decay: list[Decay] = Field(min_length=1)
    coverage_gaps: list[str]
    prospective_plan_or_gap: str = Field(min_length=1)
    operator_disposition: str = Field(min_length=1)
    artifacts: list[Artifact] = Field(min_length=1)


def sha256(path):
    with Path(path).open('rb') as stream:
        return file_digest(stream,'sha256').hexdigest()


def assess(payload, root, policy_path):
    """Deterministic integrity/completeness review; never authorizes any action."""
    evidence=Evidence.model_validate(payload)
    root=Path(root).resolve();policy_path=Path(policy_path)
    policy=json.loads(policy_path.read_text(encoding='utf8'))
    if policy.get('version')!=VERSION or sha256(policy_path)!=evidence.policy_sha256:
        raise ValueError('Evidence must bind the exact versioned policy bytes')
    # Prevent a policy edit from reintroducing either retired numerical proxy.
    if (policy['universal_minimum_half_life'] is not None or policy['annual_cost_ceiling_bp'] is not None
            or policy['ic_profitability_veto'] is not False):
        raise ValueError('Policy version forbids universal half-life, cost and IC vetoes')
    issues=[];roles=set();verified=[];seen=set()
    for ref in evidence.artifacts:
        relative=Path(ref.path)
        if relative.is_absolute() or '..' in relative.parts:
            issues.append('Artifact path must stay relative to the workspace: '+ref.path);continue
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            issues.append('Artifact missing or outside workspace: '+ref.path);continue
        if path in seen:
            issues.append('Duplicate artifact reference: '+ref.path);continue
        seen.add(path)
        if sha256(path)!=ref.sha256:
            issues.append('Artifact hash mismatch: '+ref.path);continue
        roles.update(ref.roles);verified.append(ref.path)
    missing=sorted(set(policy['required_research_roles'])-roles)
    issues.extend('Missing research evidence role: '+r for r in missing)
    evaluation=next(w for w in evidence.sample.windows if w.role=='evaluation')
    clean_claim=evidence.sample.claim!='retrospective_development'
    if clean_claim and (evidence.sample.selection_basis!='training_only' or evaluation.prior_use!='uninspected'):
        issues.append('Inspected or evaluation-selected data cannot support an untouched/prospective claim')
    if evidence.sample.claim=='prospective':
        if (evidence.sample.recipe_frozen_at.date()>=evaluation.start
                or not evidence.sample.observations_captured_after_freeze):
            issues.append('Prospective evidence requires a prior freeze and later captured observations')
        if (evidence.inputs.historical_availability!='certified_point_in_time'
                or evidence.inputs.historical_membership!='certified_point_in_time'):
            issues.append('Prospective claim requires point-in-time inputs and universe evidence')
    if not evidence.inputs.full_supported_pool:
        issues.append('Full supported candidate-pool evaluation is missing')
    if not evidence.fixed_and_dynamic_evaluated:
        issues.append('Fixed and dynamic rebalance comparison is missing')
    gaps=list(evidence.coverage_gaps)
    for d in evidence.decay:
        if d.status=='insufficient':gaps.append('Unresolved decay/stability coverage: '+d.signal)
    if evidence.purpose!='retain_research':
        gaps.extend('Missing application evidence role: '+r for r in sorted(set(policy['required_monitoring_roles'])-roles))
    if evidence.purpose=='promotion_review':
        gaps.extend('Missing promotion evidence role: '+r for r in sorted(set(policy['required_promotion_roles'])-roles))
        if evidence.sample.claim!='prospective':gaps.append('Fresh prospective validation has not been established')
        if evidence.net_verdict!='guarded_advantage':gaps.append('Predeclared net-performance claim has not been established')
        if evidence.inputs.historical_availability!='certified_point_in_time':
            gaps.append('Historical publication availability is not certified')
        if evidence.inputs.historical_membership!='certified_point_in_time':
            gaps.append('Historical membership availability is not certified')
    warnings=[]
    if evidence.sample.selection_basis=='evaluation_informed':
        warnings.append('Evaluation has become selection/development evidence for this decision')
    if evidence.sample.claim=='retrospective_development':
        warnings.append('Chronological separation is not a claim of untouched or prospective validation')
    warnings.append('Checklist verifies supplied file integrity and declarations; reviewer must assess scientific adequacy and provenance')
    return dict(schema_version=1,policy_version=VERSION,policy_sha256=evidence.policy_sha256,
        dossier_fingerprint=hash_bytes(json.dumps(evidence.model_dump(mode='json'),sort_keys=True,
            separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        study_id=evidence.study_id,candidate_id=evidence.candidate_id,purpose=evidence.purpose,
        status='incomplete_evidence' if issues else 'research_evidence_reviewable',
        requested_stage='needs_evidence' if issues or (evidence.purpose!='retain_research' and gaps) else 'ready_for_human_review',
        net_verdict=evidence.net_verdict,integrity_and_claim_issues=issues,evidence_gaps=sorted(set(gaps)),
        warnings=warnings,verified_artifacts=verified,
        authority=dict(monitoring=False,promotion=False,allocation=False,execution=False),
        validator_sha256=sha256(Path(__file__)))
