from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from systematic_trading.research.flow_concentration import FlowConcentrationSpec
from systematic_trading.research.constituent_signals import ConstituentOverlaySpec


class BacktestRunSpec(BaseModel):
    schema_version: Literal[1] = 1
    strategy: Literal['sota', 'benchmark', 'sota_flow', 'sota_constituents', 'registered'] = 'sota'
    strategy_definition: dict | None = None
    flow_overlay: FlowConcentrationSpec | None = None
    constituent_overlay: ConstituentOverlaySpec | None = None
    base_tree_model_schedule: bool = False
    fixed_model_from: str | None = None
    mode: Literal['targets', 'shared'] = 'shared'
    start_date: str
    end_date: str
    warmup_start: str
    initial_cash_cnh: str = '1000000'
    transaction_cost_bps: str = '5'
    slippage_bps: str = '0'
    execution_delay_sessions: int = Field(default=0, ge=0, le=5)
    random_seed: int = 0
    lookback_bars: int = Field(default=63, ge=21, le=252)
    accounting_currency: Literal['CNH'] = 'CNH'
    scenario: Literal['adjusted_cnh_units_next_open'] = 'adjusted_cnh_units_next_open'
    normalization: Literal['provider adjusted OHLC; no separate dividend or split credits'] = 'provider adjusted OHLC; no separate dividend or split credits'
    settlement: Literal['instant CNH settlement of FX-converted adjusted units; whole units; no leverage'] = 'instant CNH settlement of FX-converted adjusted units; whole units; no leverage'
    certification: Literal['uncertified_legacy', 'synthetic_fixture'] = 'uncertified_legacy'
    promotion_eligible: Literal[False] = False
    target_tolerance: str = '0.00000001'
    money_tolerance_cnh: str = '0.01'
    strategy_hash: str
    source_hash: str
    repository_commit: str
    calendar_version: str = 'us-equity-v2-closures-2012-2018-2025'
    fx_policy: Literal['exact_observation', 'legacy_carry_max7'] = 'exact_observation'
    split_date: str = '2023-01-01'
    limitations: list[str] = Field(default_factory=lambda: [
        'Adjusted historical vintages and historical universe membership are not certified point-in-time.',
        'Frozen pre-2023 tree: in-sample fitted performance is not out-of-sample evidence.',
        'Daily open fills do not model intraday TWAP, liquidity, partial fills or settlement delays.',
        'CNH-adjusted units differ from retaining USD sale proceeds in the legacy Python scenario.',
    ])

    @model_validator(mode='after')
    def validate_economics(self):
        if (self.strategy == 'registered') != (self.strategy_definition is not None):
            raise ValueError('Registered runs require a complete frozen strategy definition')
        if self.fixed_model_from is not None:
            date.fromisoformat(self.fixed_model_from)
            if not self.base_tree_model_schedule or self.fixed_model_from < '2023-01-01':
                raise ValueError('Frozen deployed model must follow a causal schedule and cannot precede 2023')
        if self.base_tree_model_schedule and self.strategy == 'benchmark':
            raise ValueError('A benchmark cannot use a tree schedule')
        if (self.strategy == 'sota_constituents') != (self.constituent_overlay is not None):
            raise ValueError('sota_constituents requires a constituent overlay; other strategies must not have one')
        if (self.strategy == 'sota_flow') != (self.flow_overlay is not None):
            raise ValueError('sota_flow requires a flow overlay; other strategies must not have one')
        if not date.fromisoformat(self.warmup_start) < date.fromisoformat(self.start_date) <= date.fromisoformat(self.end_date):
            raise ValueError('Require warmup < start <= end')
        for name in ('initial_cash_cnh', 'target_tolerance', 'money_tolerance_cnh'):
            value = Decimal(getattr(self, name))
            if not value.is_finite() or value <= 0:
                raise ValueError(f'{name} must be positive and finite')
        for name in ('transaction_cost_bps', 'slippage_bps'):
            value = Decimal(getattr(self, name))
            if not value.is_finite() or not 0 <= value < 10000:
                raise ValueError(f'{name} outside supported bounds')
        return self


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2, default=str) + '\n', encoding='utf-8')


def verify_bundle(root: Path) -> dict:
    root = root.resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported bundle schema')
    expected = manifest['files']
    for name, digest in expected.items():
        unresolved = root / name
        path = unresolved.resolve()
        if not path.is_relative_to(root) or unresolved.is_symlink() or not path.is_file():
            raise ValueError(f'Unsafe/missing bundle file: {name}')
        if any(parent.is_symlink() for parent in unresolved.parents if parent != root and parent.is_relative_to(root)):
            raise ValueError(f'Unsafe bundle symlink: {name}')
        if sha256(path) != digest:
            raise ValueError(f'Bundle hash mismatch: {name}')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root / 'manifest.json'}
    if actual != set(expected):
        raise ValueError('Bundle file inventory changed')
    spec = BacktestRunSpec.model_validate_json((root / 'spec.json').read_text(encoding='utf-8'))
    return {'manifest': manifest, 'spec': spec}
