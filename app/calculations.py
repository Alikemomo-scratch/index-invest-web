"""Pure valuation and holding-period calculations."""

from __future__ import annotations

import calendar
import math
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from statistics import median, pstdev
from typing import Iterable


def valid_points(points: Iterable[dict], positive_only: bool = True) -> list[dict]:
    cleaned = []
    for point in points:
        value = point.get("value")
        if (
            isinstance(value, (int, float))
            and math.isfinite(value)
            and (value > 0 or not positive_only)
        ):
            cleaned.append({"date": str(point["date"]), "value": float(value), **{
                key: val for key, val in point.items() if key not in {"date", "value"}
            }})
    return sorted(cleaned, key=lambda item: item["date"])


def percentile_rank(
    points: Iterable[dict], current: float, minimum: int = 36,
    positive_only: bool = True,
) -> tuple[float | None, int]:
    values = [point["value"] for point in valid_points(points, positive_only)]
    invalid_current = not math.isfinite(current) or (positive_only and current <= 0)
    if len(values) < minimum or invalid_current:
        return None, len(values)
    return round(sum(value <= current for value in values) / len(values) * 100, 1), len(values)


def month_end_points(points: Iterable[dict]) -> list[dict]:
    by_month: dict[str, dict] = {}
    for point in sorted(points, key=lambda item: item["date"]):
        if point.get("value") is None:
            continue
        by_month[str(point["date"])[:7]] = point
    return list(by_month.values())


