"""Application service: provider chains, cache policy, and API payload assembly."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from .cache import JsonCache
from .calculations import (
    add_years,
    holding_period_returns,
    month_end_points,
    percentile_rank,
    resample_points,
    return_summary,
    scheduled_dca_backtest,
    valid_points,
)
from .catalog import IndexDefinition, get_index
from .sources import (
    SourceError,
    fetch_csi_history,
    fetch_csi_indicator,
    fetch_legu_metric,
    fetch_multpl_metric,
    fetch_tencent_adjusted_history,
    fetch_yahoo_history,
)


SOURCE_INFO = {
    "csi_official": {"name": "中证指数官网", "tier": "official", "url": "https://www.csindex.com.cn/"},
    "legulegu": {"name": "乐咕乐股", "tier": "aggregated", "url": "https://legulegu.com/stockdata"},
    "multpl": {"name": "Multpl", "tier": "aggregated", "url": "https://www.multpl.com/"},
    "yahoo": {"name": "Yahoo Finance", "tier": "aggregated", "url": "https://finance.yahoo.com/markets/"},
    "tencent": {"name": "腾讯证券", "tier": "aggregated", "url": "https://gu.qq.com/"},
}


class ResearchService:
    def __init__(self, cache_path: Path):
        self.cache = JsonCache(cache_path)

    @staticmethod
    def _age_hours(timestamp: str) -> float:
        fetched = datetime.fromisoformat(timestamp)
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - fetched).total_seconds() / 3600

    def _load(
        self,
        key: str,
        source: str,
        fetcher: Callable[[], list[dict]],
        ttl_hours: int,
        force: bool = False,
    ) -> tuple[list[dict], dict]:
        cached = self.cache.get(key)
        if cached and not force and self._age_hours(cached["fetched_at"]) <= ttl_hours:
            return cached["payload"], {
                "source": source, "fetched_at": cached["fetched_at"], "stale": False,
                "from_cache": True, "fallback_from": None, "partial": False,
            }
        try:
            points = fetcher()
            dates = [str(point["date"])[:10] for point in points if point.get("date")]
            if cached and dates:
                truncated = (
                    cached["point_count"] >= 36
                    and len(dates) < cached["point_count"] * 0.8
                    and cached["first_date"]
                    and dates[0] > cached["first_date"]
                )
                if truncated:
                    return cached["payload"], {
                        "source": cached["source"], "fetched_at": cached["fetched_at"],
                        "stale": self._age_hours(cached["fetched_at"]) > ttl_hours,
                        "from_cache": True, "fallback_from": source, "partial": True,
                        "error": "新数据覆盖范围疑似截断，保留了更完整的本地缓存",
                    }
            metadata = self.cache.put(key, points, source, dates)
            return points, {
                "source": source, "fetched_at": metadata["fetched_at"], "stale": False,
                "from_cache": False, "fallback_from": None, "partial": False,
            }
        except Exception as exc:
            if cached:
                return cached["payload"], {
                    "source": cached["source"], "fetched_at": cached["fetched_at"],
                    "stale": True, "from_cache": True, "fallback_from": source,
                    "partial": False, "error": str(exc),
                }
            raise SourceError(str(exc)) from exc

    @staticmethod
    def _cutoff(years: int) -> date:
        today = date.today()
        try:
            return today.replace(year=today.year - years)
        except ValueError:
            return today.replace(year=today.year - years, day=28)

    def _metric(
        self,
        metric_id: str,
        label: str,
        unit: str,
        series: list[dict],
        lookback_years: int,
        source: str,
        metadata: dict,
        history_frequency: str = "monthly",
        current_override: dict | None = None,
        note: str | None = None,
    ) -> dict:
        cutoff = self._cutoff(lookback_years).isoformat()
        today = date.today().isoformat()
        filtered = [point for point in valid_points(series) if cutoff <= point["date"] <= today]
        percentile_history = month_end_points(filtered)
        history = resample_points(filtered, history_frequency)
        current_point = current_override or (filtered[-1] if filtered else None)
        if not current_point:
            return self._unavailable_metric(metric_id, label, unit, "数据源没有返回有效观测")
        current = float(current_point["value"])
        percentile, sample_count = percentile_rank(percentile_history, current)
        status = "ready" if percentile is not None else "insufficient_history"
        source_info = {**SOURCE_INFO[source], "id": source}
        return {
            "id": metric_id, "label": label, "unit": unit, "value": round(current, 3),
            "date": current_point["date"], "percentile": percentile,
            "percentile_direction": "higher_is_cheaper" if metric_id == "dividend_yield" else "higher_is_more_expensive",
            "status": status, "sample_count": sample_count, "lookback_years": lookback_years,
            "percentile_frequency": "month_end", "history_frequency": history_frequency,
            "history": history, "source": source_info,
            "fetched_at": metadata.get("fetched_at"), "stale": metadata.get("stale", False),
            "partial": metadata.get("partial", False), "fallback_from": metadata.get("fallback_from"),
            "estimated": bool(current_point.get("estimated")), "note": note,
        }

    @staticmethod
    def _unavailable_metric(metric_id: str, label: str, unit: str, reason: str) -> dict:
        return {
            "id": metric_id, "label": label, "unit": unit, "value": None, "date": None,
            "percentile": None, "status": "unavailable", "sample_count": 0,
            "history": [], "source": None, "reason": reason, "stale": False,
            "partial": False, "estimated": False,
        }

    def _a_share_research(
        self, index: IndexDefinition, years: int, history_frequency: str, force: bool
    ) -> tuple[list[dict], list[dict]]:
        issues = []
        official_history, official_meta = [], {}
        indicator, indicator_meta = [], {}
        legu_pe, legu_pe_meta = [], {}
        legu_pb, legu_pb_meta = [], {}
        try:
            raw_history, official_meta = self._load(
                f"csi:history:{index.code}", "csi_official",
                lambda: fetch_csi_history(index.code), 18, force,
            )
            official_history = [
                {"date": point["date"], "value": point.get("pe")}
                for point in raw_history if point.get("pe")
            ]
        except SourceError as exc:
            issues.append({"source": "csi_official", "message": str(exc)})
        try:
            indicator, indicator_meta = self._load(
                f"csi:indicator:{index.code}", "csi_official",
                lambda: fetch_csi_indicator(index.code), 18, force,
            )
        except SourceError as exc:
            issues.append({"source": "csi_official", "message": str(exc)})
        try:
            legu_pe, legu_pe_meta = self._load(
                f"legu:pe:{index.valuation_code}", "legulegu",
                lambda: fetch_legu_metric(index.valuation_code or "", "pe"), 24, force,
            )
        except SourceError as exc:
            issues.append({"source": "legulegu", "message": str(exc)})
        try:
            legu_pb, legu_pb_meta = self._load(
                f"legu:pb:{index.valuation_code}", "legulegu",
                lambda: fetch_legu_metric(index.valuation_code or "", "pb"), 24, force,
            )
        except SourceError as exc:
            issues.append({"source": "legulegu", "message": str(exc)})

        official_current = indicator[-1] if indicator else None
        pe_series, pe_source, pe_meta = (official_history, "csi_official", official_meta)
        if not pe_series:
            pe_series, pe_source, pe_meta = legu_pe, "legulegu", legu_pe_meta
        pe_override = None
        if official_current and official_current.get("pe"):
            pe_override = {"date": official_current["date"], "value": official_current["pe"]}
        cross_check = None
        if pe_override and legu_pe:
            public_value = float(legu_pe[-1]["value"])
            difference = abs(pe_override["value"] - public_value) / pe_override["value"] * 100
            cross_check = {
                "official_value": round(pe_override["value"], 3),
                "aggregated_value": round(public_value, 3),
                "difference_pct": round(difference, 1),
                "status": "source_mismatch" if difference > 25 else "within_tolerance",
                "note": "两源计算用股本口径可能不同，仅作异常核验。",
            }
            if difference > 25:
                issues.append({"source": "cross_check", "message": "PE 官方值与聚合值偏差超过 25%"})

        pe_metric = self._metric(
            "pe", "PE TTM", "×", pe_series, years, pe_source, pe_meta,
            history_frequency=history_frequency, current_override=pe_override,
        )
        if cross_check and cross_check["status"] == "source_mismatch":
            pe_metric["status"] = "source_mismatch"
            pe_metric["cross_check"] = cross_check
            pe_metric["note"] = "官方值与聚合值偏差超过阈值；保留官方值并拒绝聚合值覆盖。"
        metrics = [
            pe_metric,
            self._metric(
                "pb", "PB", "×", legu_pb, years, "legulegu", legu_pb_meta,
                history_frequency=history_frequency,
            )
            if legu_pb else self._unavailable_metric("pb", "PB", "×", "聚合源当前不可用"),
        ]
        if official_current and official_current.get("dividend_yield"):
            dividend_series = [
                {"date": point["date"], "value": point.get("dividend_yield")}
                for point in indicator if point.get("dividend_yield")
            ]
            metrics.append(self._metric(
                "dividend_yield", "股息率", "%", dividend_series, years,
                "csi_official", indicator_meta, history_frequency=history_frequency,
                current_override={"date": official_current["date"], "value": official_current["dividend_yield"]},
                note="中证公开表仅提供近期观测，当前值可用，但不足以计算 10 年分位。",
            ))
        else:
            metrics.append(self._unavailable_metric("dividend_yield", "股息率", "%", "中证官方估值表当前不可用"))
        if cross_check:
            issues.append({
                "source": "cross_check",
                "message": "PE 官方值与公共聚合值已完成交叉核验。",
                **cross_check,
            })
        return metrics, issues

    def _sp500_research(self, years: int, history_frequency: str, force: bool) -> tuple[list[dict], list[dict]]:
        metrics, issues = [], []
        definitions = (("pe", "PE TTM", "×"), ("pb", "PB", "×"), ("dividend_yield", "股息率", "%"))
        for metric_id, label, unit in definitions:
            try:
                points, meta = self._load(
                    f"multpl:{metric_id}", "multpl", lambda metric_id=metric_id: fetch_multpl_metric(metric_id),
                    24, force,
                )
                metrics.append(self._metric(
                    metric_id, label, unit, points, years, "multpl", meta,
                    history_frequency=history_frequency,
                ))
            except SourceError as exc:
                metrics.append(self._unavailable_metric(metric_id, label, unit, str(exc)))
                issues.append({"source": "multpl", "message": str(exc)})
        return metrics, issues

    def get_research(
        self, index_id: str, lookback_years: int = 10,
        history_frequency: str = "monthly", force: bool = False,
    ) -> dict:
        if lookback_years not in {3, 5, 10, 15, 20}:
            raise ValueError("lookback_years must be 3, 5, 10, 15, or 20")
        if history_frequency not in {"daily", "monthly", "quarterly", "yearly"}:
            raise ValueError("history_frequency must be daily, monthly, quarterly, or yearly")
        index = get_index(index_id)
        if index.valuation_provider == "csi_legu":
            metrics, issues = self._a_share_research(index, lookback_years, history_frequency, force)
        elif index.valuation_provider == "multpl":
            metrics, issues = self._sp500_research(lookback_years, history_frequency, force)
        else:
            reason = f"{index.name}：{index.valuation_coverage}"
            metrics = [
                self._unavailable_metric("pe", "PE TTM", "×", reason),
                self._unavailable_metric("pb", "PB", "×", reason),
                self._unavailable_metric("dividend_yield", "股息率", "%", reason),
            ]
            issues = [{"source": "valuation", "message": reason}]
        ready_count = sum(metric["status"] == "ready" for metric in metrics)
        dates = [metric["date"] for metric in metrics if metric.get("date")]
        return {
            "index": index.public_dict(), "status": "ready" if ready_count == 3 else "partial",
            "as_of": max(dates) if dates else None, "lookback_years": lookback_years,
            "history_frequency": history_frequency,
            "metrics": metrics, "issues": issues,
        }

    def _return_series(self, index: IndexDefinition, force: bool) -> tuple[list[dict], dict, str, str, str]:
        if index.price_provider == "csi":
            source, source_fetcher = "csi_official", fetch_csi_history
        elif index.price_provider == "yahoo":
            source, source_fetcher = "yahoo", fetch_yahoo_history
        elif index.price_provider == "tencent":
            source, source_fetcher = "tencent", fetch_tencent_adjusted_history
        else:
            raise SourceError(f"不支持的行情适配器：{index.price_provider}")
        effective_return_type = index.return_type
        effective_return_label = index.return_label
        try:
            points, meta = self._load(
                f"returns:daily:{index.id}:{index.price_code}", source,
                lambda: source_fetcher(index.price_code), 18, force,
            )
        except SourceError as primary_error:
            if not index.fallback_price_code:
                raise
            points, meta = self._load(
                f"returns:daily:{index.id}:{index.fallback_price_code}", source,
                lambda: source_fetcher(index.fallback_price_code or ""), 18, force,
            )
            meta["fallback_from"] = f"{source}:{index.price_code}"
            meta["primary_error"] = str(primary_error)
            effective_return_type = "price_return"
            effective_return_label = "价格指数（不含分红）"
        return points, meta, source, effective_return_type, effective_return_label

    @staticmethod
    def _return_warning(return_type: str) -> str | None:
        if return_type == "price_return":
            return "该指数当前使用价格指数，不含分红再投资；与全收益结果不可直接比较。"
        if return_type == "adjusted_proxy":
            return (
                "当前使用 515450 ETF 前复权日线代理，不是标普官方指数全收益序列；"
                "结果包含基金费率、跟踪误差、市场价格偏离，且仅覆盖 ETF 上市后的历史。"
            )
        return None

    def get_returns(
        self,
        index_id: str,
        frequency: str = "quarterly",
        holding_years: int = 5,
        measure: str = "annualized",
        force: bool = False,
    ) -> dict:
        if frequency not in {"monthly", "quarterly", "semiannual"}:
            raise ValueError("frequency must be monthly, quarterly, or semiannual")
        if holding_years not in {1, 3, 5, 10}:
            raise ValueError("holding_years must be 1, 3, 5, or 10")
        if measure not in {"annualized", "cumulative"}:
            raise ValueError("measure must be annualized or cumulative")
        index = get_index(index_id)
        try:
            points, meta, source, effective_return_type, effective_return_label = self._return_series(index, force)
            samples = holding_period_returns(points, frequency, holding_years, measure)
            status = "ready" if samples else "insufficient_history"
            error = None
        except SourceError as exc:
            points, samples, meta, source = [], [], {}, "csi_official" if index.price_provider == "csi" else "yahoo"
            effective_return_type, effective_return_label = index.return_type, index.return_label
            status, error = "source_error", str(exc)
        warning = self._return_warning(effective_return_type)
        return {
            "index": index.public_dict(), "status": status, "frequency": frequency,
            "holding_years": holding_years, "measure": measure, "unit": "%",
            "samples": samples, "summary": return_summary(samples),
            "data_as_of": points[-1]["date"] if meta and points else None,
            "latest_complete_start": samples[-1]["start_date"] if samples else None,
            "latest_complete_end": samples[-1]["end_date"] if samples else None,
            "source": {**SOURCE_INFO[source], "id": source} if meta else None,
            "fetched_at": meta.get("fetched_at"), "stale": meta.get("stale", False),
            "partial": meta.get("partial", False), "fallback_from": meta.get("fallback_from"),
            "return_type": effective_return_type, "return_label": effective_return_label,
            "warning": warning, "error": error,
        }

    def get_dca(
        self, index_id: str, years: int = 10, contribution_amount: float = 1000,
        start_date: str | None = None, end_date: str | None = None,
        cadence: str = "monthly", schedule_value: int = 1, force: bool = False,
    ) -> dict:
        if start_date is None and years not in {3, 5, 10, 15, 20}:
            raise ValueError("years must be 3, 5, 10, 15, or 20")
        if (start_date is None) != (end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        if cadence not in {"monthly", "weekly"}:
            raise ValueError("cadence must be monthly or weekly")
        schedule_limit = 31 if cadence == "monthly" else 7
        if schedule_value < 1 or schedule_value > schedule_limit:
            raise ValueError(f"schedule_value must be between 1 and {schedule_limit} for {cadence}")
        if not math.isfinite(contribution_amount) or contribution_amount <= 0 or contribution_amount > 10_000_000:
            raise ValueError("contribution_amount must be greater than 0 and no more than 10000000")
        if start_date is not None and end_date is not None:
            try:
                parsed_start, parsed_end = date.fromisoformat(start_date), date.fromisoformat(end_date)
            except ValueError as exc:
                raise ValueError("start_date and end_date must use YYYY-MM-DD") from exc
            if parsed_start > parsed_end:
                raise ValueError("start_date must not be later than end_date")
        index = get_index(index_id)
        source = "csi_official" if index.price_provider == "csi" else "yahoo"
        meta: dict = {}
        return_type, return_label = index.return_type, index.return_label
        try:
            points, meta, source, return_type, return_label = self._return_series(index, force)
            if start_date is None or end_date is None:
                market_end = date.fromisoformat(points[-1]["date"][:10])
                start_date = add_years(market_end, -years).isoformat()
                end_date = market_end.isoformat()
            result = scheduled_dca_backtest(
                points, start_date, end_date, cadence, schedule_value, contribution_amount,
            )
            status, error = "ready", None
        except SourceError as exc:
            result, status, error = None, "source_error", str(exc)
        except ValueError as exc:
            result = None
            status = "insufficient_data_granularity" if "daily observations" in str(exc) else "insufficient_history"
            error = str(exc)
        warning = self._return_warning(return_type)
        return {
            "index": index.public_dict(), "status": status, "years": years,
            "start_date": start_date, "end_date": end_date,
            "cadence": cadence, "schedule_value": schedule_value,
            "contribution_amount": contribution_amount,
            "currency": index.currency, "result": result,
            "source": {**SOURCE_INFO[source], "id": source} if meta else None,
            "fetched_at": meta.get("fetched_at"), "stale": meta.get("stale", False),
            "partial": meta.get("partial", False), "fallback_from": meta.get("fallback_from"),
            "return_type": return_type, "return_label": return_label,
            "warning": warning, "error": error,
            "assumptions": [
                "计划日休市时顺延到下一有效交易日，超出结束日则不执行",
                "允许购买小数单位，期末资产按结束日当日或之前最近行情估值",
                "XIRR 使用每笔投入日期和期末资产价值计算",
                "未计手续费、税费、跟踪误差、汇率、通胀和整股限制",
            ],
        }

    def validate_metric(
        self, index_id: str, metric_id: str, reference_value: float,
        reference_date: str, reference_source: str = "用户参考", tolerance_pct: float = 2.0,
    ) -> dict:
        if metric_id not in {"pe", "pb", "dividend_yield"}:
            raise ValueError("metric_id must be pe, pb, or dividend_yield")
        if not math.isfinite(reference_value) or reference_value <= 0:
            raise ValueError("reference_value must be positive")
        if not math.isfinite(tolerance_pct) or tolerance_pct <= 0 or tolerance_pct > 100:
            raise ValueError("tolerance_pct must be greater than 0 and no more than 100")
        try:
            requested_date = date.fromisoformat(reference_date)
        except ValueError as exc:
            raise ValueError("reference_date must use YYYY-MM-DD") from exc
        research = self.get_research(index_id, 20, history_frequency="daily")
        metric = next(item for item in research["metrics"] if item["id"] == metric_id)
        if not metric.get("history"):
            return {
                "status": "unavailable", "metric_id": metric_id,
                "reference": {"value": reference_value, "date": reference_date, "source": reference_source},
                "reason": metric.get("reason") or "没有可用于核验的历史观测",
            }
        nearest = min(
            metric["history"],
            key=lambda point: abs((date.fromisoformat(point["date"][:10]) - requested_date).days),
        )
        day_distance = abs((date.fromisoformat(nearest["date"][:10]) - requested_date).days)
        difference_pct = abs(float(nearest["value"]) - reference_value) / reference_value * 100
        if day_distance > 7:
            status = "date_mismatch"
            conclusion = "没有找到日期足够接近的观测，暂时无法比较。"
        elif difference_pct > tolerance_pct:
            status = "source_mismatch"
            conclusion = "数值偏差超过容差，需要进一步核对计算口径。"
        else:
            status = "consistent"
            conclusion = "数值在容差内一致；参考源计算口径未完全确认。"
        return {
            "status": status, "metric_id": metric_id, "metric_label": metric["label"],
            "reference": {"value": reference_value, "date": reference_date, "source": reference_source},
            "observed": {
                "value": nearest["value"], "date": nearest["date"],
                "source": metric["source"], "estimated": bool(nearest.get("estimated")),
            },
            "date_distance_days": day_distance, "difference_pct": round(difference_pct, 2),
            "tolerance_pct": tolerance_pct, "definition_status": "unknown",
            "conclusion": conclusion,
            "methodology_note": "核验只证明数值接近；TTM/静态、成分股亏损处理和聚合方式仍需来源方口径说明。",
        }
