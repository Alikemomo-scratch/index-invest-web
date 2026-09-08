import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
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
        self.assertIn('/static/app.js?v=', html)
        self.assertIn('/static/interaction.css?v=', html)
        self.assertNotIn('id="returnBars"', html)
        self.assertIn("function updateReturnHover(event)", script)
        self.assertIn('$("returnSvg").addEventListener("pointermove", updateReturnHover)', script)
        self.assertIn('$("returnSvg").addEventListener("pointerleave", hideReturnHover)', script)
        self.assertIn('start.textContent=`买入 ${formatDate(sample.start_date)}`', script)
        self.assertIn('end.textContent=`结束 ${formatDate(sample.end_date)}`', script)
        self.assertIn('formatPct(summary.average)', script)
        self.assertIn('"累计收益平均值"', script)


if __name__ == "__main__":
    unittest.main()
