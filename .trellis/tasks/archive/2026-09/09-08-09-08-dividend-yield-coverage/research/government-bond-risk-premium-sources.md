# Government-Bond Risk-Premium Source Decision

## Formula contract

- Earnings-yield premium: `100 / PE TTM - 10Y government bond yield`.
- Dividend-yield premium: `index dividend yield - 10Y government bond yield`.
- All terms are percentage points. Components must be aligned to the same
  calendar month before subtraction.
- Mainland indices use China's 10-year government bond yield. US indices use
  the US 10-year Treasury yield.

## Historical source

Use Eastmoney's public `RPTA_WEB_TREASURYYIELD` dataset through a small local
adapter. The upstream dataset provides China and US 10-year yields in one dated
response and supports 500-row pagination. The fields used are:

- `SOLAR_DATE`: observation date.
- `EMM00166466`: China 10-year government bond yield.
- `EMG00001310`: US 10-year Treasury yield.

AKShare's maintained `bond_zh_us_rate` implementation documents and consumes the
same endpoint and fields, which provides an independent parser reference without
adding AKShare or pandas as runtime dependencies.

## Official checks and disclosure

- ChinaBond's Ministry of Finance government-bond curve is the official current
  reference. The current 10-year value was consistent with Eastmoney on the
  observation checked on 2026-09-08 after normal display rounding.
- FRED series DGS10 is the official US Federal Reserve H.15 reference for the US
  10-year Treasury constant-maturity rate.
- The historical risk-premium response must label Eastmoney as a public
  aggregate source and must not relabel it as official ChinaBond or FRED data.

## Join and failure semantics

- Resample every component independently to the last valid observation in each
  calendar month.
- Inner-join only common `YYYY-MM` keys. Use the equity metric's observation date
  as the output point date and retain component dates and values for audit.
- Reject zero/negative PE before inversion. Preserve zero/negative calculated
  premiums because a negative spread is economically valid.
- If common-month overlap is below the existing minimum-sample contract, return
  an actionable insufficient-history status rather than filling or fabricating
  observations.
