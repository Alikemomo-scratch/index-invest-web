# DCA scheduling extension

## Decision

- The user selects an explicit inclusive `start_date` and `end_date`.
- `cadence=monthly` uses `schedule_value=1..31` as the desired calendar day.
- `cadence=weekly` uses `schedule_value=1..7` where Monday is 1 and Sunday is 7.
- A planned date executes on the first real market observation on or after that date. An execution after `end_date` is excluded.
- A monthly day beyond the calendar length is clamped to that month's final calendar day before trading-day adjustment.
- Multiple planned dates mapped to one observation are deduplicated.
- Terminal value uses the last observation on or before `end_date`, and the curve includes a terminal valuation point when it differs from the final contribution date.
- Every contribution retains `scheduled_date` and `execution_date`; the response reports `adjusted_count`.

## Data-resolution guard

Date- and weekday-specific simulation requires daily observations. Yahoo requests use `interval=1d` and a versioned daily cache key. A source series whose typical observation gaps exceed daily-market cadence is rejected for scheduled DCA rather than silently treating monthly values as exact trading dates.

## Compatibility

The API keeps `years` as an optional legacy/default window when explicit dates are absent. The production UI sends explicit dates, cadence, and schedule value.
