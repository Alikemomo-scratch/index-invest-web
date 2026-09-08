# Index Research Data Contracts

> Executable contracts for source adapters, cache behavior, valuation research, and holding-period return analysis.

## Scenario: Public index research with transparent degradation

### 1. Scope / Trigger

- Trigger: adding or changing a market data source, cache record, research API, or return calculation.
- Data flow: public source -> adapter -> SQLite JSON cache -> service normalization -> FastAPI -> browser.
- The product is a research tool. Missing data must remain missing; it must not be synthesized only to complete the interface.

### 2. Signatures

```text
GET  /api/indices
GET  /api/indices/{index_id}/research?lookback_years={3|5|10|15|20}&history_frequency={daily|monthly|quarterly|yearly}
GET  /api/indices/{index_id}/returns?frequency={monthly|quarterly|semiannual}&holding_years={1|3|5|10}&measure={annualized|cumulative}
GET  /api/indices/{index_id}/dca?contribution_amount={(0,10000000]}&start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}&cadence={monthly|weekly}&schedule_value={1..31 monthly|1..7 weekly}
GET  /api/indices/{index_id}/validation?metric_id={pe|pb|dividend_yield}&reference_value={positive finite number}&reference_date={YYYY-MM-DD}&reference_source={text}&tolerance_pct={(0,100]}
POST /api/refresh/{index_id}?lookback_years={3|5|10|15|20}&history_frequency={daily|monthly|quarterly|yearly}&frequency={monthly|quarterly|semiannual}&holding_years={1|3|5|10}&measure={annualized|cumulative}&dca_amount={(0,10000000]}&dca_start_date={YYYY-MM-DD}&dca_end_date={YYYY-MM-DD}&dca_cadence={monthly|weekly}&dca_schedule_value={integer}
```

Cache identity is `cache_key`; `source_id` is stored as record metadata. Each record stores JSON payload plus `fetched_at`, `first_date`, `last_date`, and `point_count`.

### 3. Contracts

Research metrics expose:

- `id`, `label`, `unit`, `value`, `date`, `status`
- `percentile`, `lookback_years`, `sample_count`, `history`
- `source` with `id`, `name`, `tier`, and source URL
- `stale`, `partial`, `reason` or `note` when applicable
- `cross_check` when an official and aggregated value can be compared

Return results expose:

- the validated request fields and normalized index identity
- `return_type` and `return_label`; use `total_return` only for a total-return series
- actual `source`, optional `fallback_from`, `warning`, `stale`, and `partial`
- `samples` and `summary` (`average`, `median`, `win_rate`, `worst`, `best`, `count`); `average` is the arithmetic mean of every complete sample under the active annualized/cumulative measure
- `data_as_of`, `latest_complete_start`, and `latest_complete_end` so the UI distinguishes source freshness from eligible buy dates

No credentials are required for MVP. The local cache path is `data/index-invest.sqlite3` and must not be committed.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Unknown `index_id` | HTTP 404 with an actionable detail message |
| Unsupported query value | HTTP 422; do not coerce to a nearby option |
| Primary source fails, complete cache exists | Return cache with `stale: true` and explain the failure |
| New response is suspiciously truncated | Keep the more complete cache and mark the result partial/stale |
| Total-return series fails, price series works | Return price series with `fallback_from` and dividend-exclusion warning |
| Metric history has fewer than 36 month-end samples | Return current value if available; percentile is null with `insufficient_history` |
| Metric source unavailable | Return an unavailable metric object; never invent a proxy silently |
| Official/aggregated PE difference exceeds 25% | Keep the official current value and return `source_mismatch` |
| Holding period has no valid ending observation | Omit that sample; do not extrapolate beyond available data |
| Buy anchor has not yet completed N years | Omit it from both the chart and summary; do not mix partial holding windows with complete samples |
| Manual refresh uses non-default controls | Force the same lookback, frequency, holding years, and measure; preserve the selected UI state |

### 5. Good / Base / Bad Cases

- Good: official PE and dividend yield, public PB history, total-return series, and fresh cache all resolve; the response is complete and traceable.
- Base: one metric lacks sufficient history; other metrics and return analysis remain usable while the missing percentile is explicit.
- Bad: an upstream parser returns a short or malformed series; the adapter raises `SourceError`, and the service uses a prior complete cache or reports unavailability.

### 6. Tests Required

- Unit: empirical percentile, month-end sampling, exact anniversary lookup, annualized and cumulative return formulas.
- Unit: return summary average uses all complete samples, is rounded to two decimals, and is null for an empty sample set.
- Cache: fresh hit, stale fallback, completeness guard, and metadata round-trip.
- Adapter: fixture parsing, future-estimate filtering, malformed-response rejection.
- Service/API: A-share and US research, total-to-price fallback semantics, validation errors, current-option refresh forwarding, freshness dates, and all 24 frequency/holding/measure combinations per representative index.
- Browser smoke: desktop and 390 px layouts, index/metric/control switching, actionable partial states, and zero console errors.

### 7. Wrong vs Correct

#### Wrong

