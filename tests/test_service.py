import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app.service import ResearchService
from app.sources import SourceError


class ResearchServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
