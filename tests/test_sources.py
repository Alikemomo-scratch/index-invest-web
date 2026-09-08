import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.sources import SourceError, _TableParser, fetch_tencent_adjusted_history


class SourceParserTests(unittest.TestCase):
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
