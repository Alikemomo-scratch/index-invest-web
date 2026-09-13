# Index Earnings Growth Options

## Goal

Identify one defensible metric that tracks the earnings growth of the companies
represented by each supported index without confusing market-price changes with
profit growth.

## Verified Source Facts

- CSI's public performance endpoint returns matched daily index `close` and a
  valuation field currently normalized by this project as trailing P/E. It does
  not return a direct EPS field.
- For the nine CSI/SSE indices currently in the catalog, matched price and P/E
  history is sufficient to derive an index earnings level. Coverage starts
  between 2011-06-28 and 2020-04-07, depending on the index.
- The existing Multpl source has a separate S&P 500 earnings table with monthly
  observations. It is a public aggregate source, not an official S&P DJI feed.
- The current free-source routes do not provide reliable historical P/E or EPS
  for Nasdaq-100 or S&P China A Large Cap Dividend Low Volatility 50.

## Comparable Measurement Patterns

### A. Implied trailing index EPS growth (recommended MVP)

- Earnings level: `price_index_close / trailing_pe`.
- Growth: compare completed month-end earnings level with the same month one year
  earlier.
- Tracks the earnings power of the index as an investable portfolio.
- Includes constituent rebalancing and weighting changes, so it is not a
  constant-company-cohort organic growth measure.
- Uses no constituent-level financial statement ingestion and fits the current
  source architecture.

### B. Bottom-up aggregate net-profit growth

- Persist each rebalance's constituent set, fetch company TTM profits, apply the
  index weighting/free-float methodology, and aggregate.
- Can support attribution by company and sector, but requires point-in-time
  constituents, corporate-action handling, accounting-period alignment, and a
  licensed or substantially more complex fundamentals source.
- A naive implementation creates survivorship bias and cannot be treated as the
  official index earnings series.

### C. Forward consensus EPS growth

- Aggregate analyst earnings forecasts for the index constituents.
- Leads reported earnings and can track expectation revisions.
- Requires forecast coverage and usually a paid source such as Wind/Bloomberg;
  it has analyst-coverage and revision biases.

## Sample Verification

Using CSI's matched price/P/E rows for CSI 300 Dividend Low Volatility and only
completed month ends:

- 2026-08-31 implied trailing EPS level: 779.65 index points.
- 2025-08-29 implied trailing EPS level: 826.83 index points.
- Year-over-year implied trailing EPS growth: -5.71%.

This is a calculation example, not an official CSI-published EPS value.

## Recommended Contract

- User-facing name: `指数盈利增长（隐含 EPS TTM 同比）`.
- Primary value: completed-month year-over-year percentage.
- Supporting chart: implied EPS TTM level plus its year-over-year growth.
- Use the price index, never the total-return index, in the numerator.
- Price and P/E must share the same index identity, observation date, and source
  methodology; do not apply a latest-value override from a different P/E series.
- Missing or non-positive P/E makes that observation unavailable.
- Label the result `official_derived` for matched CSI official inputs and
  `aggregated_derived` for public aggregate inputs.
- Disclose that rebalances and weighting changes contribute to measured growth.

## Sources

- CSI public performance endpoint:
  `https://www.csindex.com.cn/csindex-home/perf/index-perf`
- Multpl S&P 500 earnings table:
  `https://www.multpl.com/s-p-500-earnings/table/by-month`
