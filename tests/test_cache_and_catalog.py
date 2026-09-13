import tempfile
import unittest
from pathlib import Path

from app.cache import JsonCache
from app.catalog import INDEX_CATALOG, get_index


class CacheAndCatalogTests(unittest.TestCase):
    def test_cache_roundtrip_keeps_coverage_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = JsonCache(Path(directory) / "cache.sqlite3")
            payload = [{"date": "2024-01-31", "value": 1}, {"date": "2024-02-29", "value": 2}]
            cache.put("sample", payload, "fixture", [item["date"] for item in payload])
            stored = cache.get("sample")
            self.assertEqual(stored["payload"], payload)
            self.assertEqual(stored["point_count"], 2)
            self.assertEqual(stored["first_date"], "2024-01-31")

    def test_catalog_covers_both_markets_and_discloses_return_type(self):
        self.assertEqual({item.market for item in INDEX_CATALOG.values()}, {"cn", "us"})
        self.assertEqual(get_index("csi300").return_type, "total_return")
        self.assertEqual(get_index("nasdaq100").return_type, "price_return")
        expected = {
            "csi300_div_low_vol": ("300 红利低波", "930740", "H20740"),
            "csi_div_low_vol": ("红利低波", "H30269", "H20269"),
            "csi_div_low_vol_100": ("红利低波 100", "930955", "H20955"),
            "csi_dfh_div_low_vol": ("东证红利低波", "931446", "921446"),
        }
        for index_id, (name, code, return_code) in expected.items():
            item = get_index(index_id)
            self.assertEqual(item.name, name)
            self.assertEqual(item.code, code)
            self.assertEqual(item.price_code, return_code)
            self.assertEqual(item.return_type, "total_return")
        sp_china = get_index("sp_china_a_div_low_vol_50")
        self.assertEqual(sp_china.code, "SPCLLHCP")
        self.assertEqual(sp_china.price_code, "sh515450")
        self.assertEqual(sp_china.return_type, "adjusted_proxy")
        with self.assertRaises(KeyError):
            get_index("unknown")

    def test_catalog_has_explicit_public_dividend_history_routes(self):
        expected = {
            "csi300": "000300.SH",
            "csi500": "000905.SH",
            "csi1000": "000852.SH",
            "sse50": "000016.SH",
            "sse_dividend": "000015.SH",
            "csi300_div_low_vol": "930740.CSI",
            "csi_div_low_vol": "h30269.CSI",
            "csi_div_low_vol_100": "930955.CSI",
            "csi_dfh_div_low_vol": None,
        }
        self.assertEqual(
            {index_id: get_index(index_id).dividend_history_code for index_id in expected},
            expected,
        )
        self.assertEqual(
            {get_index(index_id).valuation_provider for index_id in expected},
            {"csi_legu"},
        )


if __name__ == "__main__":
    unittest.main()
