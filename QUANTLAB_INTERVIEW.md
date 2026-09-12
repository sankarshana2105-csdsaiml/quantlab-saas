# QuantLab interview guide

## Product and architecture

**What problem does QuantLab solve?** It makes research experiments reproducible while defending against timing, accounting, leakage, persistence, and ownership errors that can make backtests misleading.

**Why separate engine, service, repository, and routes?** The engine remains deterministic and transport-free; the service coordinates use cases; the repository owns transactions and authorization filters; routes translate HTTP contracts. This keeps one source of quantitative truth.

## Quantitative correctness

**Why execute a close-time signal at the next open?** The closing price is not known until that bar completes. Filling at the same close would grant unavailable execution and create look-ahead.

**Who owns an overnight move?** The position held before the next-open fill owns close-to-open PnL. The new position owns movement only after its fill.

**Why use cash and shares for shorts?** Explicit fill notional, signed shares, and mark-to-market equity handle asymmetric short losses and avoid the ambiguity of merely negating simple returns.

**How are reversals and costs handled?** A reversal closes the old shares and opens the opposite shares, so both economic legs affect cash. Commission uses executed notional and slippage moves each fill adversely.

**Why derive win rate from completed trades?** Return bars are not trades. Completed entry-to-exit net PnL is the defensible unit for wins, losses, profit factor, and trade count.

## Leakage and validation

**How is future leakage prevented?** Signals receive only information available by each decision time; execution is delayed; tuning uses training history only; OOS predictions are concatenated once in chronological order.

**How does walk-forward state work?** The first OOS fold starts in cash. Later folds inherit actual OOS cash and holdings, not hypothetical training positions, and boundary changes execute with real costs.

**What edge cases matter most?** Empty or invalid data, duplicate timestamps, NaN/inf values, impossible prices, insufficient history, zero trades/volatility, immediate reversals, bankruptcy, and empty/incomplete folds all have explicit behavior and tests.

## Backend, data, and security

**How do stored results remain exact?** A single service calls the validated engine, then one transaction persists configuration, metrics, trades, equity, and drawdown. Reconstruction is validated and tested against direct engine output.

**How is tenant isolation enforced?** Authenticated user UUIDs scope repository reads, lists, and deletes. Another user's valid UUID behaves as not found, preventing object enumeration.

**What are the honest production limits?** Runs are synchronous, result series are unpaginated, JWTs are stateless, and browser session storage still depends on strong XSS prevention. The dataset cap bounds current portfolio-demo workloads.

## Be ready to demonstrate

Explain one ledger row by hand, a `+1` to `-1` reversal, the independent `1e-12` reconciliation, a train/test boundary, an owner-scoped query, and the upload-to-saved-comparison browser flow.
