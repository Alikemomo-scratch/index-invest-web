# Chart Interaction Contracts

> Executable UI contracts for valuation and holding-return inspection plus manual data refresh.

## Scenario: Inspect a valuation point and refresh the active research view

### 1. Scope / Trigger

- Trigger: changing valuation SVG rendering, research controls, or the manual refresh flow.
- Applies to `static/index.html`, `static/app.js`, and chart-specific CSS.

### 2. Signatures

```text
renderHistory(metric)
updateHistoryHover(pointerEvent)
hideHistoryHover()
renderReturnChart(samples)
updateReturnHover(pointerEvent)
hideReturnHover()
refreshCurrent()
renderDca(payload)
runValidation()
```

Stable DOM hooks include `historySvg`, `historyFrequencySelect`, `historyTooltip`, `riskPremiumAudit`, `riskPremiumFormula`, `riskPremiumSources`, `returnSvg`, `returnLine`, `returnTooltip`, `returnHoverLine`, `returnHoverHorizontal`, `returnHoverDot`, `returnDates`, `dcaSvg`, `dcaStartDate`, `dcaEndDate`, `dcaCadence`, `dcaScheduleValue`, `contributionAmountInput`, validation inputs/result fields, and `refreshButton`.

### 3. Contracts

- Pointer movement over an available valuation series selects the nearest observation by x-position.
- The tooltip displays the metric value with unit and the observation date.
- Vertical and horizontal guide lines plus a point marker identify the selected observation.
- Pointer leave hides every hover artifact; changing metric clears the prior hover state.
- Holding-return samples render as one continuous line ordered by historical buy date; bars are not used.
- Holding-return summary cards display arithmetic average, median, and population standard deviation for the same complete samples. Their labels switch between annualized and cumulative wording with the active measure.
- Updated interactive CSS and JavaScript assets use versioned URLs in `index.html` so a browser does not combine new DOM hooks with stale rendering code.
- Pointer movement over the return line selects the nearest sample by x-position and displays its return, `start_date`, and `end_date` with vertical and horizontal guide lines.
- Redrawing or emptying the return chart clears hover state and artifacts. The zero-return reference line remains visible whenever samples exist.
- Refresh sends the active index, lookback, frequency, holding years, and measure to the refresh API.
- Refresh must not reset active controls. `已更新` means fresh remote data; `使用缓存` means at least one returned series is stale.
- The return panel displays `data_as_of` separately from the latest complete sample start/end dates.
- Valuation display granularity has daily/monthly/quarterly/yearly choices. Plotted point count is labeled separately from the fixed month-end percentile sample count.
- When dividend yield is active, the valuation footer displays official CSI
  D/P1 and D/P2 comparison values plus the aggregate history's date range,
  valid-month count, missing-month count, and requested-range clipping state.
- Public aggregate dividend history is visibly marked as methodology
  unconfirmed and is not presented as an official D/P1 or D/P2 history.
- Earnings-yield and dividend-yield premium cards display the exact formula and
  both component sources. Their percentile direction is higher-is-cheaper.
- Risk-premium charts allow a domain below zero; the scale must not clamp the
  minimum to zero when `allow_negative` is true.
- DCA controls send an explicit range, monthly/weekly cadence, calendar day/weekday, and per-contribution amount.
- Changing cadence rebuilds the schedule choices as 1–31 calendar days or Monday–Sunday without losing unrelated controls.
- The DCA chart draws accumulated capital and portfolio value. Summary cards display XIRR, total invested, ending value, profit, contribution count, and non-trading-day adjustment count.
- Validation reports the nearest observed date, relative difference, status, estimate flag, and methodology certainty independently.
- The built-in S&P 500 sample fills 2026-09-04, PE 26.12, and the user-observed Futu source before running validation.

### 4. Validation & Error Matrix

