# Verification Record

Date: 2026-09-08

## Automated checks

- Python compile check: passed for `app`, `tests`, and `run.py`.
- Unit, API, adapter, and frontend contract tests: 29 passed.
- Dependency consistency: `pip check` reported no broken requirements.
- Frontend syntax: `node --check static/app.js` passed.
- Return matrix: 48 representative combinations passed for CSI 300 and S&P 500 across monthly/quarterly/semiannual sampling, 1/3/5/10-year holding periods, and annualized/cumulative measures.

## Browser smoke checks

- CSI 300 loaded real valuation and return data from the local API.
- S&P 500 loaded real valuation data and switched to monthly, 10-year, cumulative return results.
- Source mismatch and insufficient-history explanations remained visible and actionable.
- At 390 px viewport width, document width stayed within the viewport with no horizontal overflow.
- The normal viewport was restored and the app was returned to the default CSI 300 view.
- PE and PB chart interaction displayed the nearest point's value and date with both guide lines visible.
- Manual refresh preserved a non-default 5-year lookback, monthly sampling, 1-year holding period, and cumulative-return selection.
- The refresh request included every active query option and completed with fresh data through 2026-09-07.
- The return panel displayed the latest market date separately from the latest complete holding-period sample window.
- S&P 500 valuation display changed from monthly to yearly (120 to 11 plotted observations) while PE percentile stayed at 69.2% with 120 month-end percentile samples. Daily mode did not synthesize observations beyond the monthly source coverage.
- The built-in Futu sample returned 26.12 vs Multpl 26.36 on 2026-09-04, a 0.92% difference, `consistent` numerical status, `estimated` observed evidence, and unknown methodology.
- S&P 500 5-year monthly DCA with USD 2,000 produced 60 contributions, USD 120,000 invested, USD 188,207 ending value, and 18.6% XIRR using the current cached total-return series.
- At the 390 px test viewport the DCA and validation panels were 351 px wide and document horizontal overflow was false.
- DCA service matrix passed for CSI 300 and S&P 500 at 3/5/10/15/20 years; the valuation frequency matrix returned daily/monthly/quarterly/yearly point counts of 121/120/40/11 while retaining the same 69.2% PE percentile and 120 month-end percentile samples.
- Manual refresh forwarded `history_frequency=monthly`, `dca_years=5`, and `monthly_amount=2000` together with the active return controls; the response kept every visible selection and had no error notice.
- Scheduled DCA unit tests cover explicit ranges, monthly calendar-day selection, weekly weekday selection, weekend adjustment, invalid ranges, invalid weekday values, and rejection of monthly-only data for day-specific scheduling.
- Real-data matrix passed for CSI 300 and S&P 500 across monthly day 3/day 31 and weekly Monday/Sunday. Every combination returned `ready` with auditable adjustment counts.
- S&P 500 total-return cache now contains 9,237 daily observations from 1990-01-02 through 2026-09-04; maximum adjacent calendar gap is seven days.
- Browser smoke used S&P 500, 2024-01-01 through 2024-03-31, every Sunday: 12 contributions, all 12 shifted to real trading days, one final plan skipped because its next trading day exceeded the selected end, and terminal valuation on 2024-03-28.
- A source-gap regression proves plans are skipped after 14 days instead of being falsely shifted across missing months. A weekend end date uses the preceding market observation without being mislabeled as source-range clipping.
- The new date/cadence/schedule controls remained within a 375 px document viewport with no horizontal overflow.
- The holding-return panel rendered a 69-point SVG line with no bar container; the zero-return line and current-sample marker remained visible.
- Selecting the holding-return chart displayed return value, buy date, end date, vertical guide, horizontal guide, and point marker; leaving the chart hid every hover artifact.
- At the 390 px test viewport, the return chart was 309 px wide, the document had no horizontal overflow, and the tooltip stayed inside the viewport.
- The selector exposed all four new official identities: 930740, H30269, 930955, and SPCLLHCP; it contained 11 total indices.
- Live CSI research returned current PE and dividend yield through 2026-09-08 for all three new CSI indices. H30269 also returned 261 PB observations; 930740 and 930955 kept PB explicitly unavailable.
- Live five-year monthly holding-return requests returned 203, 190, and 190 complete total-return samples for 930740/H20740, H30269/H20269, and 930955/H20955 respectively.
- The SPCLLHCP entry returned 20 five-year monthly samples through 2026-09-08 from the 515450 Tencent `qfq` proxy, with `return_type: adjusted_proxy` and the full fee/tracking/listing-history warning.
- Monthly-day-15 DCA over 2021-01-01 through 2026-09-08 returned `ready` for all four additions with 68 contributions each. Sources were CSI official for the three CSI entries and Tencent for the S&P proxy.
- Manual refresh returned research `partial`, returns `ready`, and DCA `ready` for both a representative new CSI entry and the S&P proxy while preserving each source/return-type disclosure.
- Browser switching rendered the available and unavailable valuation fields, return sample count, DCA result, source label, and proxy warning for every new index. The longest S&P label stayed within a 375 px document viewport without horizontal overflow.
- The catalog now exposes 12 total indices and renders `东证红利低波 · 931446 · A 股` as `csi_dfh_div_low_vol` in the browser selector.
- The official CSI price endpoint returned 931446 observations through 2026-09-08, while the official factsheet and live endpoint confirmed 921446—not inferred H21446—as the total-return identity.
- A forced refresh returned current official PE 8.36 and dividend yield 4.22% through 2026-09-08. Public PB remained explicitly unavailable; it was not substituted from another series.
- One-year monthly annualized holding-return research on 921446 returned 190 complete samples, an 11.33% median, and official `total_return` disclosure.
- Weekly-Wednesday DCA over 2021-01-01 through 2026-09-08 returned 294 contributions, 17 shifted executions, CNY 294,000 invested, CNY 405,169.20 ending value, and 11.3% XIRR.
- Browser switching showed the same PE/dividend/PB states, 190-sample one-year annualized return line, and weekly-Wednesday DCA result with the official 921446 return label.
- Holding-return summary now exposes the arithmetic `average` of all complete samples alongside the median; unit coverage asserts non-empty, empty, and mean-versus-median cases.
- For 931446/921446 with monthly buy anchors and one-year holding, the API returned average annualized return 14.42% and average cumulative return 14.38% across the same 190 complete samples.
- Browser smoke rendered `年化收益平均值 14.4%`, switched the label to `累计收益平均值`, and restored the annualized view. Versioned JS/CSS URLs prevented stale assets from leaving the new card empty.

## Closeout boundary

The workspace root is not a Git repository. No work commit, task archive commit, or session journal commit was created. The Trellis task remains `in_progress` even though its implementation acceptance criteria are satisfied.
