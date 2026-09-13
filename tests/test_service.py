import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app.service import ResearchService
from app.sources import SourceError


class ResearchServiceTests(unittest.TestCase):
    @staticmethod
    def _monthly_points(start_year: int, year_count: int, key: str = "value") -> list[dict]:
        return [
            {"date": f"{year}-{month:02d}-28", key: 2 + (year - start_year) / 10 + month / 100}
            for year in range(start_year, start_year + year_count)
            for month in range(1, 13)
            if f"{year}-{month:02d}-28" <= date.today().isoformat()
        ]

    def test_coverage_audit_reports_internal_gaps_and_requested_range_clipping(self):
        cleaned = [
            {"date": "2022-03-31", "value": 3.0},
            {"date": "2022-05-31", "value": 3.2},
        ]
        audit = ResearchService._coverage_audit(cleaned, cleaned, "2021-01-01", "2022-05-31")
        self.assertEqual(audit["missing_months"], ["2022-04"])
        self.assertEqual(audit["valid_month_count"], 2)
        self.assertTrue(audit["requested_range_clipped"])

    def test_a_share_dividend_history_keeps_official_dp_values_separate(self):
        current_year = date.today().year
        price_history = [
            {**point, "pe": point["value"]}
            for point in self._monthly_points(current_year - 10, 11)
        ]
        metric_history = self._monthly_points(current_year - 10, 11)
        bond_history = [
            {"date": point["date"], "china_10y": 2.0, "us_10y": 4.0}
            for point in metric_history
        ]
        indicator = [{
            "date": date.today().isoformat(),
            "pe": 9.0,
            "dividend_yield": 3.1,
            "dividend_yield_total_share": 3.0,
            "dividend_yield_calculation_share": 3.1,
        }]
        with tempfile.TemporaryDirectory() as directory, patch(
            "app.service.fetch_csi_history", return_value=price_history,
        ), patch(
            "app.service.fetch_csi_indicator", return_value=indicator,
        ), patch(
            "app.service.fetch_legu_metric", return_value=metric_history,
        ), patch(
            "app.service.fetch_funddb_dividend_yield", return_value=metric_history,
        ), patch(
            "app.service.fetch_government_bond_yields", return_value=bond_history,
        ):
            service = ResearchService(Path(directory) / "cache.sqlite3")
            payload = service.get_research("csi300_div_low_vol", 10, force=True)
        metric = next(item for item in payload["metrics"] if item["id"] == "dividend_yield")
        self.assertEqual(metric["source"]["id"], "funddb")
        self.assertEqual(metric["status"], "ready")
        self.assertEqual([item["id"] for item in metric["official_values"]], ["dp1", "dp2"])
        self.assertEqual(metric["methodology_status"], "unconfirmed")
        self.assertEqual(metric["coverage"]["missing_month_count"], 0)

    def test_index_without_public_dividend_history_returns_official_current_only(self):
        current_year = date.today().year
        price_history = [
            {**point, "pe": point["value"]}
            for point in self._monthly_points(current_year - 3, 4)
        ]
        indicator = [{
            "date": date.today().isoformat(),
            "pe": 10.0,
            "dividend_yield": 4.2,
            "dividend_yield_total_share": 4.1,
            "dividend_yield_calculation_share": 4.2,
        }]
        bond_history = [
            {"date": point["date"], "china_10y": 2.0, "us_10y": 4.0}
            for point in price_history
        ]
        with tempfile.TemporaryDirectory() as directory, patch(
            "app.service.fetch_csi_history", return_value=price_history,
        ), patch(
            "app.service.fetch_csi_indicator", return_value=indicator,
        ), patch(
            "app.service.fetch_legu_metric", return_value=price_history,
        ), patch(
            "app.service.fetch_funddb_dividend_yield",
        ) as dividend_fetcher:
            with patch(
                "app.service.fetch_government_bond_yields", return_value=bond_history,
            ):
                service = ResearchService(Path(directory) / "cache.sqlite3")
                payload = service.get_research("csi_dfh_div_low_vol", 10, force=True)
        dividend_fetcher.assert_not_called()
        metric = next(item for item in payload["metrics"] if item["id"] == "dividend_yield")
        self.assertEqual(metric["source"]["id"], "csi_official")
        self.assertEqual(metric["status"], "insufficient_history")
        self.assertEqual(metric["methodology_status"], "official_dp2")
        self.assertEqual(len(metric["official_values"]), 2)

    def test_risk_premium_metric_uses_pe_inverse_and_keeps_negative_spreads(self):
        points = []
        bonds = []
        for index in range(36):
            year, month = 2023 + index // 12, index % 12 + 1
            point_date = f"{year}-{month:02d}-28"
            points.append({"date": point_date, "value": 20.0})
            bonds.append({"date": point_date, "china_10y": 6.0, "us_10y": 4.0})
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(Path(directory) / "cache.sqlite3")
            metric = service._risk_premium_metric(
                "earnings_yield_premium", "盈利收益率溢价", "pe",
                points, "csi_official", {}, bonds, "china_10y", "中国", {}, 5, "monthly",
                {"date": points[-1]["date"], "value": 25.0},
            )
        self.assertEqual(metric["value"], -2.0)
        self.assertEqual(metric["sample_count"], 36)
        self.assertEqual(metric["status"], "ready")
        self.assertEqual(metric["formula"], "100 / PE TTM - 10年期国债收益率")
        self.assertTrue(metric["allow_negative"])
        self.assertEqual(metric["percentile_direction"], "higher_is_cheaper")

    def test_metric_does_not_treat_future_estimate_as_current(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(Path(directory) / "cache.sqlite3")
            current_year = date.today().year
            points = [
                {"date": f"{year}-01-31", "value": 10 + year - (current_year - 3)}
                for year in range(current_year - 3, current_year + 1)
            ] * 9
            points.append({"date": f"{current_year + 1}-01-31", "value": 99, "estimated": True})
            metric = service._metric(
                "pe", "PE TTM", "×", points, 5, "multpl",
                {"fetched_at": "2026-01-01T00:00:00+00:00"},
            )
            self.assertNotEqual(metric["value"], 99)
            self.assertLessEqual(metric["date"], date.today().isoformat())

    def test_history_frequency_does_not_change_month_end_percentile(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(Path(directory) / "cache.sqlite3")
            points = []
            for month in range(1, 13):
                for day in (1, 28):
                    points.append({"date": f"2025-{month:02d}-{day:02d}", "value": month})
            daily = service._metric(
                "pe", "PE TTM", "×", points * 3, 3, "multpl", {}, history_frequency="daily"
            )
            monthly = service._metric(
                "pe", "PE TTM", "×", points * 3, 3, "multpl", {}, history_frequency="monthly"
            )
            self.assertEqual(daily["percentile"], monthly["percentile"])
            self.assertGreater(len(daily["history"]), len(monthly["history"]))

    def test_total_return_source_falls_back_to_disclosed_price_index(self):
        start = date(2020, 1, 1)
        price_points = [
            {"date": (start + timedelta(days=month * 30)).isoformat(), "value": 100 + month}
            for month in range(40)
        ]
        with tempfile.TemporaryDirectory() as directory, patch(
            "app.service.fetch_csi_history",
            side_effect=[SourceError("primary unavailable"), price_points],
        ):
            service = ResearchService(Path(directory) / "cache.sqlite3")
            payload = service.get_returns("csi300", "quarterly", 1, "annualized", force=True)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["return_type"], "price_return")
            self.assertIn("csi_official:H00300", payload["fallback_from"])
            self.assertIn("不含分红", payload["warning"])
            self.assertEqual(payload["data_as_of"], price_points[-1]["date"])
            self.assertEqual(payload["latest_complete_end"], payload["samples"][-1]["end_date"])

    def test_sp500_reference_validation_marks_close_values_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(Path(directory) / "cache.sqlite3")
            payload = {
                "metrics": [{
                    "id": "pe", "label": "PE TTM",
                    "history": [{"date": "2026-09-04", "value": 26.36, "estimated": True}],
                    "source": {"id": "multpl", "name": "Multpl"},
                }]
            }
            with patch.object(service, "get_research", return_value=payload):
                result = service.validate_metric("sp500", "pe", 26.12, "2026-09-04", "富途 App", 2)
            self.assertEqual(result["status"], "consistent")
            self.assertEqual(result["difference_pct"], 0.92)
            self.assertTrue(result["observed"]["estimated"])
            self.assertEqual(result["definition_status"], "unknown")

    def test_sp_china_proxy_discloses_adjusted_etf_source(self):
        start = date(2020, 2, 26)
        price_points = [
            {"date": (start + timedelta(days=day)).isoformat(), "value": 1 + day / 10_000}
            for day in range(365 * 6)
        ]
        with tempfile.TemporaryDirectory() as directory, patch(
            "app.service.fetch_tencent_adjusted_history", return_value=price_points,
        ):
            service = ResearchService(Path(directory) / "cache.sqlite3")
            payload = service.get_returns(
                "sp_china_a_div_low_vol_50", "monthly", 1, "annualized", force=True,
            )
            research = service.get_research("sp_china_a_div_low_vol_50")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["return_type"], "adjusted_proxy")
        self.assertEqual(payload["source"]["id"], "tencent")
        self.assertIn("ETF 前复权日线代理", payload["warning"])
        self.assertIn("公开历史估值不可用", research["metrics"][0]["reason"])
        self.assertEqual(len(research["metrics"]), 5)


if __name__ == "__main__":
    unittest.main()