```python
# A price index is presented as total return after the preferred source fails.
return {"return_type": "total_return", "samples": calculate(price_points)}
```

#### Correct

```python
return {
    "return_type": "price_return",
    "fallback_from": preferred_total_return_code,
    "warning": "Price return excludes reinvested dividends.",
    "samples": calculate(price_points),
}
```

## Design decisions

### Fixed provider chains by market

Each catalog entry owns a deterministic primary and fallback chain. Adapters return the actual successful source and coverage metadata; callers must not infer the source from the requested index alone.

### Month-end valuation percentiles

Valuation history is normalized to the last valid observation of each calendar month. Percentile is the empirical CDF `count(value <= current) / sample_count * 100`. This prevents high-frequency recent data from outweighing older history.

### Exact return semantics

Buy anchors use the final valid trading observation in each requested month, quarter, or half-year. The end value is the closest valid observation on or before the target anniversary, and annualized return uses actual elapsed days.

Only complete N-year windows enter `samples` and `summary`. `data_as_of` may be current even though `latest_complete_start` is approximately N years earlier; clients must display both dates rather than treating the latest buy date as source freshness.

## Scenario: Display resampling, source validation, and scheduled DCA

### 1. Scope / Trigger

- Trigger: changing valuation history sampling, cross-source validation, scheduled DCA cash-flow logic, or any related API payload.
- Data flow: source series -> normalization/cache -> calculation/service -> FastAPI -> browser controls and charts.

### 2. Signatures

```text
GET /api/indices/{index_id}/research?lookback_years={3|5|10|15|20}&history_frequency={daily|monthly|quarterly|yearly}
GET /api/indices/{index_id}/dca?contribution_amount={(0,10000000]}&start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}&cadence={monthly|weekly}&schedule_value={integer}
GET /api/indices/{index_id}/validation?metric_id={pe|pb|dividend_yield}&reference_value={positive}&reference_date={YYYY-MM-DD}&reference_source={text}&tolerance_pct={(0,100]}
```

```python
resample_points(points, frequency) -> list[dict]
scheduled_dca_backtest(points, start_date, end_date, cadence, schedule_value, contribution_amount) -> dict
xirr(cashflows) -> float
ResearchService.validate_metric(index_id, metric_id, reference_value, reference_date, reference_source, tolerance_pct) -> dict
```

### 3. Contracts

- Resampling chooses the final real observation in each requested period and never interpolates or upsamples.
- Research responses expose both `history_frequency` and fixed `percentile_frequency: month_end`. Display frequency never changes percentile inputs.
- DCA accepts an inclusive explicit date range and either a calendar day for monthly cadence or ISO weekday for weekly cadence.
- A non-trading planned date moves to the first real observation on or after it, with a maximum 14-day adjustment. Longer source gaps are skipped and counted. Short months clamp the requested day to calendar month-end first. Executions beyond `end_date` are excluded and duplicate execution dates are deduplicated.
- Day-specific DCA requires real daily observations. Yahoo requests use `interval=1d` and daily-versioned cache keys; monthly source data must fail instead of pretending to be precise.
- Each contribution is a negative dated XIRR cash flow; terminal portfolio value uses the last observation on or before `end_date` and is the positive flow.
- DCA responses expose actual source/fallback/return type, warning, assumptions, requested/effective range, clipping status, cadence, schedule value, adjustment/skipped counts, and `contributions` with `scheduled_date` and `execution_date`.
- Validation exposes separate reference and observed evidence, day distance, relative difference, tolerance, source, estimate flag, definition status, and a conclusion. Numerical agreement is not proof of identical vendor methodology.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Unsupported history frequency or cadence | HTTP 422; never coerce to a default |
| DCA amount is non-finite, non-positive, or above 10,000,000 | HTTP 422 |
| Only one range boundary is supplied, dates are invalid, or start is after end | HTTP 422 before source access |
| Monthly schedule is outside 1–31 or weekly schedule is outside 1–7 | HTTP 422 |
| Typical source gap exceeds three days | `insufficient_data_granularity`; do not simulate chosen days from weekly/monthly data |
| The next observation is more than 14 days after a planned date | Skip and count that plan; do not treat a source outage as a market closure |
| DCA source loaded but requested history is unavailable | `insufficient_history`; preserve successful source metadata |
| Reference date is not `YYYY-MM-DD` | HTTP 422 |
| Nearest validation observation is more than seven days away | `date_mismatch`; do not interpret the numeric tolerance |
| Relative difference exceeds tolerance | `source_mismatch` |
| Difference is within tolerance but methodology is unavailable | `consistent` plus `definition_status: unknown` |
| Metric has no usable history | `unavailable` with an actionable reason |

### 5. Good / Base / Bad Cases

- Good: daily total-return data covers the explicit range, planned/execution dates are auditable, XIRR converges, and both capital/value curves are returned.
- Base: price-return fallback remains calculable but carries a dividend-exclusion warning; same-date valuation values may agree while definition status remains unknown.
- Bad: an unsupported unit, invalid range/schedule, monthly-only price series, or non-positive amount is rejected instead of silently changing the request.

