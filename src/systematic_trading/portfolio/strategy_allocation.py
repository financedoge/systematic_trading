"""Versioned strategy roles and capital allocations. No broker side effects."""
from dataclasses import replace
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from systematic_trading.portfolio.context import portfolio_context
from systematic_trading.research.strategy_catalog import current_sota_definition, registered_strategy_definition


class StrategyCapital(BaseModel):
    strategy_key: str
    weight: Decimal = Field(gt=0, le=1, allow_inf_nan=False)


class AllocationChange(BaseModel):
    expected_revision: int = Field(ge=0)
    event_id: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    operator: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)
    sota_key: str | None = None
    allocations: list[StrategyCapital] | None = None
    effective_close: str | None = None
    max_batch_notional_cnh: Decimal = Field(default=Decimal('1000000'), gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_change(self):
        if not self.operator.strip() or not self.reason.strip():
            raise ValueError('Operator and reason are required.')
        if self.sota_key is None and self.allocations is None:
            raise ValueError('Choose a SOTA designation or trading allocation.')
        if self.allocations is not None:
            if not self.allocations or sum(a.weight for a in self.allocations) > 1:
                raise ValueError('Choose at least one strategy; capital weights must sum to at most 100%.')
            if len({a.strategy_key for a in self.allocations}) != len(self.allocations):
                raise ValueError('A strategy can appear only once.')
            if not self.effective_close:
                raise ValueError('Choose the completed market session for the handover.')
        return self


def scope_for(store):
    context = portfolio_context(store)
    # The portfolio episode is stable across accounting checkpoints and later
    # account metadata enrichment. Account identity is separately pinned at review.
    return ':'.join((context.portfolio_id, context.environment, context.episode_id))


def control_state(store):
    # Lightweight test doubles predating this contract still represent the legacy allocation.
    reader = getattr(store, 'strategy_control_state', None)
    state = reader(scope_for(store)) if reader else None
    if state is not None:
        return state
    definition = current_sota_definition()
    return dict(revision=0, sota_key=definition.key, pending=None, active=dict(
        version='legacy', key=definition.key, activated_at=None, effective_close=None,
        allocations=[dict(strategy_key=definition.key, weight='1')],
        capital_rebalance='monthly', max_batch_notional_cnh=None,
        history_label='Legacy assignment; activation date not established'))


def control_events(store):
    reader = getattr(store, 'strategy_control_events', None)
    return reader(scope_for(store)) if reader else []


def trading_definition(store):
    active = control_state(store)['active']
    if active['version'] == 'legacy':
        return current_sota_definition()
    definitions = [registered_strategy_definition(row['strategy_key']) for row in active['allocations']]
    return replace(definitions[0], key=active['key'], sleeve_name=active['key'],
        name=' + '.join(f"{Decimal(row['weight'])*100:g}% {d.name}" for row, d in zip(active['allocations'], definitions)))


def sota_definition(store):
    return registered_strategy_definition(control_state(store)['sota_key'])


def allocation_binding_issues(store, proposal):
    active = control_state(store)['active']
    bound = proposal.input_provenance.get('allocation', {}).get('version', 'legacy')
    if bound != active['version']:
        return ['Proposal belongs to a previous trading allocation. Build and approve a new proposal.']
    return []


def combine_targets(capital, targets, *, sleeve):
    """Sum capital × within-strategy weights; preserve reserve and strategy cash."""
    from systematic_trading.domain.portfolio import AllocationTarget
    weights = {}
    if any(w < 0 for w in capital.values()) or sum(capital.values()) > Decimal('1.000000000001'):
        raise ValueError('Invalid strategy capital allocation.')
    for key, share in capital.items():
        rows = targets[key]
        if sum(t.target_weight for t in rows) > 1:
            raise ValueError('Strategy weights exceed its capital.')
        for target in rows:
            weights[target.symbol] = weights.get(target.symbol, Decimal(0)) + share * target.target_weight
    if any(w > Decimal('0.450000000001') for w in weights.values()):
        raise ValueError('Combined ETF weight exceeds the 45% portfolio limit.')
    return [AllocationTarget(symbol=s, target_weight=w, sleeve=sleeve,
        rationale='Capital-weighted strategy targets; opposing changes are netted before broker sizing.')
        for s, w in sorted(weights.items())]
