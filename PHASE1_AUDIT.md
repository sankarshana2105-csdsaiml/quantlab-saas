# Phase 1 mathematical audit — 2026-09-11

**Final verdict: PASS.** The initial audit failed; all A01–A12 findings were corrected and independently reverified on 2026-09-11. Phase 1 now has zero unresolved High findings and zero known failing assertions.

Scope: all four engine modules, all tests, the example generator, saved CSV/metrics, and saved plot. Findings below preserve the original diagnosis and record the implemented resolution.

## Evidence and reproducibility

The corrected suite passes 53 tests. `tests/test_phase1_audit.py` contains ordinary passing regression tests with no expected failures. It independently implements the sample cash/share ledger using scalar arithmetic; all saved metrics, every equity point, and all four completed-trade PnLs reconcile within `1e-12` absolute tolerance.

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=D:\QuantLab\.pytest_cache\audit-temp
.\.venv\Scripts\python.exe -m tests.test_phase1_audit
```

The last command independently recomputes the corrected sample with Python scalar arithmetic. CSV content matches the seed-7 generator. The regenerated PNG was visually inspected: its cash plateaus, final equity around $8,136, and roughly -24.1% drawdown agree with the ledger.

For comparison, the independent executable ledger consumes each signal at the next open, holds shares until exit, buys with cash inclusive of commission, shifts buy/sell fill prices adversely by 2 bps, and charges 5 bps on filled notional. It allows fractional shares, assumes fills are possible, and does not force a last-bar sale. The sample ends flat. This is an explicitly specified comparison model, not a universal ground truth or an implementation fix.

| Sample quantity | Failed pre-audit model | Corrected engine and independent ledger |
| --- | ---: | ---: |
| Total return | -19.118833% | -18.641609% |
| Period-based annualized return (252) | -6.837360% | -6.654248% |
| Annualized volatility | 10.241281% | 10.202340% |
| Sharpe | -0.640342 | -0.623934 |
| Sortino | -0.887466 | -0.865040 |
| Maximum drawdown | -24.387259% | -24.095118% |

The correction changes total return by approximately 0.477224 percentage points in this sample; the bias need not always favor the strategy. Both ledgers now report four completed trades with net PnL of approximately -$493.69, -$1,239.66, -$314.09, and +$183.28: trade win rate 25% and trade profit factor 0.089516.

## Findings

The “why” and “evidence” bullets preserve the failed implementation’s behavior. Current resolution status is authoritative in each heading. The implemented corrections are summarized here:

| Findings | Resolution |
| --- | --- |
| A01–A03 | One next-open cash/share ledger now owns overnight moves correctly, keeps quantity fixed, and applies commission to filled notional plus adverse-price slippage. |
| A04 | Completed trades carry net PnL; win rate, profit factor, and trade count use that ledger. |
| A05 | Evaluation calls custom strategies once per available prefix, so later observations cannot change earlier decisions. |
| A06–A07 | Walk-forward selection uses rolling train windows, while one fresh-cash OOS account executes continuously through every complete or partial test fold. |
| A08–A10 | Warm-up and sample-size checks, a strict weekday frequency contract, conflicting-duplicate rejection, calendar CAGR, and derived finite-value checks now fail explicitly. |
| A11–A12 | The optimizer minimizes volatility/turnover; metrics now include completed trade count and interval exposure. |

### A01 — High — RESOLVED — Close signal versus executable fill

- **Location:** `quantlab/backtest.py:85–91`, `run_backtest`; `tests/test_backtest.py:24`, timing test.
- **Why incorrect:** `signal.shift(1) * close.pct_change()` applies the signal from close t to the entire interval close t → close t+1. It implicitly buys at close t, after using that close to decide. No next-open or next-close fill is modeled; `open` is ignored. Shifting the array alone does not implement the promised next-bar execution.
- **Evidence:** closes/opens 100 → 120 → 120 produce +20% for a new long, although buying at the next open of 120 earns zero. On exit, closes/opens 100 → 100 → 80 produce zero rather than the -20% overnight loss still owned before selling at 80. The old timing test explicitly expects the impossible entry gain when open equals close.
- **Expected:** old holdings own overnight movement; a new position owns movement only after its fill. An order generated at a completed close cannot fill retrospectively at that close without a separately justified execution model. Next-open market execution is a standard convention described in [Backtrader's execution documentation](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/).
- **Minimal fix:** choose and document next-open execution; mark old shares at the new open, execute the previous signal, then mark at close. Alternatively use next-close fills with the additional delay and correspondingly aligned returns. Replace the old timing assertion.
- **Tests:** `test_entry_does_not_earn_the_gap_before_next_open`, `test_exit_still_owns_the_gap_until_next_open`.

### A02 — High — RESOLVED — Short compounding and holdings

- **Location:** `quantlab/backtest.py:86–94`, `run_backtest`.
- **Why incorrect:** a constant -1 position is treated as -100% of the new equity on every bar. That requires changing short quantity as price and equity change. Turnover, however, records only changes in the target sign. Thus the engine is neither a fixed-share position ledger nor a correctly costed rebalanced-weight portfolio.
- **Evidence:** short one share at 100 with $100 initial equity; price 100 → 90 → 100 has zero gross PnL when shares are held. The engine finishes at $97.777778 while recording no intermediate rebalance. This value is mathematically possible for a rebalanced short, but its required transactions are absent from the ledger and costs.
- **Expected:** either fixed quantity until a signal change, or explicit target-weight rebalances with actual traded notional.
- **Minimal fix:** retain cash and share quantity, derive equity and turnover from fills. If daily target-weight rebalancing is intended instead, calculate the drifted pre-trade weight and trade to the new target, including costs.
- **Test:** `test_unchanged_short_quantity_round_trip_price_has_zero_pnl` selects the fixed-share contract; an explicit rebalanced contract instead needs an independent turnover/notional oracle.

### A03 — High — RESOLVED — Cash, notional, commission, and slippage

- **Location:** `quantlab/backtest.py:88–94`, `run_backtest`.
- **Why incorrect:** `abs(position.diff()) * rate` deducts a fraction of prior equity without reserving purchase cash or calculating filled notional. Commission and slippage are merged as additive bps, so there is no adverse fill price or commission/slippage interaction. This is a useful first-order approximation only if declared as such; the current output is presented as correctly costed trading. The solvency check runs after the full bar gain and can mask impossible spending at execution.
- **Evidence:** $1,000, open 100, close 110, 1% commission gives $1,090 in the engine. Cash-funded shares are `1000 / (100 * 1.01)`, giving $1,089.108911. With 200% costs and a later 300% gain the engine still accepts the trade: a future gain funds an earlier fee in its arithmetic.
- **Expected:** budget fees at execution, debit commission on actual notional, apply slippage in the adverse direction. Reject infeasible costs/exposure before earning later returns, or size down under an explicit model.
- **Minimal fix:** calculate quantity, fill price, and fee together; use the same ledger for long, short, exit, and reversal. A linear bps approximation must be labeled and bounded if deliberately retained.
- **Tests:** `test_entry_commission_reserves_cash_before_buying_shares`, `test_entry_cost_cannot_consume_more_than_available_capital`. The latter chooses rejection; safe cash-funded resizing is another acceptable explicit contract. `test_reversal_cost_counts_two_sides_at_flat_prices` confirms the existing approximation does count +1 → -1 as two sides, with no commission double-counting on that fixture.

### A04 — High — RESOLVED — Completed-trade statistics

- **Location:** `quantlab/backtest.py:39–42,54–55`, `_metrics`.
- **Why incorrect:** win rate counts positive nonzero return bars, and profit factor divides sums of positive/negative percentage returns. Neither is the win rate or PnL-based profit factor of completed trades. Percentages also ignore changing capital. The sample explicitly labels win rate as period-based, which is valid, but the public metric names and profit-factor description do not communicate this distinction.
- **Evidence:** one completed profitable trade through prices 100 → 110 → 99 → 108.9 reports win rate 2/3 and profit factor 2, although there is one winning trade and no losing trade. Standard closed-trade statistics use a trade collection, as in [QuantConnect's statistics contract](https://www.quantconnect.com/docs/v2/cloud-platform/api-reference/backtest-management/read-backtest/backtest-statistics).
- **Expected:** trade win rate = winning completed trades / completed trades; profit factor = gross winning net trade PnL / absolute losing net trade PnL, with a declared zero-loss convention.
- **Minimal fix:** either rename these to `winning_period_rate` and `period_return_profit_factor`, or derive the conventional names from a minimal fill/trade ledger. Document breakeven trades and how entry/exit fees and reversals are allocated.
- **Tests:** `test_one_completed_winning_trade_has_trade_win_rate_one`, `test_one_completed_winning_trade_has_no_losing_trade_denominator`.

### A05 — High — RESOLVED — Causal custom-strategy evaluation

- **Location:** `quantlab/evaluation.py:44,78,82–83`, `train_test_evaluate` and `walk_forward_evaluate`; `quantlab/backtest.py:79–86` only checks alignment and values.
- **Why incorrect:** callbacks receive the entire test period when producing test signals. A full-sample mean/normalization, centered rolling feature, backfill, or negative shift can therefore see later test rows. A final one-bar shift cannot remove this leakage. This is a missing safeguard for arbitrary callbacks, not evidence that the supplied moving average leaks.
- **Evidence:** a callback comparing close to the full-frame mean changes earlier test positions when only the last test close is changed. The engine accepts both outputs as valid.
- **Expected:** earlier decisions must be invariant to future-row mutations. Fitted transforms must be learned only from the eligible training prefix.
- **Minimal fix:** restrict the current public evaluation surface to vetted causal strategies and add prefix-invariance tests. For arbitrary callbacks, evaluate only data available at each decision timestamp, or implement a clear train-fit/frozen-transform contract before claiming leakage protection.
- **Tests:** `test_future_test_mutation_cannot_change_earlier_test_position`; `test_builtin_strategy_is_prefix_invariant_at_every_timestamp` passes for the built-in strategy.

### A06 — High — RESOLVED — Continuous walk-forward account

- **Location:** `quantlab/evaluation.py:17–18,81–89`, `_window_result` and `walk_forward_evaluate`.
- **Why incorrect:** each selected parameter set is simulated backward through its training period, then its test slice is rebased to fresh initial capital. Its hypothetical training position is treated as already held. The initial OOS purchase can be free; later folds do not carry the previous live position, so parameter changes can reverse exposure without paying for the reversal. Training-only parameter selection does not justify retroactive execution.
- **Evidence:** a flat-price always-long first fold with 100 bps commission reports 0% OOS return. A two-fold example selects long then short; the second flat-price fold also reports 0% despite the required reversal.
- **Expected:** indicators may inherit past observations, but the investable OOS account starts with explicit cash/holdings and carries them chronologically. Selection occurs after the last training observation; execution follows A01.
- **Minimal fix:** stitch only OOS decisions in timestamp order, execute one continuous OOS account, and then summarize each fold. For isolated folds, reset cash/positions explicitly and pay new entries. Preserve or close positions under a documented boundary policy.
- **Tests:** `test_walk_forward_cold_start_pays_entry_cost`, `test_walk_forward_parameter_switch_pays_reversal`.
- **Train/test nuance:** slicing a fixed strategy's continuously running account is legitimate conditional performance. `train_test_evaluate` needs to label that meaning; its test slice is not a fresh cash-funded backtest.

### A07 — Medium — RESOLVED — OOS coverage and aggregation

- **Location:** `quantlab/evaluation.py:74–76,90–101`, `walk_forward_evaluate`.
- **Why incorrect/incomplete:** only full test blocks are evaluated; trailing rows silently disappear. Insufficient input returns an empty DataFrame with no schema or reason. The return object has only fold summaries, no concatenated OOS signals, per-bar returns, or equity, so an aggregate path and boundary accounting cannot be validated from the public output.
- **Evidence:** 9 rows, train=4/test=2 omit the final row; 3 rows return an apparent successful empty result. Complete blocks themselves are adjacent and disjoint, which passes an independent index check.
- **Expected:** every eligible OOS timestamp is scored once, or explicitly listed as excluded. No evaluable folds must be reported clearly. Return a continuous OOS path before presenting aggregate performance.
- **Minimal fix:** handle the partial tail or report dropped dates, raise a descriptive no-fold error, and retain the chronological OOS frame used by A06. Aggregate returns by compounding, never by averaging fold CAGRs/Sharpes.
- **Tests:** `test_walk_forward_scores_or_explicitly_accounts_for_tail`, `test_walk_forward_rejects_no_evaluable_folds`, `test_complete_walk_forward_test_windows_are_adjacent_and_disjoint`. Add a stitched-account equivalence test during the fix; that output does not exist yet.

### A08 — Medium — RESOLVED — Insufficient observations and warm-up

- **Location:** `quantlab/backtest.py:24–31`; `quantlab/strategies.py:10–12`; `quantlab/evaluation.py:38–40,67–81`.
- **Why incorrect:** one return has no sample variance estimate, but is assigned zero volatility and signed-infinite Sharpe. A single-price backtest also produces seemingly valid zero metrics. Separately, a slow moving average longer than the whole training window creates all-cash signals without indicating the strategy was never ready. Walk-forward can rank these alongside actually evaluated candidates.
- **Expected:** distinguish insufficient observations, unready indicators, and a valid fully observed strategy that chooses no trades. An observed constant return series may use a documented infinity convention; one observation is not evidence of zero variance.
- **Minimal fix:** use undefined/status values for statistics with too few observations and exclude those from parameter ranking. Require enough training history for each strategy's warm-up plus evaluable execution periods.
- **Tests:** `test_one_return_does_not_get_infinite_sharpe`, `test_insufficient_strategy_history_is_reported`. Existing constant-return tests remain valid for the separately declared convention.

### A09 — Medium — RESOLVED — Input frequency and duplicate policy

- **Location:** `quantlab/data.py:21–29,60`; `quantlab/backtest.py:17–24,87`.
- **Why incorrect:** CSV loading automatically drops invalid bars (even for missing volume), then all remaining adjacent rows are treated as equal daily intervals. A multi-session price change becomes one daily return, indicator horizons contract, and volatility/annualized return use the wrong observation clock. Timestamp ordering alone cannot establish sampling frequency.
- **Evidence:** three consecutive business-day prices 100, 110, 121 with the middle volume missing become 100, 121 and one 21% return. The default annualizer raises 1.21 to 252 instead of recognizing the two-session span.
- **Expected:** preserve declared market frequency/session semantics and disclose dropped/corrected rows. Period-based annualization assumes genuine equal periods; calendar CAGR is a separate elapsed-time calculation.
- **Minimal fix:** make invalid-row removal explicit and auditable; validate against a declared frequency/calendar or reject unresolved gaps. Do not repair this by blindly forward-filling prices. A minimal daily research version can require complete input under its documented calendar.
- **Test:** `test_cleaned_missing_periods_do_not_silently_get_daily_annualization` chooses strict rejection; explicitly resampling under a tested calendar is another valid remedy.
- **Duplicates:** raw duplicate timestamps are rejected by validation, but cleaning silently keeps one conflicting row. Require an explicit stable correction policy or reject conflicts; do not claim point-in-time data integrity merely because duplicates disappeared.

### A10 — Medium — RESOLVED — Derived finite-value validation

- **Location:** `quantlab/backtest.py:87–95`, `_metrics` at lines 18–45.
- **Why incorrect:** finite positive input prices can overflow when divided or compounded. The solvency test `return <= -1` does not catch NaN or positive infinity. Pandas reductions can then skip NaNs, yielding an apparently valid total return alongside nonfinite equity.
- **Evidence:** finite prices 1e-300 → 1e300 with a cash signal produce invalid derived arithmetic without a ValueError.
- **Expected:** a result must contain finite per-period returns and equity, or fail explicitly. Intentionally undefined/infinite risk ratios are separate from invalid equity arithmetic.
- **Minimal fix:** validate derived asset returns, cost rates, net returns, and equity under explicit floating-point error handling; avoid silently reducing NaNs. Guard annualization overflow separately as well.
- **Test:** `test_derived_nonfinite_returns_are_rejected`.

### A11 — Medium — RESOLVED — Optimization direction

- **Location:** `quantlab/evaluation.py:63,81`, `walk_forward_evaluate`.
- **Why incorrect:** every `score` key uses `max`, including volatility and turnover. Choosing `score="volatility"` selects the riskiest candidate. Negative signed drawdown, total return, and Sharpe are appropriately higher-is-better; the keys do not share one direction.
- **Expected:** an explicit maximize/minimize objective or a validated restricted set of maximizing scores.
- **Minimal fix:** initially allow only supported higher-is-better scores, or add an objective direction. Validate invalid/nonfinite scores instead of letting them silently win or tie.
- **Test:** `test_volatility_selection_prefers_lower_risk`; rejection of unsupported volatility optimization is also an acceptable contract.

### A12 — Low — RESOLVED — Trade count and exposure

- **Location:** `quantlab/backtest.py:46–57`, `_metrics` return contract.
- **Why incomplete:** turnover is not trade count; winning periods are not trades. Neither exposure nor completed trade count is returned, despite being requested audit outputs. This is a coverage gap, not an incorrect existing formula.
- **Expected:** explicit completed-trade count and a defined exposure measure, such as the fraction of valid return intervals with a nonzero position; distinguish gross notional exposure where needed.
- **Minimal fix:** derive trade count from the ledger introduced for A04 and exposure from the chosen execution timeline. State whether open terminal positions count as completed (normally they do not).
- **Test:** `test_trade_count_and_exposure_are_available` uses one completed flat-price trade and 1/3 interval exposure under the current interval convention; update exposure timing after A01.

## What checks out, and limits of that conclusion

| Area | Audit result |
| --- | --- |
| Total/cumulative return | `product(1+r)-1` is correct for valid net return inputs; duplicated names are aliases. |
| Equity | Cash plus shares marked at each close reconciles to recursively compounded account returns. |
| Annualized return | `product(1+r)^(252/n)-1` is the period-based measure; `cagr` separately uses elapsed calendar time. |
| Volatility | Sample standard deviation (`ddof=1`) times sqrt(252), with fewer than two observations reported as undefined. |
| Sharpe | Mean net return / sample deviation times sqrt(252), assuming zero risk-free return and the usual square-root scaling assumptions. No risk-free series is implemented. |
| Sortino | Mean net return / sqrt(mean(min(r,0)^2)) times sqrt(252), using all periods and zero target return. Correct for that convention. |
| Maximum drawdown | Equity/running peak minus one, with initial capital included. `_window_result` also anchors its peak to initial capital. Negative sign convention is consistent. |
| Calmar | Not implemented; no formula to verify, and it was requested only if present. |
| Turnover | Each bar’s executed mid-price notional divided by pre-trade equity; a reversal includes its close and new entry. |
| First/last bar | First row is zero return and excluded from period count; last signal has no later bar and is not executed. Remaining holdings are marked to market, not liquidated; therefore terminal liquidation costs are intentionally absent but should be documented. |
| Built-in leakage search | Trailing uncentered rolling means and every custom callback are evaluated on timestamp prefixes; future-mutation and prefix-invariance tests pass. |
| Walk-forward splits | Fixed-length rolling training windows feed disjoint consecutive OOS folds, including a partial tail. The executed OOS account and holdings remain continuous across boundaries. |
| Invalid data | Empty/missing/infinite values, invalid/conflicting timestamps, nonpositive prices, inconsistent bars, missing weekday sessions, and nonfinite derived accounting fail explicitly. Exact duplicate rows may be deduplicated. |
| Edge behavior | Cash/no trades, all-positive and all-negative constant returns, flat-price reversal costs, and NaN-signal rejection tested. No-trade ratios are defined as zero; nonzero constant returns use signed-infinite Sharpe. These are explicit reporting conventions, not evidence of skill. |
| 100% loss | A short against a doubling price is rejected rather than producing a -100% drawdown result. This is a documented conservative limitation, not erroneous negative-equity compounding. Bankruptcy reporting and continued margin accounting are unsupported. |

OHLCV alone does not model order-book liquidity, volume-limited fills, borrow availability/fees, financing, dividends, splits, or margin. Those omissions should remain explicit limitations; they are not silently treated as bugs requiring speculative infrastructure. The sample benchmark is gross buy-and-hold from the first close, whereas the strategy has costs and an 80-bar readiness delay. Label that comparison accordingly before drawing superiority claims. Synthetic negative results are useful demonstrations, not market validation.

## Completed remediation

1. A01–A03: implemented next-open execution with fixed shares and explicit cash/fill accounting.
2. A04–A07: added a completed-trade ledger, causal prefix evaluation, and one continuous OOS account covering partial tails.
3. A08–A12: added readiness/frequency/finite checks, calendar CAGR, score direction, trade count, and exposure.
4. Converted all expected failures to passing regressions and regenerated/reconciled the sample metrics and plot.

**PASS — mathematically sound under the documented Phase 1 assumptions and safe to proceed when FastAPI is requested.**
