"""Strategy declaration objects for the Gayed LRS project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ETFAsset:
    id: str
    ticker: str
    region: str
    exposure: str
    role: str


@dataclass(frozen=True)
class FilterSpec:
    id: str
    type: str
    length: int


@dataclass(frozen=True)
class RiskOffSpec:
    primary_asset: str
    fallback_asset: str
    fallback_rule: str
    cash_daily_return: float


@dataclass(frozen=True)
class ExecutionAssetSpec:
    id: str
    ticker: str | None
    leverage: float
    mode: str


@dataclass(frozen=True)
class LeveragedExecutionSpec:
    signal_ticker: str
    execution_assets: tuple[ExecutionAssetSpec, ...]


@dataclass(frozen=True)
class FalseBreakoutSpec:
    trading_filter_enabled: bool
    diagnostics_enabled: bool
    definition: str
    whipsaw_window_sessions: int
    decision_rule: str


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    direction: str
    portfolio_mode: str
    phase_1_leverage_multiplier: float
    baseline_filter: FilterSpec
    candidate_filters: tuple[FilterSpec, ...]
    test_universe: tuple[ETFAsset, ...]
    leveraged_execution: tuple[LeveragedExecutionSpec, ...]
    risk_off: RiskOffSpec
    false_breakout: FalseBreakoutSpec
    signal_timing: str
    execution_timing: str
    position_size_pct: float
    initial_capital: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "StrategyDefinition":
        strategy = config["strategy"]
        data = config["data"]
        execution = config["execution"]

        return cls(
            name=strategy["name"],
            direction=strategy["direction"],
            portfolio_mode=strategy["portfolio_mode"],
            phase_1_leverage_multiplier=float(strategy["phase_1_leverage_multiplier"]),
            baseline_filter=_filter_from_mapping(strategy["baseline_filter"]),
            candidate_filters=tuple(
                _filter_from_mapping(item) for item in strategy["candidate_filters"]
            ),
            test_universe=tuple(_asset_from_mapping(item) for item in data["test_universe"]),
            leveraged_execution=tuple(
                _leveraged_execution_from_mapping(item)
                for item in data["leveraged_execution"]
            ),
            risk_off=RiskOffSpec(
                primary_asset=data["risk_off"]["primary_asset"],
                fallback_asset=data["risk_off"]["fallback_asset"],
                fallback_rule=data["risk_off"]["fallback_rule"],
                cash_daily_return=float(data["risk_off"]["cash_daily_return"]),
            ),
            false_breakout=FalseBreakoutSpec(
                trading_filter_enabled=bool(
                    strategy["false_breakout"]["trading_filter_enabled"]
                ),
                diagnostics_enabled=bool(strategy["false_breakout"]["diagnostics_enabled"]),
                definition=strategy["false_breakout"]["definition"],
                whipsaw_window_sessions=int(
                    strategy["false_breakout"]["whipsaw_window_sessions"]
                ),
                decision_rule=strategy["false_breakout"]["decision_rule"],
            ),
            signal_timing=execution["signal_timing"],
            execution_timing=execution["execution_timing"],
            position_size_pct=float(execution["position_size_pct"]),
            initial_capital=float(execution["initial_capital"]),
        )

    def to_markdown(self) -> str:
        filters = "\n".join(
            f"- `{item.id}`: {item.type} {item.length}" for item in self.candidate_filters
        )
        assets = "\n".join(
            f"| `{item.ticker}` | {item.region} | {item.exposure} | {item.role} |"
            for item in self.test_universe
        )
        execution_rows = "\n".join(
            _leveraged_execution_to_markdown(item) for item in self.leveraged_execution
        )

        return f"""# Strategy Declaration

## Core Rule

- Strategy: `{self.name}`
- Direction: `{self.direction}`
- Portfolio mode: `{self.portfolio_mode}`
- Signal layer: normal ETF close versus moving-average filter
- Risk-on state: long the configured execution asset
- Risk-off state: `{self.risk_off.primary_asset}`
- Entry: close crosses from at/below filter to above filter
- Exit: close crosses from above filter to at/below filter
- Signal timing: `{self.signal_timing}`
- Execution timing: `{self.execution_timing}`
- Position size: `{self.position_size_pct:.0%}`
- Initial capital: `${self.initial_capital:,.0f}`

## ETF Universe

| Ticker | Region | Exposure | Role |
| --- | --- | --- | --- |
{assets}

## Leveraged Execution Map

| Signal ETF | Execution ID | Execution Ticker | Leverage | Mode |
| --- | --- | --- | --- | --- |
{execution_rows}

## Filters

Baseline:

- `{self.baseline_filter.id}`: {self.baseline_filter.type} {self.baseline_filter.length}

Candidates:

{filters}

## False Breakout Handling

- Trading filter enabled: `{str(self.false_breakout.trading_filter_enabled).lower()}`
- Diagnostics enabled: `{str(self.false_breakout.diagnostics_enabled).lower()}`
- Whipsaw definition: `{self.false_breakout.definition}`
- Whipsaw window: `{self.false_breakout.whipsaw_window_sessions}` sessions
- Decision rule: `{self.false_breakout.decision_rule}`

Professional stance:

- Phase 1 measures false breakouts but does not filter them.
- A false-breakout filter can be tested later only if whipsaw evidence is material.
"""


def _asset_from_mapping(item: dict[str, Any]) -> ETFAsset:
    return ETFAsset(
        id=item["id"],
        ticker=item["ticker"],
        region=item["region"],
        exposure=item["exposure"],
        role=item["role"],
    )


def _filter_from_mapping(item: dict[str, Any]) -> FilterSpec:
    return FilterSpec(id=item["id"], type=item["type"], length=int(item["length"]))


def _leveraged_execution_from_mapping(item: dict[str, Any]) -> LeveragedExecutionSpec:
    return LeveragedExecutionSpec(
        signal_ticker=item["signal_ticker"],
        execution_assets=tuple(
            ExecutionAssetSpec(
                id=asset["id"],
                ticker=asset.get("ticker"),
                leverage=float(asset["leverage"]),
                mode=asset["mode"],
            )
            for asset in item["execution_assets"]
        ),
    )


def _leveraged_execution_to_markdown(item: LeveragedExecutionSpec) -> str:
    rows = []
    for asset in item.execution_assets:
        ticker = asset.ticker or "synthetic"
        rows.append(
            f"| `{item.signal_ticker}` | `{asset.id}` | `{ticker}` | "
            f"{asset.leverage:.1f}x | `{asset.mode}` |"
        )
    return "\n".join(rows)
