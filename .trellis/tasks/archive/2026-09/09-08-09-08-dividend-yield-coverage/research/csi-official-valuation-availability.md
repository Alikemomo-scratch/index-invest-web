# CSI Official Public Valuation Availability

## Question

Can the A-share index researcher use only CSI official data for current values
and 3/5/10-year valuation percentiles?

## Verified Public Endpoints

### Index performance history

- Endpoint: `https://www.csindex.com.cn/csindex-home/perf/index-perf`
- Example: index `930740`, 2016-01-01 through 2026-09-09.
- Result: 2,598 daily rows.
- Available valuation-like field: `peg`, whose current value tracks the index
  P/E and is already normalized by the adapter as `pe`.
- No D/P, dividend-yield, or PB field is present in the returned rows.

### Official indicator workbook

- Endpoint pattern:
  `https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/{code}indicator.xls`
- Verified workbook: `930740indicator.xls` on 2026-09-09.
- Result: 20 observations from 2026-08-13 through 2026-09-09.
- Columns: Date, identity fields, P/E1, P/E2, D/P1, and D/P2.
- Latest 930740 values: P/E1 9.05, P/E2 8.99, D/P1 4.31%, D/P2 4.61%.
- The workbook contains no PB column.

### Factsheet and methodology

- The public factsheet provides a current fundamentals snapshot and states that
  the displayed indicators use calculation share capital.
- The index methodology explains construction but does not provide a historical
  downloadable D/P or PB series.

## Product Decision

The user chose history coverage over an official-only restriction after seeing
the trade-off. Use the sources with explicit labels and no series splicing:

- PE: long public CSI history plus official current P/E2 override; Legulegu may
  be retained only as a disclosed cross-check or fallback when official PE is
  unavailable.
- Dividend yield: FundDB public aggregate history is the main series used for
  the displayed value and percentile. Mark its exact D/P methodology as
  unconfirmed and list official CSI D/P1 and D/P2 separately.
- PB: use the disclosed Legulegu public aggregate history when available.
- Dividend-yield premium: derive from the same FundDB dividend series used by
  the main card and the separately disclosed China 10-year government yield.

Never label FundDB history as official CSI D/P1 or D/P2, and never overwrite an
aggregate series' latest value with an official value from a different
methodology.
