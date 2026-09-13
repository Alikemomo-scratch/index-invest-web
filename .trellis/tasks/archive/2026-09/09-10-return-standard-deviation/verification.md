# Verification

## Automated checks

- `.venv/bin/python -m unittest tests.test_calculations tests.test_frontend_contract`: 18 tests passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`: 44 tests passed.
- `.venv/bin/python -m compileall app tests run.py`: passed after allowing Python to write its standard macOS bytecode cache.
- `.venv/bin/python -m pip check`: no broken requirements.
- `node --check static/app.js`: passed.

## Browser smoke

- Current annualized view displayed `年化收益标准差` with `9.1%` for CSI 300, quarterly anchors, and a five-year holding period.
- Switching the measure displayed `累计收益标准差` with `70.9%`.
- Browser console had no errors.
- At the 390 px responsive breakpoint, document `scrollWidth` equaled `clientWidth`; no horizontal overflow was introduced.

## Scope guard

- Existing dividend-yield, risk-premium, earnings-growth, and valuation-triggered DCA work remained in place.
- This task did not change holding-period sample eligibility or return formulas.
