# Valuation Validation and Monthly DCA Research

Date: 2026-09-08

## S&P 500 PE observation

- The user observed S&P 500 PE `26.12` in Futu for 2026-09-04. This is user-provided evidence; the Futu calculation policy was not independently retrieved.
- Multpl publishes `26.36` for 2026-09-04 and explicitly marks it as an estimate: <https://www.multpl.com/s-p-500-pe-ratio/table/by-month>.
- Relative difference using the Futu observation as reference is `abs(26.36 - 26.12) / 26.12 = 0.92%`.
- S&P DJI's index mathematics methodology defines constituent and index attribute calculations, including LTM earnings inputs and float-adjusted data: <https://www.spglobal.com/spdji/en/documents/methodologies/methodology-index-math.pdf>.
- Conclusion: the two observations are numerically consistent under a 2% comparison tolerance, but this is not proof of identical methodology. The UI must preserve `estimated` and `definition_unknown` disclosures.

## Validation design

Use three independent checks:

1. Date alignment: exact date preferred; otherwise disclose nearest observation and day distance.
2. Numeric comparison: relative difference against an explicit user-selected tolerance.
3. Definition alignment: trailing/forward/static, aggregation method, constituent universe, loss-company handling, and estimated/final status. If either source does not disclose these fields, return `definition_unknown`.

Validation status:

- `consistent`: exact or near date, numeric difference within tolerance, but not a claim of truth.
- `source_mismatch`: difference exceeds tolerance.
- `date_mismatch`: no observation within seven days.
- `definition_unknown`: values are comparable but methodology identity cannot be verified.

## Valuation chart granularity

- Offer `daily`, `monthly`, `quarterly`, and `yearly` display intervals.
- Never upsample. If a source only has monthly or quarterly observations, choosing daily retains the original sparse points.
- Percentile calculation remains month-end based so changing visual resolution does not silently change the valuation statistic.

## Monthly DCA backtest

- Investor.gov defines dollar-cost averaging as investing equal portions at regular intervals: <https://www.investor.gov/introduction-investing/investing-basics/glossary/dollar-cost-averaging>.
- Contributions buy fractional index units at the final valid observation of each month.
- Use total-return indices where available. S&P DJI states that total-return indices reflect price movement plus reinvested dividend income: <https://www.spglobal.com/spdji/en/methodology/article/index-mathematics-methodology/>.
- Money-weighted annualized return is XIRR over dated negative contributions plus the final positive portfolio value. Microsoft documents that XIRR requires at least one positive and one negative cash flow: <https://support.microsoft.com/en-us/excel/functions/xirr-function>.
- Show total contributed, ending value, profit, cumulative return, XIRR, contribution count, and a portfolio-value-versus-contributed-capital chart.
- MVP excludes fees, taxes, tracking error, FX conversion, inflation, and whole-share constraints. These omissions must be visible.
