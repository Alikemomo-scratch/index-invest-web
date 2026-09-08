# Technical Design

## Architecture

Use one local Python process:

```text
Remote source / imported CSV
  -> provider adapter
  -> market-specific provider chain
  -> validation + normalization
  -> SQLite raw/cache metadata + normalized series
  -> valuation percentile / holding-period return services
  -> FastAPI JSON endpoints
  -> selected Direction A static web UI
```

### Backend

* Python 3.9+ and FastAPI.
* `httpx` for bounded HTTP requests with explicit timeouts.
* Built-in `sqlite3` for JSON payload cache and source coverage metadata.
* Small parser dependency only where needed for official XLS files.
* Plain normalized dictionaries define the current MVP response contract; the code-spec records required fields and error behavior.
* Provider failures are isolated per source and returned as actionable availability states.
* Following the useful pattern in `daily_stock_analysis`, each market uses an explicit,
  deterministic provider chain instead of one global priority list. A successful payload
  records both the actual `source` and the highest-priority failed `fallback_from` source.
* A partial cache hit is never reported as a complete refresh. Responses expose requested
  range, actual range, freshness, and partial/stale flags.

### Provider chains

* A-share valuation: CSI official PE/dividend snapshot and PE history -> Legulegu PE/PB
  history -> stale local cache. Official and aggregated observations are compared where
  definitions overlap.
* A-share returns: CSI total-return index -> CSI price index with an explicit price-return
  warning -> stale local cache.
* S&P 500 valuation: Multpl public historical tables, whose page discloses S&P/Shiller as
  underlying sources -> stale local cache. Estimated observations stay marked estimated.
* U.S. returns: Yahoo Finance public chart for total-return symbols where available -> price
  index symbol -> stale local cache.
* A provider returning non-empty but truncated history is treated as partial and cannot
  overwrite a more complete cache snapshot.

### Frontend

* Productionize the approved Direction A using semantic HTML, CSS, and modular vanilla JavaScript.
* No chart framework initially; use accessible SVG charts to keep the local bundle small.
* All controls read from API responses; no illustrative market values remain in production code.
* Loading, stale, partial, unavailable, and source-mismatch states are first-class UI states.

## Proposed modules

```text
app/
  main.py          # FastAPI routes and local static serving
  catalog.py       # supported indices and fixed provider chains
  sources.py       # CSI, Legulegu, Multpl, and Yahoo adapters
  cache.py         # SQLite JSON cache and coverage metadata
  calculations.py  # percentile and holding-period calculations
  service.py       # provider fallback and response assembly
static/
  index.html
  styles.css
  app.js
tests/
  test_api.py
  test_cache_and_catalog.py
  test_calculations.py
  test_service.py
  test_sources.py
data/
  index-invest.sqlite3  # runtime, ignored
```

## API

* `GET /api/health`
* `GET /api/indices`
* `GET /api/indices/{index_id}/research?lookback_years=10`
* `GET /api/indices/{index_id}/returns?frequency=monthly|quarterly|semiannual&holding_years=1|3|5|10&measure=annualized|cumulative`
* `POST /api/refresh/{index_id}`

## Error semantics

* `unavailable`: no configured source can provide the field.
* `stale`: latest observation is older than the source-specific freshness threshold.
* `insufficient_history`: fewer than 36 valid monthly valuation observations or no complete holding windows.
* `source_mismatch`: official cross-check exceeds the configured tolerance.
* `source_error`: upstream timeout, invalid response, or parser failure; cached values may be returned only with a stale flag.
* `partial`: the source returned usable data but did not cover the requested range.

## Testing

* Unit tests for percentile inclusion/exclusion and every holding frequency/year combination.
* Fixture-based provider parser tests; tests never depend on live network availability.
* API contract tests for healthy, partial, stale, and unavailable states.
* Browser smoke test for index switching, valuation metric switching, frequency switching, and holding-year switching.

## Security and privacy

* Bind to `127.0.0.1` by default.
* No broker connection, telemetry, or remote user account.
* MVP uses credential-free public sources and does not return internal provider routing codes to the browser.
