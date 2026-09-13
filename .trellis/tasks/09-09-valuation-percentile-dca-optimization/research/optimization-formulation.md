# Valuation-Percentile DCA Optimization Formulation

## Classification

With a fixed rule shape and only a percentile trigger to choose, this is a
constrained, simulation-based hyperparameter optimization problem on a time
series. The backtest objective is path-dependent and non-differentiable, so a
small deterministic grid search is more appropriate than gradient optimization.

If each period's investment amount becomes an independent decision variable,
the problem expands into constrained stochastic control. Adding discrete
trigger/on-off decisions and continuous contribution amounts makes it a
mixed-integer nonlinear optimization problem. That added complexity is not
needed for the MVP.

## Recommended Policy Shape

Use a continuous base DCA plus valuation-based acceleration:

- A fixed external budget arrives every month.
- A configured base fraction is invested every month, regardless of valuation.
- The remaining tactical fraction accumulates in a cash reserve.
- When the valuation percentile enters the cheap zone, the strategy deploys
  reserve subject to a per-month cap.
- Residual cash is included in terminal wealth so waiting is not hidden.

This preserves time diversification and makes the percentile threshold an
acceleration signal, not an all-in market-timing signal.

## Decision Variables

- `q`: valuation trigger percentile, tested on a small grid such as 5, 10, ...,
  50.
- `base_fraction`: share of each monthly budget always invested; recommended
  default 70% for the first experiment.
- `monthly_cap_multiple`: maximum total equity purchase in one month relative
  to the normal monthly budget; recommended default 2.0.

For an MVP that seeks one suitable percentile, optimize only `q` and hold the
other parameters fixed.

## Signal Direction

- PE and PB: cheaper when percentile is lower; trigger when `p_t <= q`.
- Dividend yield and either risk-premium metric: cheaper when percentile is
  higher; normalize to a common `cheapness_percentile` first, then use the same
  trigger contract.
- Every percentile must be computed using only observations available at time
  `t`; a full-history percentile introduces look-ahead bias.

## Recommended Objective and Constraints

Evaluate the strategy over many rolling start dates, not one chosen period.

Recommended objective:

`maximize median(out_of_sample_XIRR - plain_DCA_XIRR)`

Subject to:

- downside CVaR (worst 20% of excess XIRR samples) is not below a configured
  tolerance versus plain DCA;
- at least 24 complete rolling windows are available;
- the base monthly contribution is never skipped;
- equity deployment in one month does not exceed the cap;
- both strategies receive identical external cash flows and use the same
  start/end dates and return index;
- no future valuation observations participate in the signal or percentile.

If the primary user preference is capital preservation rather than balanced
improvement, maximize the 20th-percentile XIRR instead of median excess XIRR.

## Validation Protocol

- Use walk-forward evaluation: fit/select the threshold on the earlier segment,
  then score it on a later untouched segment.
- Report a plateau or stable range of thresholds rather than claiming the
  single best in-sample point is universal.
- Compare against plain monthly DCA with identical external cash flows.
- Report median, 20th percentile, worst result, CVaR, win rate versus baseline,
  contribution count, reserve cash, and maximum one-month deployment.
- Run the protocol separately per index and metric; do not pool incomparable
  PE, dividend-yield, or market histories.

## Existing Repo Fit

- `app/calculations.py` already has scheduled DCA, XIRR, period-end sampling,
  and return-summary primitives.
- The existing DCA assumes a fixed amount per execution and has no cash-reserve
  or valuation-signal model.
- The valuation service already emits month-end percentile histories, but an
  optimizer must recompute each historical percentile on an expanding window to
  avoid look-ahead bias.
