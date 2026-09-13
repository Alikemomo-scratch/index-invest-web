import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_dividend_history_discloses_official_definitions_and_coverage(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="dividendAudit"', html)
        self.assertIn('id="dividendOfficial"', html)
        self.assertIn('id="dividendCoverage"', html)
        self.assertIn('/static/dividend.css?v=', html)
        self.assertIn("function renderDividendAudit(metric)", script)
        self.assertIn('metric.official_values || []', script)
        self.assertIn('官方核对：', script)
        self.assertIn('A 股股息率历史来自公共聚合源', html)
        self.assertIn('coverage.missing_month_count', script)
        self.assertIn('coverage.requested_range_clipped', script)

    def test_risk_premium_cards_disclose_formula_sources_and_support_negative_chart_values(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="riskPremiumAudit"', html)
        self.assertIn("盈利收益率溢价 = 100 ÷ PE TTM", html)
        self.assertIn("function renderRiskPremiumAudit(metric)", script)
        self.assertIn('metric.component_sources || []', script)
        self.assertIn('metric.allow_negative ? min - pad', script)

    def test_return_research_uses_interactive_line_chart(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="returnLine"', html)
        self.assertIn('id="returnTooltip"', html)
        self.assertIn('id="zeroLine"', html)
        self.assertIn('id="returnHoverLine"', html)
        self.assertIn('id="returnHoverHorizontal"', html)
        self.assertIn('id="returnHoverDot"', html)
        self.assertIn('id="averageLabel"', html)
        self.assertIn('id="averageReturn"', html)
        self.assertIn('id="standardDeviationLabel"', html)
        self.assertIn('id="standardDeviationReturn"', html)
        self.assertIn('/static/app.js?v=', html)
        self.assertIn('/static/interaction.css?v=', html)
        self.assertNotIn('id="returnBars"', html)
        self.assertIn("function updateReturnHover(event)", script)
        self.assertIn('$("returnSvg").addEventListener("pointermove", updateReturnHover)', script)
        self.assertIn('$("returnSvg").addEventListener("pointerleave", hideReturnHover)', script)
        self.assertIn('start.textContent=`买入 ${formatDate(sample.start_date)}`', script)
        self.assertIn('end.textContent=`结束 ${formatDate(sample.end_date)}`', script)
        self.assertIn('formatPct(summary.average)', script)
        self.assertIn('formatPct(summary.standard_deviation)', script)
        self.assertIn('"累计收益平均值"', script)
        self.assertIn('"累计收益标准差"', script)


if __name__ == "__main__":
    unittest.main()
