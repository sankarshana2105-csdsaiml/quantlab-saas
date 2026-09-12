# Sample backtest

This reproducible example uses 756 synthetic business-day OHLCV bars generated with seed 7. It contains positive, negative, and recovering drift regimes; it is demonstration data, not evidence of a tradable edge.

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m examples.sample_backtest
```

The 20/80-day moving-average strategy is long when the fast average exceeds the slow average and otherwise holds cash. A signal formed at a completed close executes at the next open. The ledger buys fractional shares with available cash, charges 5 basis points on filled notional, and moves fills adversely by 2 basis points for slippage. Expected behavior is an initial 80-bar warm-up, fewer trades than a short-window strategy, participation in sustained rises, exits after trends weaken, and unavoidable lag around reversals.

The deterministic output writes `data/sample_ohlcv.csv`, `results/sample_metrics.json`, and `results/sample_backtest.png`. Exact metrics are recorded in the JSON file; rerunning with the documented Python dependencies should reproduce them within floating-point tolerance.

Expected seed-7 results:

| Metric | Value |
| --- | ---: |
| Total return | -18.64% |
| Period-based annualized return | -6.65% |
| Calendar CAGR | -6.88% |
| Annualized volatility | 10.20% |
| Sharpe ratio | -0.62 |
| Sortino ratio | -0.87 |
| Maximum drawdown | -24.10% |
| Completed-trade win rate | 25.00% |
| Completed-trade profit factor | 0.09 |
| Completed trades | 4 |
| Exposure | 30.86% |
| Turnover | 7.9972 |

The deliberately difficult synthetic path loses about 50.07% under gross buy-and-hold. The trend strategy still loses 18.64%, which demonstrates risk reduction rather than presenting synthetic data as a profitable discovery. It is expected to remain flat while in cash and to underperform during sudden reversals because moving averages lag.

`tests/test_phase1_audit.py` independently repeats the next-open cash/share calculation with scalar arithmetic. Every saved metric, equity value, and closed-trade PnL reconciles to the engine within an absolute tolerance of `1e-12`. Daily tests currently require a complete Monday–Friday index; exchange-holiday calendars are outside this initial local engine.