def resample_points(
    points: Iterable[dict], frequency: str, positive_only: bool = True,
) -> list[dict]:
    """Return the final real observation in each requested display period."""
    if frequency not in {"daily", "monthly", "quarterly", "yearly"}:
        raise ValueError("history_frequency must be daily, monthly, quarterly, or yearly")
    cleaned = valid_points(points, positive_only)
    if frequency == "daily":
        return list({point["date"]: point for point in cleaned}.values())
    grouped: dict[tuple[int, ...], dict] = {}
    for point in cleaned:
        parsed = date.fromisoformat(point["date"][:10])
        if frequency == "monthly":
            key = (parsed.year, parsed.month)
        elif frequency == "quarterly":
            key = (parsed.year, (parsed.month - 1) // 3 + 1)
        else:
            key = (parsed.year,)
        grouped[key] = point
    return list(grouped.values())


def aligned_risk_premium(
    equity_points: Iterable[dict], bond_points: Iterable[dict],
    bond_key: str, equity_kind: str,
) -> list[dict]:
    """Align month-end components and return percentage-point risk premiums."""
    if equity_kind not in {"pe", "dividend_yield"}:
        raise ValueError("equity_kind must be pe or dividend_yield")
    equity_by_month = {
        point["date"][:7]: point for point in month_end_points(valid_points(equity_points))
    }
    normalized_bonds = [
        {"date": str(point["date"]), "value": point.get(bond_key)}
        for point in bond_points
    ]
    bond_by_month = {
        point["date"][:7]: point for point in month_end_points(valid_points(normalized_bonds))
    }
    result = []
    for month in sorted(equity_by_month.keys() & bond_by_month.keys()):
        equity = equity_by_month[month]
        bond = bond_by_month[month]
        equity_value = float(equity["value"])
        base_yield = 100 / equity_value if equity_kind == "pe" else equity_value
        bond_yield = float(bond["value"])
        result.append({
            "date": equity["date"],
            "value": base_yield - bond_yield,
            "equity_date": equity["date"],
            "bond_date": bond["date"],
            "equity_value": equity_value,
            "base_yield": base_yield,
            "government_bond_yield": bond_yield,
        })
    return result


def add_years(value: date, years: int) -> date:
    day = min(value.day, calendar.monthrange(value.year + years, value.month)[1])
    return value.replace(year=value.year + years, day=day)


def sample_period_ends(points: Iterable[dict], frequency: str) -> list[dict]:
    if frequency not in {"monthly", "quarterly", "semiannual"}:
        raise ValueError("frequency must be monthly, quarterly, or semiannual")
    grouped: dict[tuple[int, int], dict] = {}
    for point in sorted(points, key=lambda item: item["date"]):
        parsed = date.fromisoformat(str(point["date"])[:10])
        bucket = parsed.month
        if frequency == "quarterly":
            bucket = (parsed.month - 1) // 3 + 1
        elif frequency == "semiannual":
            bucket = (parsed.month - 1) // 6 + 1
        grouped[(parsed.year, bucket)] = point
    return list(grouped.values())


def holding_period_returns(
    points: Iterable[dict], frequency: str, holding_years: int, measure: str
) -> list[dict]:
    if frequency not in {"monthly", "quarterly", "semiannual"}:
        raise ValueError("frequency must be monthly, quarterly, or semiannual")
    if holding_years not in {1, 3, 5, 10}:
        raise ValueError("holding_years must be 1, 3, 5, or 10")
    if measure not in {"annualized", "cumulative"}:
        raise ValueError("measure must be annualized or cumulative")
    prices = [
        {"date": date.fromisoformat(str(point["date"])[:10]), "value": float(point["value"])}
        for point in valid_points(points)
    ]
    if not prices:
        return []
    anchors = sample_period_ends(
        [{"date": item["date"].isoformat(), "value": item["value"]} for item in prices],
        frequency,
    )
    result = []
    price_index = 0
    for anchor in anchors:
        start_date = date.fromisoformat(anchor["date"])
        target = add_years(start_date, holding_years)
        while price_index < len(prices) and prices[price_index]["date"] <= target:
            price_index += 1
        if price_index == 0:
            continue
        end = prices[price_index - 1]
        if end["date"] < target and (target - end["date"]).days > 40:
            continue
        if end["date"] <= start_date or end["value"] <= 0:
            continue
        cumulative = end["value"] / float(anchor["value"]) - 1
        elapsed_days = (end["date"] - start_date).days
        annualized = (1 + cumulative) ** (365.2425 / elapsed_days) - 1
        result.append({
            "start_date": start_date.isoformat(),
            "end_date": end["date"].isoformat(),
            "value": round((annualized if measure == "annualized" else cumulative) * 100, 3),
        })
    return result


def return_summary(samples: list[dict]) -> dict:
    values = [sample["value"] for sample in samples]
    if not values:
        return {
            "average": None, "median": None, "standard_deviation": None,
            "win_rate": None,
            "worst": None, "best": None, "count": 0,
        }
    return {
        "average": round(sum(values) / len(values), 2),
        "median": round(median(values), 2),
        "standard_deviation": round(pstdev(values), 2),
        "win_rate": round(sum(value > 0 for value in values) / len(values) * 100, 1),
        "worst": round(min(values), 2),
        "best": round(max(values), 2),
        "count": len(values),
    }


def xirr(cashflows: Iterable[dict]) -> float | None:
    """Return the annualized IRR for dated cash flows as a decimal rate."""
    flows = sorted(
        ({"date": date.fromisoformat(str(flow["date"])[:10]), "value": float(flow["value"])} for flow in cashflows),
        key=lambda flow: flow["date"],
    )
    if not flows or not any(flow["value"] < 0 for flow in flows) or not any(flow["value"] > 0 for flow in flows):
        return None
    origin = flows[0]["date"]

    def npv(rate: float) -> float:
        return sum(
            flow["value"] / ((1 + rate) ** ((flow["date"] - origin).days / 365.2425))
            for flow in flows
        )

    low, high = -0.9999, 1.0
    low_value, high_value = npv(low), npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high = high * 2 + 1
        high_value = npv(high)
    if low_value * high_value > 0:
        return None
    for _ in range(160):
        middle = (low + high) / 2
        middle_value = npv(middle)
        if abs(middle_value) < 1e-8:
            return middle
        if low_value * middle_value <= 0:
            high, high_value = middle, middle_value
        else:
            low, low_value = middle, middle_value
    return (low + high) / 2


def _scheduled_dates(start: date, end: date, cadence: str, schedule_value: int) -> list[date]:
    if cadence == "weekly":
        current = start + timedelta(days=(schedule_value - start.isoweekday()) % 7)
        result = []
        while current <= end:
            result.append(current)
            current += timedelta(days=7)
        return result
    current = start.replace(day=1)
    result = []
    while current <= end:
        planned = current.replace(day=min(schedule_value, calendar.monthrange(current.year, current.month)[1]))
        if start <= planned <= end:
            result.append(planned)
        current = date(current.year + 1, 1, 1) if current.month == 12 else current.replace(month=current.month + 1)
    return result


def scheduled_dca_backtest(
    points: Iterable[dict], start_date: str, end_date: str, cadence: str,
    schedule_value: int, contribution_amount: float, require_daily: bool = True,
    max_adjustment_days: int = 14,
) -> dict:
    if cadence not in {"monthly", "weekly"}:
        raise ValueError("cadence must be monthly or weekly")
    limit = 31 if cadence == "monthly" else 7
    if schedule_value < 1 or schedule_value > limit:
        raise ValueError(f"schedule_value must be between 1 and {limit} for {cadence}")
    if not math.isfinite(contribution_amount) or contribution_amount <= 0 or contribution_amount > 10_000_000:
        raise ValueError("contribution_amount must be greater than 0 and no more than 10000000")
    try:
        requested_start, requested_end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("start_date and end_date must use YYYY-MM-DD") from exc
    if requested_start > requested_end:
        raise ValueError("start_date must not be later than end_date")
    history = valid_points(points)
    if len(history) < 2:
        raise ValueError("insufficient observations for DCA backtest")
    price_dates = [date.fromisoformat(point["date"][:10]) for point in history]
    if require_daily and len(price_dates) >= 3:
        typical_gap = median((right - left).days for left, right in zip(price_dates, price_dates[1:]))
        if typical_gap > 3:
            raise ValueError("daily observations are required for day-specific DCA scheduling")
    effective_start = max(requested_start, price_dates[0])
    effective_end = min(requested_end, price_dates[-1])
    if effective_start > effective_end:
        raise ValueError("requested date range does not overlap the available market history")
    terminal_index = bisect_right(price_dates, effective_end) - 1
    if terminal_index < 0:
        raise ValueError("no market observation is available on or before end_date")
    terminal_point = history[terminal_index]
    planned_dates = _scheduled_dates(effective_start, effective_end, cadence, schedule_value)
    executions = []
    used_execution_dates = set()
    for planned in planned_dates:
        execution_index = bisect_left(price_dates, planned)
        if execution_index >= len(history) or price_dates[execution_index] > effective_end:
            continue
        execution = history[execution_index]
        execution_date = price_dates[execution_index]
        if (execution_date - planned).days > max_adjustment_days:
            continue
        if execution_date in used_execution_dates:
            continue
        used_execution_dates.add(execution_date)
        executions.append((planned, execution_date, execution))
    if len(executions) < 2:
        raise ValueError("insufficient scheduled contributions in the requested date range")
    units = 0.0
    invested = 0.0
    curve = []
    cashflows = []
    contributions = []
    for planned, execution_date, point in executions:
        units += contribution_amount / point["value"]
        invested += contribution_amount
        cashflows.append({"date": execution_date.isoformat(), "value": -contribution_amount})
        contribution = {
            "scheduled_date": planned.isoformat(), "execution_date": execution_date.isoformat(),
            "price": round(point["value"], 6), "adjusted": planned != execution_date,
        }
        contributions.append(contribution)
        curve.append({
            "date": execution_date.isoformat(), "scheduled_date": planned.isoformat(),
            "kind": "contribution",
            "invested": round(invested, 2),
            "portfolio_value": round(units * point["value"], 2),
        })
    terminal_date = date.fromisoformat(terminal_point["date"][:10])
    ending_value = units * terminal_point["value"]
    cashflows.append({"date": terminal_date.isoformat(), "value": ending_value})
    if terminal_date != executions[-1][1]:
        curve.append({
            "date": terminal_date.isoformat(), "scheduled_date": None, "kind": "valuation",
            "invested": round(invested, 2), "portfolio_value": round(ending_value, 2),
        })
    annualized = xirr(cashflows)
    profit = ending_value - invested
    return {
        "requested_start_date": requested_start.isoformat(),
        "requested_end_date": requested_end.isoformat(),
        "start_date": effective_start.isoformat(), "end_date": terminal_date.isoformat(),
        "range_clipped": effective_start != requested_start or (requested_end - terminal_date).days > 7,
        "cadence": cadence, "schedule_value": schedule_value,
        "contribution_amount": round(contribution_amount, 2),
        "monthly_amount": round(contribution_amount, 2) if cadence == "monthly" else None,
        "contribution_count": len(executions),
        "adjusted_count": sum(item["adjusted"] for item in contributions),
        "skipped_count": len(planned_dates) - len(executions),
        "total_invested": round(invested, 2),
        "ending_value": round(ending_value, 2),
        "profit": round(profit, 2),
        "cumulative_return": round(profit / invested * 100, 2),
        "annualized_return": round(annualized * 100, 2) if annualized is not None else None,
        "curve": curve, "contributions": contributions,
    }


def monthly_dca_backtest(points: Iterable[dict], years: int, monthly_amount: float) -> dict:
    """Compatibility wrapper for the original fixed-window monthly DCA API."""
    if years not in {3, 5, 10, 15, 20}:
        raise ValueError("years must be 3, 5, 10, 15, or 20")
    history = valid_points(points)
    if len(history) < 2:
        raise ValueError("insufficient observations for DCA backtest")
    latest = date.fromisoformat(history[-1]["date"][:10])
    return scheduled_dca_backtest(
        history, add_years(latest, -years).isoformat(), latest.isoformat(),
        "monthly", 1, monthly_amount, require_daily=False, max_adjustment_days=40,
    )