| Condition | Required UI behavior |
| --- | --- |
| No metric history | Hide hover artifacts and show the chart empty state |
| No complete holding-return samples | Clear the line, zero line, current marker, and hover artifacts; show the return-chart empty state |
| Return summary is empty or the request fails | Display `—` for standard deviation and every other summary value; never retain a value from the prior selection |
| Pointer outside plot bounds | Clamp selection to the first or last observation |
| Refresh fails | Keep the existing chart, show the error, and restore the refresh button |
| User changes controls during refresh | Ignore the superseded refresh response using the request token |
| Response contains stale data | Show stale notice and use the `使用缓存` completion label |
| Complete holding samples end before the current date | Display both `data_as_of` and the latest complete sample window |
| High-frequency history is unavailable | Show only real available observations; never create interpolated points |
| Dividend history covers less than the selected lookback | Keep the real series and percentile if sample count permits, and disclose the clipped requested range |
| Risk premium contains negative values | Plot the full negative domain and keep those points in sample counts |
| One risk-premium component is unavailable | Disable only that metric card and show the backend reason |
| DCA input is invalid or history is insufficient | Keep research panels intact and show an actionable DCA notice |
| Requested end is newer than source history | Keep the user-selected date, disclose the effective valuation range, and never extrapolate |
| Monthly or weekly schedule lands on a closed market day | Display the backend adjustment count; backend evidence remains the source of truth |
| Validation is within tolerance but methodology is unknown | Show `数值一致` and `口径未确认` together |
| HTML adds a new DOM hook but cached JavaScript predates it | Version the changed static asset URLs; never leave the new card permanently empty because of a mixed asset revision |

### 5. Good / Base / Bad Cases

- Good: hover tracks the line, date/value remain readable, and refresh redraws the same active selections with fresh data.
- Good: return hover displays the exact sample's buy date, end date, and annualized or cumulative value while both crosshair guides track the point; the summary card displays the matching measure's standard deviation.
- Base: the source is current but the latest eligible buy date is N years earlier; the date row explains the distinction.
- Bad: rendering bars or showing only the buy date hides the time window represented by each holding-return sample.
- Bad: a stale refresh response arrives after another control change; it must not overwrite the newer view.
- Good: the Futu sample produces 26.12 vs 26.36 and 0.92%, while retaining unknown definition status.
- Base: choosing daily over a monthly-only source shows the same real points with a daily display label; no values are invented.

### 6. Tests Required

- JavaScript syntax check.
- API test asserting refresh query options are forwarded with `force=True`.
- Browser smoke test for PE and PB hover readouts, both guide lines, active-control preservation, completion label, and freshness date row.
- Frontend contract and browser smoke tests asserting the return chart has a line rather than bars, pointer movement reveals both sample dates and value, both guide lines are visible, and pointer leave clears the tooltip.
- Frontend contract and browser smoke tests assert the average and standard-deviation cards render `summary.average` and `summary.standard_deviation`, and both labels change with the active measure.
- Responsive check at 390 px without horizontal overflow.
- Browser smoke for all valuation display units, unchanged percentile, custom DCA date range/month day/weekday/amount, and built-in validation evidence.
- Frontend contract and browser smoke for both risk-premium formulas, component
  sources, 3/5/10-year sample counts, and a negative-value chart.

### 7. Wrong vs Correct

#### Wrong

```javascript
fetch(`/api/refresh/${state.indexId}`, {method: "POST"});
```

This silently refreshes server defaults and can redraw data that does not match the visible controls.

#### Correct

```javascript
const query = new URLSearchParams({
  lookback_years: state.lookback,
  history_frequency: state.historyFrequency,
  frequency: state.frequency,
  holding_years: state.years,
  measure: state.measure,
  dca_amount: state.contributionAmount,
  dca_start_date: state.dcaStartDate,
  dca_end_date: state.dcaEndDate,
  dca_cadence: state.dcaCadence,
  dca_schedule_value: state.dcaScheduleValue,
});
fetch(`/api/refresh/${state.indexId}?${query}`, {method: "POST"});
```

#### Wrong

```javascript
$("standardDeviationReturn").textContent = cachedStandardDeviation;
```

This can leave an annualized value visible after switching to cumulative returns or after a request failure.

#### Correct

```javascript
$("standardDeviationReturn").textContent = formatPct(payload.summary.standard_deviation);
$("standardDeviationLabel").textContent = state.measure === "annualized"
  ? "年化收益标准差"
  : "累计收益标准差";
```
