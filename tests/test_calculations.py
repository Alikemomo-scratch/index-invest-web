import unittest
from datetime import date, timedelta

from app.calculations import (
    holding_period_returns,
    monthly_dca_backtest,
    percentile_rank,
    resample_points,
    return_summary,
    sample_period_ends,
    scheduled_dca_backtest,
    xirr,
)


class PercentileTests(unittest.TestCase):
    def test_empirical_percentile_includes_current_value(self):
        points = [{"date": f"2020-{month:02d}-28", "value": month} for month in range(1, 13)] * 3
        percentile, count = percentile_rank(points, 6, minimum=36)
        self.assertEqual(count, 36)
        self.assertEqual(percentile, 50.0)

    def test_rejects_non_positive_and_small_samples(self):
        percentile, count = percentile_rank(
            [{"date": "2024-01-01", "value": -1}, {"date": "2024-02-01", "value": 2}], 2
        )
        self.assertIsNone(percentile)
        self.assertEqual(count, 1)


class ReturnTests(unittest.TestCase):
    @staticmethod
    def daily_growth_points(days=365 * 3 + 3):
        start = date(2020, 1, 1)
        return [
            {"date": (start + timedelta(days=index)).isoformat(), "value": 100 * (1.10 ** (index / 365.2425))}
            for index in range(days)
        ]

    def test_period_end_sampling(self):
        points = [
            {"date": "2024-01-12", "value": 1}, {"date": "2024-01-31", "value": 2},
            {"date": "2024-02-28", "value": 3}, {"date": "2024-03-29", "value": 4},
            {"date": "2024-04-30", "value": 5}, {"date": "2024-06-28", "value": 6},
        ]
        self.assertEqual(len(sample_period_ends(points, "monthly")), 5)
        self.assertEqual([p["date"] for p in sample_period_ends(points, "quarterly")], ["2024-03-29", "2024-06-28"])
        self.assertEqual(sample_period_ends(points, "semiannual")[-1]["date"], "2024-06-28")

    def test_annualized_return_uses_elapsed_days(self):
        samples = holding_period_returns(self.daily_growth_points(), "semiannual", 1, "annualized")
        self.assertGreater(len(samples), 2)
        self.assertAlmostEqual(samples[0]["value"], 10.0, places=1)

    def test_cumulative_return_and_summary(self):
        samples = holding_period_returns(self.daily_growth_points(), "quarterly", 1, "cumulative")
        self.assertAlmostEqual(samples[0]["value"], 10.0, places=1)
        summary = return_summary(samples)
        self.assertEqual(summary["count"], len(samples))
        self.assertEqual(summary["win_rate"], 100.0)
        self.assertAlmostEqual(
            summary["average"],
            round(sum(sample["value"] for sample in samples) / len(samples), 2),
        )

    def test_return_summary_average_uses_all_samples(self):
        summary = return_summary([{"value": 1.0}, {"value": 2.0}, {"value": 6.0}])
        self.assertEqual(summary["average"], 3.0)
        self.assertEqual(summary["median"], 2.0)
        self.assertIsNone(return_summary([])["average"])

    def test_rejects_invalid_options(self):
        with self.assertRaises(ValueError):
            holding_period_returns([], "weekly", 5, "annualized")
        with self.assertRaises(ValueError):
            holding_period_returns([], "monthly", 2, "annualized")

    def test_display_resampling_uses_real_period_end_observations(self):
        points = [
            {"date": "2024-01-02", "value": 1}, {"date": "2024-01-31", "value": 2},
            {"date": "2024-02-29", "value": 3}, {"date": "2024-04-30", "value": 4},
        ]
        self.assertEqual(len(resample_points(points, "daily")), 4)
        self.assertEqual([point["value"] for point in resample_points(points, "monthly")], [2, 3, 4])
        self.assertEqual([point["value"] for point in resample_points(points, "quarterly")], [3, 4])
        self.assertEqual([point["value"] for point in resample_points(points, "yearly")], [4])

    def test_xirr_and_monthly_dca_cash_flow_semantics(self):
        rate = xirr([
            {"date": "2020-01-01", "value": -100},
            {"date": "2021-01-01", "value": 110},
        ])
        self.assertAlmostEqual(rate, 0.10, delta=0.001)

        points = []
        current = date(2020, 1, 31)
        for index in range(49):
            points.append({"date": current.isoformat(), "value": 100})
            current = date(current.year + (current.month == 12), current.month % 12 + 1, 28)
        result = monthly_dca_backtest(points, 3, 1000)
        self.assertEqual(result["ending_value"], result["total_invested"])
        self.assertAlmostEqual(result["annualized_return"], 0.0, places=2)
        self.assertEqual(result["contribution_count"], len(result["curve"]))

    def test_scheduled_dca_supports_month_day_weekday_and_explicit_range(self):
        start = date(2024, 1, 1)
        points = [
            {"date": (start + timedelta(days=offset)).isoformat(), "value": 100 + offset}
            for offset in range(91)
            if (start + timedelta(days=offset)).isoweekday() <= 5
        ]
        monthly = scheduled_dca_backtest(
            points, "2024-01-01", "2024-03-31", "monthly", 3, 1000
        )
        self.assertEqual(monthly["contribution_count"], 3)
        self.assertEqual(monthly["adjusted_count"], 2)
        self.assertEqual(monthly["contributions"][1]["scheduled_date"], "2024-02-03")
        self.assertEqual(monthly["contributions"][1]["execution_date"], "2024-02-05")
        self.assertEqual(monthly["end_date"], "2024-03-29")
        self.assertFalse(monthly["range_clipped"])

        weekly = scheduled_dca_backtest(
            points, "2024-01-01", "2024-01-31", "weekly", 7, 1000
        )
        self.assertEqual(weekly["contribution_count"], 4)
        self.assertTrue(all(item["adjusted"] for item in weekly["contributions"]))
        self.assertEqual(weekly["contributions"][0]["execution_date"], "2024-01-08")

    def test_scheduled_dca_rejects_invalid_range_and_monthly_only_data(self):
        points = [{"date": f"2024-{month:02d}-01", "value": 100} for month in range(1, 7)]
        with self.assertRaisesRegex(ValueError, "daily observations"):
            scheduled_dca_backtest(points, "2024-01-01", "2024-06-30", "weekly", 1, 1000)
        with self.assertRaisesRegex(ValueError, "must not be later"):
            scheduled_dca_backtest(points, "2024-06-01", "2024-01-01", "monthly", 1, 1000)

    def test_scheduled_dca_skips_source_gaps_instead_of_long_adjustments(self):
        points = []
        for period_start in (date(2024, 1, 1), date(2024, 4, 1)):
            for offset in range(12):
                current = period_start + timedelta(days=offset)
                if current.isoweekday() <= 5:
                    points.append({"date": current.isoformat(), "value": 100})
        result = scheduled_dca_backtest(
            points, "2024-01-01", "2024-04-10", "monthly", 1, 1000
        )
        self.assertEqual(result["contribution_count"], 2)
        self.assertEqual(result["skipped_count"], 2)


if __name__ == "__main__":
    unittest.main()
