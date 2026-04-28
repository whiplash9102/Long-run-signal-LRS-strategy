"""Config loading and validation for the Gayed LRS project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigValidationError(ValueError):
    """Raised when the strategy config is missing required values."""


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict):
        raise ConfigValidationError(f"Config must be a mapping: {config_path}")

    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    errors: list[str] = []

    for section in (
        "project",
        "data",
        "strategy",
        "execution",
        "costs",
        "alerts",
        "backtest",
        "future_extensions",
        "reporting",
        "validation",
    ):
        if section not in config:
            errors.append(f"Missing section: {section}")

    if errors:
        raise ConfigValidationError(_format_errors(errors))

    _validate_project(config, errors)
    _validate_data(config, errors)
    _validate_strategy(config, errors)
    _validate_execution(config, errors)
    _validate_backtest(config, errors)

    if errors:
        raise ConfigValidationError(_format_errors(errors))


def _validate_project(config: dict[str, Any], errors: list[str]) -> None:
    project = config["project"]
    for field in ("name", "version", "base_currency"):
        if not project.get(field):
            errors.append(f"project.{field} is required")


def _validate_data(config: dict[str, Any], errors: list[str]) -> None:
    data = config["data"]
    for field in (
        "frequency",
        "market_timezone",
        "start_date",
        "end_date",
        "warmup_bars",
        "signal_price_field",
        "execution_price_field",
    ):
        if data.get(field) in (None, ""):
            errors.append(f"data.{field} is required")

    universe = data.get("test_universe")
    if not isinstance(universe, list) or not universe:
        errors.append("data.test_universe must be a non-empty list")
        return

    tickers: set[str] = set()
    for index, asset in enumerate(universe):
        if not isinstance(asset, dict):
            errors.append(f"data.test_universe[{index}] must be a mapping")
            continue
        for field in ("id", "ticker", "region", "exposure", "role"):
            if not asset.get(field):
                errors.append(f"data.test_universe[{index}].{field} is required")
        ticker = asset.get("ticker")
        if ticker in tickers:
            errors.append(f"Duplicate test universe ticker: {ticker}")
        if ticker:
            tickers.add(ticker)

    risk_off = data.get("risk_off")
    if not isinstance(risk_off, dict):
        errors.append("data.risk_off must be a mapping")
        return
    for field in ("primary_asset", "fallback_asset", "fallback_rule"):
        if not risk_off.get(field):
            errors.append(f"data.risk_off.{field} is required")

    leveraged_execution = data.get("leveraged_execution")
    if not isinstance(leveraged_execution, list) or not leveraged_execution:
        errors.append("data.leveraged_execution must be a non-empty list")
        return

    signal_tickers = {asset["ticker"] for asset in universe if isinstance(asset, dict)}
    for index, mapping in enumerate(leveraged_execution):
        if not isinstance(mapping, dict):
            errors.append(f"data.leveraged_execution[{index}] must be a mapping")
            continue
        signal_ticker = mapping.get("signal_ticker")
        if signal_ticker not in signal_tickers:
            errors.append(
                f"data.leveraged_execution[{index}].signal_ticker must be in test_universe"
            )
        execution_assets = mapping.get("execution_assets")
        if not isinstance(execution_assets, list) or not execution_assets:
            errors.append(
                f"data.leveraged_execution[{index}].execution_assets must be a non-empty list"
            )
            continue
        for asset_index, execution_asset in enumerate(execution_assets):
            for field in ("id", "leverage", "mode"):
                if execution_asset.get(field) in (None, ""):
                    errors.append(
                        "data.leveraged_execution"
                        f"[{index}].execution_assets[{asset_index}].{field} is required"
                    )
            mode = execution_asset.get("mode")
            ticker = execution_asset.get("ticker")
            if mode in {"observed_etf", "observed_leveraged_etf"} and not ticker:
                errors.append(
                    "observed execution assets require a ticker: "
                    f"data.leveraged_execution[{index}].execution_assets[{asset_index}]"
                )
            if float(execution_asset.get("leverage", 0)) <= 0:
                errors.append(
                    f"execution asset leverage must be positive: {execution_asset.get('id')}"
                )


def _validate_strategy(config: dict[str, Any], errors: list[str]) -> None:
    strategy = config["strategy"]
    if strategy.get("direction") != "long_only":
        errors.append("strategy.direction must be long_only")
    if strategy.get("allow_short") is not False:
        errors.append("strategy.allow_short must be false")
    if float(strategy.get("phase_1_leverage_multiplier", -1)) != 1.0:
        errors.append("strategy.phase_1_leverage_multiplier must be 1.0 in phase 1")

    baseline = strategy.get("baseline_filter")
    if not isinstance(baseline, dict):
        errors.append("strategy.baseline_filter must be a mapping")
    elif baseline.get("type") != "SMA" or int(baseline.get("length", 0)) != 200:
        errors.append("strategy.baseline_filter must be SMA 200")

    filters = strategy.get("candidate_filters")
    if not isinstance(filters, list) or not filters:
        errors.append("strategy.candidate_filters must be a non-empty list")
    else:
        seen_ids: set[str] = set()
        for index, filter_spec in enumerate(filters):
            if not isinstance(filter_spec, dict):
                errors.append(f"strategy.candidate_filters[{index}] must be a mapping")
                continue
            for field in ("id", "type", "length"):
                if filter_spec.get(field) in (None, ""):
                    errors.append(f"strategy.candidate_filters[{index}].{field} is required")
            if filter_spec.get("type") not in {"SMA", "EMA"}:
                errors.append(f"Invalid filter type: {filter_spec.get('type')}")
            filter_id = filter_spec.get("id")
            if filter_id in seen_ids:
                errors.append(f"Duplicate candidate filter id: {filter_id}")
            if filter_id:
                seen_ids.add(filter_id)

    false_breakout = strategy.get("false_breakout")
    if not isinstance(false_breakout, dict):
        errors.append("strategy.false_breakout must be a mapping")
    else:
        if false_breakout.get("trading_filter_enabled") is not False:
            errors.append("strategy.false_breakout.trading_filter_enabled must be false in phase 1")
        if int(false_breakout.get("whipsaw_window_sessions", 0)) <= 0:
            errors.append("strategy.false_breakout.whipsaw_window_sessions must be positive")


def _validate_execution(config: dict[str, Any], errors: list[str]) -> None:
    execution = config["execution"]
    if execution.get("signal_timing") != "confirmed_daily_close":
        errors.append("execution.signal_timing must be confirmed_daily_close")
    if execution.get("execution_timing") != "next_session_open":
        errors.append("execution.execution_timing must be next_session_open")
    if execution.get("lookahead_bias_guard") is not True:
        errors.append("execution.lookahead_bias_guard must be true")


def _validate_backtest(config: dict[str, Any], errors: list[str]) -> None:
    walk_forward = config["backtest"].get("walk_forward", {})
    weights = walk_forward.get("score_weights")
    if not isinstance(weights, dict) or not weights:
        errors.append("backtest.walk_forward.score_weights must be a non-empty mapping")
        return

    total_weight = sum(float(value) for value in weights.values())
    if abs(total_weight - 1.0) > 1e-9:
        errors.append(f"walk-forward score weights must sum to 1.0, got {total_weight}")


def _format_errors(errors: list[str]) -> str:
    joined = "\n- ".join(errors)
    return f"Invalid config:\n- {joined}"
