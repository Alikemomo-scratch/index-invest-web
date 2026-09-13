import unittest
import hashlib
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.sources import (
    FUNDDB_SIGNING_SALT,
    SourceError,
    _TableParser,
    _funddb_signed_payload,
    _parse_government_bond_rows,
    _parse_csi_indicator_rows,
    fetch_funddb_dividend_yield,
    fetch_government_bond_yields,
    fetch_tencent_adjusted_history,
)


class SourceParserTests(unittest.TestCase):
    def test_csi_indicator_parser_preserves_both_share_capital_definitions(self):
        rows = [[
            "日期Date", "名称", "代码", "空", "空", "空",
            "市盈率1（总股本）P/E1", "市盈率2（计算用股本）P/E2",
            "股息率1（总股本）D/P1", "股息率2（计算用股本）D/P2",
        ], ["20260908", "指数", "930740", "", "", "", 9.04, 8.97, 4.31, 4.63]]
        point = _parse_csi_indicator_rows(rows)[0]
        self.assertEqual(point["pe"], 8.97)
        self.assertEqual(point["pe_total_share"], 9.04)
        self.assertEqual(point["dividend_yield"], 4.63)
        self.assertEqual(point["dividend_yield_total_share"], 4.31)
        self.assertEqual(point["dividend_yield_calculation_share"], 4.63)

    def test_funddb_signature_and_dividend_series_parser(self):
        timestamp = 1_725_000_000_000
        signed = _funddb_signed_payload("930740.CSI", 10, timestamp)
        unsigned_keys = {
            "gu_code", "pe_category", "year", "ver", "type", "version",
            "authtoken", "act_time",
        }
        digest_input = "".join(
            str(signed[key]) for key in sorted(unsigned_keys) if signed[key]
        ) + FUNDDB_SIGNING_SALT
        digest = hashlib.md5(digest_input.encode("utf-8")).hexdigest()
        self.assertEqual(signed["tirgkjfs"], digest[0:2])
        self.assertEqual(signed["h13ey474"], digest[29:32])

        # Provider timestamps represent midnight in China (16:00 UTC on the prior day).
        start = datetime(2024, 12, 31, 16, tzinfo=timezone.utc)
        rows = [
            [int((start + timedelta(days=index)).timestamp() * 1000), 3 + index / 100]
            for index in range(12)
        ]
        response = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {"tubiao": {"series": [{"name": "股息率", "data": rows}]}},
        }
        client = MagicMock()
        client.post.return_value = response
        context = MagicMock()
        context.__enter__.return_value = client
        with patch("app.sources._client", return_value=context):
            points = fetch_funddb_dividend_yield("930740.CSI")
        self.assertEqual(len(points), 12)
        self.assertEqual(points[0], {"date": "2025-01-01", "value": 3.0})
        self.assertEqual(client.post.call_args.kwargs["data"]["pe_category"], "xilv")

    def test_funddb_dividend_parser_rejects_missing_series(self):
        response = MagicMock()
        response.json.return_value = {"code": 0, "data": {"tubiao": {"series": []}}}
        client = MagicMock()
        client.post.return_value = response
        context = MagicMock()
        context.__enter__.return_value = client
        with patch("app.sources._client", return_value=context), self.assertRaises(SourceError):
            fetch_funddb_dividend_yield("931446.CSI")

    def test_government_bond_parser_preserves_both_10_year_series(self):
        rows = [
            {
                "SOLAR_DATE": "2026-09-08 00:00:00",
                "EMM00166466": 1.6815,
                "EMG00001310": 4.8,
            },
            {"SOLAR_DATE": "invalid", "EMM00166466": 2.0},
        ]
        self.assertEqual(_parse_government_bond_rows(rows), [{
            "date": "2026-09-08", "china_10y": 1.6815, "us_10y": 4.8,
        }])

    def test_government_bond_adapter_paginates_and_validates_history(self):
        start = date(2026, 1, 1)
        rows = [
            {
                "SOLAR_DATE": (start + timedelta(days=index)).isoformat(),
                "EMM00166466": 1.5 + index / 1000,
                "EMG00001310": 4.0 + index / 1000,
            }
            for index in range(40)
        ]
        responses = []
        for page_rows in (rows[:20], rows[20:]):
            response = MagicMock()
            response.json.return_value = {
                "success": True,
                "result": {"pages": 2, "data": page_rows},
            }
            responses.append(response)
        client = MagicMock()
        client.get.side_effect = responses
        context = MagicMock()
        context.__enter__.return_value = client
        with patch("app.sources._client", return_value=context):
            points = fetch_government_bond_yields(10)
        self.assertEqual(len(points), 40)
        self.assertEqual(client.get.call_count, 2)
        self.assertEqual(points[-1]["us_10y"], 4.039)
        self.assertEqual(client.get.call_args.kwargs["params"]["ps"], "500")

    def test_html_table_parser_collects_nested_cell_text(self):
        parser = _TableParser()
        parser.feed("<table><tr><th>Date</th><th>Value</th></tr><tr><td>Jan 1, 2026</td><td><span>†</span> 24.3</td></tr></table>")
        self.assertEqual(parser.rows[1], ["Jan 1, 2026", "† 24.3"])

    def test_tencent_adapter_parses_adjusted_daily_close(self):
        start = date(2025, 1, 1)
        rows = [
            [(start + timedelta(days=index)).isoformat(), "1.00", f"{1 + index / 1000:.3f}"]
            for index in range(200)
        ]
        response = MagicMock()
        response.json.return_value = {"code": 0, "data": {"sh515450": {"qfqday": rows}}}
        client = MagicMock()
        client.get.return_value = response
        context = MagicMock()
        context.__enter__.return_value = client
        with patch("app.sources._client", return_value=context):
            points = fetch_tencent_adjusted_history("sh515450")
        self.assertEqual(len(points), 200)
        self.assertEqual(points[0], {"date": "2025-01-01", "value": 1.0})
        self.assertEqual(points[-1]["value"], 1.199)
        self.assertIn(",qfq", client.get.call_args.kwargs["params"]["param"])

    def test_tencent_adapter_rejects_wrong_instrument(self):
        response = MagicMock()
        response.json.return_value = {"code": 0, "data": {"wrong": {"qfqday": []}}}
        client = MagicMock()
        client.get.return_value = response
        context = MagicMock()
        context.__enter__.return_value = client
        with patch("app.sources._client", return_value=context), self.assertRaises(SourceError):
            fetch_tencent_adjusted_history("sh515450")


if __name__ == "__main__":
    unittest.main()
