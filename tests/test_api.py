import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.main import service


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_catalog_are_available_without_network(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["local_only"])

        catalog = self.client.get("/api/indices")
        self.assertEqual(catalog.status_code, 200)
        items = catalog.json()["items"]
        markets = {item["market"] for item in items}
        self.assertEqual(markets, {"cn", "us"})
        ids = {item["id"] for item in items}
        self.assertTrue({
            "csi300_div_low_vol", "csi_div_low_vol", "csi_div_low_vol_100",
            "csi_dfh_div_low_vol", "sp_china_a_div_low_vol_50",
        }.issubset(ids))

    def test_unknown_index_returns_404(self):
        response = self.client.get("/api/indices/not-an-index/research")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown index", response.json()["detail"])

    def test_invalid_research_and_return_options_return_422(self):
        invalid_lookback = self.client.get("/api/indices/csi300/research?lookback_years=7")
        self.assertEqual(invalid_lookback.status_code, 422)

        invalid_frequency = self.client.get("/api/indices/csi300/returns?frequency=weekly")
        self.assertEqual(invalid_frequency.status_code, 422)
        self.assertIn("frequency", invalid_frequency.json()["detail"])

    def test_refresh_uses_current_query_options(self):
        research_payload = {"status": "ready", "metrics": []}
        returns_payload = {"status": "ready", "samples": []}
        dca_payload = {"status": "ready", "result": {}}
        with patch.object(service, "get_research", return_value=research_payload) as research, patch.object(
            service, "get_returns", return_value=returns_payload
        ) as returns, patch.object(service, "get_dca", return_value=dca_payload) as dca:
            response = self.client.post(
                "/api/refresh/csi300?lookback_years=15&history_frequency=quarterly&frequency=monthly"
                "&holding_years=10&measure=cumulative&dca_amount=2500"
                "&dca_start_date=2020-01-01&dca_end_date=2025-12-31"
                "&dca_cadence=weekly&dca_schedule_value=3"
            )
        self.assertEqual(response.status_code, 200)
        research.assert_called_once_with("csi300", 15, "quarterly", force=True)
        returns.assert_called_once_with("csi300", "monthly", 10, "cumulative", force=True)
        dca.assert_called_once_with(
            "csi300", 10, 2500, "2020-01-01", "2025-12-31", "weekly", 3
        )

    def test_validation_requires_reference_value_and_date(self):
        response = self.client.get("/api/indices/sp500/validation?metric_id=pe")
        self.assertEqual(response.status_code, 422)

    def test_dca_rejects_invalid_schedule_and_date_range_before_fetch(self):
        invalid_weekday = self.client.get(
            "/api/indices/csi300/dca?start_date=2024-01-01&end_date=2024-12-31"
            "&cadence=weekly&schedule_value=8"
        )
        self.assertEqual(invalid_weekday.status_code, 422)
        reversed_range = self.client.get(
            "/api/indices/csi300/dca?start_date=2025-01-01&end_date=2024-01-01"
        )
        self.assertEqual(reversed_range.status_code, 422)


if __name__ == "__main__":
    unittest.main()
