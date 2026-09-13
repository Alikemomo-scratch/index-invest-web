# Complete Index Dividend-Yield Coverage And Risk Premium Percentiles

## Context

The index researcher already exposes an index-level dividend-yield metric, but
CSI workbooks currently contribute only a short recent series. That is not
enough for a useful 3/5/10-year percentile, especially for dividend-focused
indices. The selected product trade-off is to use a clearly labeled public
aggregate history for percentiles while preserving official CSI D/P1 and D/P2
as separate comparison values.

## Scope

- Add index-level dividend-yield history for every supported CSI/SSE index for
  which the public aggregate source returns a valid series.
- Treat dividend-focused indices as first-class: show the available date range,
  month-end sample count, missing months inside that range, and requested-range
  shortfall.
- Parse and disclose both official CSI workbook definitions:
  - D/P1: total-share-capital denominator.
  - D/P2: calculation-share denominator.
- Keep the history source and official comparison values distinct. Do not imply
  that a public aggregate history is an official D/P1 or D/P2 series when its
  methodology is not published.
- Preserve current cache/fallback behavior and reject malformed or implausibly
  short upstream responses.
- Add two index-level risk-premium series and 3/5/10-year percentiles:
  - Earnings-yield premium = `100 / PE TTM - 10Y government bond yield`.
  - Dividend-yield premium = `index dividend yield - 10Y government bond yield`.
- Use China 10-year government bond yield for mainland indices and US 10-year
  Treasury yield for US indices. Align components by calendar month and never
  mix observations from different months.

## Explicit Non-goals

- Constituent-level cash-dividend records.
- Payout ratios, consecutive dividend years, ex-dividend dates, or dividend
  forecasts for individual stocks.
- Fabricating long history for an index whose public source has no series.
- Treating `PE - government bond yield` as a meaningful spread; PE must first
  be inverted into an earnings yield.
- Constituent-weighted or forecast earnings-risk-premium models.
- Claiming that the aggregate dividend series uses CSI D/P1 or D/P2 methodology.

## Requirements

1. The eight supported CSI/SSE indices with verified public history expose a
   dividend-yield history suitable for 3/5/10-year month-end percentiles when
   the requested period is covered.
2. An index without public history (currently 931446) still exposes the latest
   official D/P1 and D/P2 values and an actionable coverage explanation.
3. Every dividend-yield response contains a coverage audit with first/last
   date, raw-point count, valid month count, missing months within the observed
   range, requested start date, and whether the requested range is clipped.
4. The main historical metric uses one internally consistent public aggregate
   series. Official D/P1 and D/P2 values are shown as comparisons, not spliced
   into that history.
5. Source, tier, update date, cache freshness, and methodology status remain
   visible in the API and interface.
6. Existing PE, PB, return, DCA, and validation behavior remains compatible.
7. Risk-premium metrics retain valid zero or negative observations when
   calculating samples and percentiles; the positive-only validation used by
   PE, PB, dividend yield, and prices remains unchanged.
8. Risk-premium history uses month-end observations from the same calendar
   month, discloses its component formula and sources, and reports the same
   coverage/freshness semantics as other historical metrics.
9. A higher risk-premium percentile is presented as relatively cheaper; no
   investment conclusion is inferred from the percentile alone.

## Acceptance Criteria

- `csi300`, `csi500`, `csi1000`, `sse50`, `sse_dividend`,
  `csi300_div_low_vol`, `csi_div_low_vol`, and `csi_div_low_vol_100` can
  return public dividend-yield history through a deterministic catalog mapping.
- `csi_dfh_div_low_vol` reports official current D/P1/D/P2 plus the absence of
  public long history; it does not claim a percentile.
- CSI workbook parsing retains both D/P1 and D/P2 and keeps the existing aliases
  used by PE/dividend callers.
- The UI shows aggregate-history methodology status, official D/P1/D/P2
  comparisons, and coverage text when the active metric is dividend yield.
- Unit tests cover provider parsing/signing, workbook column preservation,
  coverage auditing, successful dividend history, and current-only fallback.
- Unit tests cover government-bond parsing, calendar-month joins, both formulas,
  negative risk-premium observations, insufficient overlap, and dynamic overall
  research status with the expanded metric set.
- The UI shows both risk-premium cards, formulas, bond-market mapping, units,
  component sources, sample counts, and 3/5/10-year percentile status.
- Relevant tests and syntax checks pass.