### 6. Tests Required

- Unit: real period-end selection, no upsampling, and unchanged percentile/sample count across display frequencies.
- Unit: constant-price DCA returns zero XIRR; explicit ranges, short months, weekends, weekday schedules, clipping, deduplication, and daily-resolution rejection are asserted.
- Service/API: Futu 26.12 vs Multpl 26.36 on 2026-09-04 returns about 0.92%, `consistent`, estimated observed value, and unknown methodology.
- API/browser: refresh forwards history and DCA options; custom DCA years/amount and both curves render.

### 7. Wrong vs Correct

#### Wrong

```python
scheduled_dca_backtest(monthly_points, start, end, "weekly", 1, amount)
```

This gives false weekday precision when the source contains only monthly observations.

#### Correct

```python
daily_points = fetch_yahoo_history(symbol)  # interval=1d, daily cache key
result = scheduled_dca_backtest(daily_points, start, end, cadence, schedule_value, amount)
```

## Scenario: Dividend low-volatility index catalog and adjusted ETF proxy

### 1. Scope / Trigger

- Trigger: adding a dividend/low-volatility index identity, return-series code, or ETF proxy to `INDEX_CATALOG`.
- Data flow: official identity and return code -> catalog -> deterministic source adapter -> cache -> research/returns/DCA APIs -> dynamic browser selector.

### 2. Signatures

```text
GET /api/indices
GET /api/indices/{csi300_div_low_vol|csi_div_low_vol|csi_div_low_vol_100|csi_dfh_div_low_vol|sp_china_a_div_low_vol_50}/research
GET /api/indices/{index_id}/returns
GET /api/indices/{index_id}/dca
POST /api/refresh/{index_id}
```

```python
fetch_csi_history(index_code) -> list[dict]
fetch_tencent_adjusted_history("sh515450", start_year=2019) -> list[dict]
ResearchService._return_warning(return_type) -> str | None
```

### 3. Contracts

- Catalog identities are 930740 -> H20740, H30269 -> H20269, 930955 -> H20955, and 931446 -> 921446 for price-display code -> official total-return code. Do not infer `H21446`; the official factsheet and live endpoint identify `921446`.
- The S&P family displays official price-index code `SPCLLHCP`; `SPCLLHCT` is its official total-return identity but is not claimed as the fetched series.
- Tencent `sh515450` `qfq` closes are an ETF adjusted proxy. Responses use `return_type: adjusted_proxy`, source `tencent`, and a warning covering fees, tracking error, market-price effects, and listing-period coverage.
- The Tencent adapter fetches dated two-year windows with at most 640 observations each, validates the requested response key, deduplicates dates, and requires at least 200 valid positive closes.
- Missing PB or complete S&P valuation remains `unavailable` with an index-specific reason. ETF valuation and another index's history are forbidden substitutes.
- Catalog `code` is always the index code shown to the user; proxy symbols stay inside provider configuration and disclosure text.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| CSI price or total-return code returns no valid observations | Use complete cache if present; otherwise return `source_error` |
| Tencent response omits `data[symbol].qfqday` or returns another symbol | Raise `SourceError`; never cache the payload |
| Tencent adjusted history has fewer than 200 valid points | Raise `SourceError` and keep prior complete cache if available |
| Public PB history is absent for a new CSI index | Return PE/dividend data and an unavailable PB metric |
| S&P official index history is not configured | Use the disclosed ETF proxy for returns/DCA only; keep all valuation metrics unavailable |
| Adjusted ETF proxy is returned | Use `adjusted_proxy`, never `total_return` or `price_return` |

### 5. Good / Base / Bad Cases

- Good: a CSI index returns official PE, recent dividend yield, official total-return history, and public PB when available.
- Base: 930740, 930955, or 931446 has no public PB history; research is partial while returns and DCA remain ready.
- Base: the S&P index uses 515450 adjusted history from 2020 onward and visibly discloses proxy limitations.
- Bad: the UI displays 515450 as the index code or labels the adjusted ETF proxy as an official S&P total-return series.

### 6. Tests Required

- Catalog/API: assert all five IDs, exact display codes, CSI total-return codes, and `adjusted_proxy` for the S&P entry.
- Adapter: assert `qfq` window requests, close parsing, date deduplication, minimum history, and wrong-symbol rejection.
- Service: assert source `tencent`, adjusted-proxy warning, generic index-specific valuation unavailability, and successful returns/DCA.
- Live/browser: switch through all five selector values, verify partial fields remain actionable, run return/DCA requests, refresh a CSI and the proxy entry, and check the long S&P label at 390 px.

### 7. Wrong vs Correct

#### Wrong

```python
IndexDefinition(..., code="515450", return_type="total_return")
```

This replaces the index identity with a fund code and overstates a proxy as official index history.

#### Correct

```python
IndexDefinition(
    ..., code="SPCLLHCP", price_provider="tencent", price_code="sh515450",
    return_type="adjusted_proxy", return_label="515450 ETF 前复权日线代理",
)
```
